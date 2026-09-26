"""PacketPilot bounded agent loop."""
from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.config import settings
from app.models import AgentDecision, AgentState, ArenaResponse, Metrics, ToolTrace
from app.model_clients import external_decision, is_external_model
from app.prompts import build_context, history_to_text
from app.tools import timed_call

UNSAFE_ACTION_TERMS = [
    'submit my application', 'submit the application', 'apply for me', 'send email',
    'email the committee', 'upload documents', 'delete', 'pay fee', 'make payment',
    'sign on my behalf', 'change my account', 'alter my account',
]

TERMINAL_STATUS_MAP = {
    'completed': 'completed',
    'needs_clarification': 'needs_clarification',
    'blocked': 'blocked',
    'approval_required': 'approval_required',
    'failed': 'failed',
}


class FaultController:
    def __init__(self, fault_type: str):
        self.fault_type = fault_type
        self.used = False

    def consume(self, fault_type: str) -> bool:
        if self.used or self.fault_type != fault_type:
            return False
        self.used = True
        return True


def _unsafe_request(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in UNSAFE_ACTION_TERMS)


def _has_minimum_context(state: AgentState) -> bool:
    facts = state.facts
    return bool(facts.required_documents or facts.eligibility_requirements or facts.deadline)


def _local_decision(context: dict[str, Any], state: AgentState, unsafe: bool) -> dict[str, Any]:
    if unsafe:
        return {
            'status': 'approval_required',
            'action': None,
            'arguments': {},
            'user_message': 'I can review readiness and draft next steps, but I cannot submit applications, send messages, pay fees, or alter real accounts.',
            'reason': 'The request crosses the non-destructive autonomy boundary.',
        }
    if 'extract_packet_info' not in state.completed_actions:
        return {
            'status': 'continue',
            'action': 'extract_packet_info',
            'arguments': {
                'task': context['user_goal'],
                'external_context': context['external_untrusted'],
                'history_text': context['bounded_history'],
            },
            'reason': 'Packet facts must be extracted before readiness can be assessed.',
        }
    if not _has_minimum_context(state):
        return {
            'status': 'needs_clarification',
            'action': None,
            'arguments': {},
            'user_message': 'Please paste the scholarship requirements, especially required documents, eligibility criteria, and deadline.',
            'reason': 'The task does not include enough packet requirements to evaluate readiness.',
        }
    if 'assess_eligibility' not in state.completed_actions:
        return {
            'status': 'continue',
            'action': 'assess_eligibility',
            'arguments': {'facts': state.facts},
            'reason': 'Eligibility and deadline risk must be checked before reporting readiness.',
        }
    if state.eligibility and state.eligibility.eligible is False:
        return {
            'status': 'blocked',
            'action': None,
            'arguments': {},
            'user_message': _format_blocked(state),
            'reason': 'A non-recoverable eligibility or deadline rule failed.',
        }
    if 'check_required_documents' not in state.completed_actions:
        return {
            'status': 'continue',
            'action': 'check_required_documents',
            'arguments': {'facts': state.facts},
            'reason': 'Required and provided documents must be compared.',
        }
    if 'build_readiness_report' not in state.completed_actions:
        return {
            'status': 'continue',
            'action': 'build_readiness_report',
            'arguments': {
                'facts': state.facts,
                'eligibility': state.eligibility,
                'documents': state.documents,
            },
            'reason': 'A final readiness report can now be assembled from validated tool outputs.',
        }
    report = state.observations[-1].get('result', {}) if state.observations else {}
    if report.get('readiness') == 'needs_clarification':
        return {
            'status': 'needs_clarification',
            'action': None,
            'arguments': {},
            'user_message': _format_report(report),
            'reason': 'Critical eligibility information is missing.',
        }
    return {
        'status': 'completed',
        'action': None,
        'arguments': {},
        'user_message': _format_report(report),
        'reason': 'The packet readiness check is complete.',
    }


def _complete_decision_arguments(raw_decision: dict[str, Any], context: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = raw_decision.get('action')
    if raw_decision.get('status') != 'continue' or not action:
        raw_decision.setdefault('arguments', {})
        return raw_decision
    if action == 'extract_packet_info':
        raw_decision['arguments'] = {
            'task': context['user_goal'],
            'external_context': context['external_untrusted'],
            'history_text': context['bounded_history'],
        }
    elif action == 'assess_eligibility':
        raw_decision['arguments'] = {'facts': state.facts}
    elif action == 'check_required_documents':
        raw_decision['arguments'] = {'facts': state.facts}
    elif action == 'build_readiness_report':
        raw_decision['arguments'] = {
            'facts': state.facts,
            'eligibility': state.eligibility,
            'documents': state.documents,
        }
    return raw_decision


def _validate_decision(decision: AgentDecision, state: AgentState) -> str | None:
    if decision.status == 'continue' and not decision.action:
        return 'continue decisions must name an action'
    if decision.status != 'continue' and decision.action is not None:
        return 'terminal decisions must not execute tools'
    order = ['extract_packet_info', 'assess_eligibility', 'check_required_documents', 'build_readiness_report']
    if decision.action:
        expected = next((action for action in order if action not in state.completed_actions), None)
        if decision.action != expected:
            return f'action {decision.action} is not valid in the current state; expected {expected}'
    if decision.action == 'assess_eligibility' and not state.facts:
        return 'eligibility assessment requires extracted facts'
    if decision.action == 'build_readiness_report' and (state.eligibility is None or state.documents is None):
        return 'readiness report requires eligibility and document assessments'
    return None


def _dump_result(result: Any) -> Any:
    return result.model_dump() if hasattr(result, 'model_dump') else result


async def _execute_tool(decision: AgentDecision, state: AgentState, fault: FaultController, traces: list[ToolTrace], errors: list[dict]) -> bool:
    tool_name = decision.action
    if not tool_name:
        return False
    max_attempts = settings.max_tool_retries + 1
    for attempt in range(1, max_attempts + 1):
        if fault.consume('tool_timeout'):
            traces.append(ToolTrace(step=state.step, tool=tool_name, attempt=attempt, outcome='timeout', latency_ms=0))
            errors.append({'type': 'tool_timeout', 'tool': tool_name, 'attempt': attempt})
            continue
        try:
            if fault.consume('malformed_tool_output'):
                traces.append(ToolTrace(step=state.step, tool=tool_name, attempt=attempt, outcome='malformed_output', latency_ms=0))
                errors.append({'type': 'malformed_tool_output', 'tool': tool_name, 'attempt': attempt})
                continue
            result, latency_ms = timed_call(tool_name, **decision.arguments)
            traces.append(ToolTrace(step=state.step, tool=tool_name, attempt=attempt, outcome='success', latency_ms=latency_ms))
            _apply_tool_result(tool_name, result, state)
            state.completed_actions.append(tool_name)
            state.observations.append({'step': state.step, 'tool': tool_name, 'result': _dump_result(result)})
            return True
        except Exception as exc:  # defensive: tool failures become typed errors
            traces.append(ToolTrace(step=state.step, tool=tool_name, attempt=attempt, outcome='exception', latency_ms=0))
            errors.append({'type': 'tool_exception', 'tool': tool_name, 'attempt': attempt, 'message': str(exc)[:300]})
    state.stop_reason = 'tool_failure_retries_exhausted'
    return False


def _apply_tool_result(tool_name: str, result: Any, state: AgentState) -> None:
    if tool_name == 'extract_packet_info':
        state.facts = result
    elif tool_name == 'assess_eligibility':
        state.eligibility = result
    elif tool_name == 'check_required_documents':
        state.documents = result


def _format_list(items: list[str]) -> str:
    return ', '.join(items) if items else 'none'


def _format_blocked(state: AgentState) -> str:
    reasons = state.eligibility.reasons if state.eligibility else ['The packet is blocked.']
    return 'Packet status: blocked. ' + ' '.join(reasons)


def _format_report(report: dict[str, Any]) -> str:
    readiness = report.get('readiness', 'unknown')
    lines = [f'Packet readiness: {readiness}.']
    if report.get('deadline_risk'):
        lines.append(f'Deadline risk: {report["deadline_risk"]}.')
    missing_info = report.get('missing_information') or []
    if missing_info:
        lines.append('Missing information: ' + _format_list(missing_info) + '.')
    missing_docs = report.get('missing_documents') or []
    if missing_docs:
        lines.append('Missing documents: ' + _format_list(missing_docs) + '.')
    provided = report.get('provided_documents') or []
    if provided:
        lines.append('Provided documents recognized: ' + _format_list(provided) + '.')
    reasons = report.get('eligibility_reasons') or []
    if reasons:
        lines.append('Eligibility notes: ' + ' '.join(reasons))
    warnings = report.get('warnings') or []
    if warnings:
        lines.append('Warnings: ' + ' '.join(warnings))
    next_steps = report.get('next_steps') or []
    if next_steps:
        lines.append('Next steps: ' + ' '.join(next_steps))
    return '\n'.join(lines)[:1900]


def _history_goal(task: str, history: list[Any]) -> str:
    if not history:
        return task
    previous = history_to_text(history, limit=4)
    return f'{previous}\ncurrent user: {task}'


async def run_agent(request, history, model):
    state = AgentState(goal=_history_goal(request.task, history))
    traces: list[ToolTrace] = []
    errors: list[dict] = []
    events: list[dict] = []
    fault = FaultController(request.arena_config.fault.type)
    invalid_repairs = 0
    unsafe = _unsafe_request(request.task)

    while state.step < request.arena_config.max_steps:
        context = build_context(request.task, history, request.external_context, state)
        decision_source = 'local-contract'
        try:
            if is_external_model(model):
                raw_decision = await external_decision(model, context, state, unsafe)
                decision_source = 'external-model'
            else:
                raw_decision = _local_decision(context, state, unsafe)
        except Exception as exc:
            errors.append({'type': 'external_model_error', 'step': state.step + 1, 'model': model, 'message': str(exc)[:300]})
            raw_decision = _local_decision(context, state, unsafe)
            decision_source = 'local-fallback'
        raw_decision = _complete_decision_arguments(raw_decision, context, state)
        state.step += 1
        events.append({'step': state.step, 'event': 'model_decision', 'model': model, 'source': decision_source, 'raw_status': raw_decision.get('status')})

        if fault.consume('invalid_agent_decision'):
            raw_decision = {'status': 'continue', 'action': 'not_registered', 'arguments': 'bad'}

        try:
            decision = AgentDecision.model_validate(raw_decision)
        except ValidationError as exc:
            errors.append({'type': 'contract_validation', 'step': state.step, 'message': str(exc)[:500]})
            invalid_repairs += 1
            if invalid_repairs <= settings.max_tool_retries and state.step < request.arena_config.max_steps:
                events.append({'step': state.step, 'event': 'contract_repair_attempt'})
                continue
            return ArenaResponse(
                request_id=request.request_id,
                status='contract_error',
                final_response='The agent could not repair an invalid model decision within the configured retry limit.',
                steps=state.step,
                stop_reason='invalid_decision_contract',
                tool_calls=traces,
                errors=errors,
                events=events,
                metrics=Metrics(model_calls=state.step),
            )

        semantic_error = _validate_decision(decision, state)
        if semantic_error:
            errors.append({'type': 'semantic_validation', 'step': state.step, 'message': semantic_error})
            invalid_repairs += 1
            if invalid_repairs <= settings.max_tool_retries and state.step < request.arena_config.max_steps:
                events.append({'step': state.step, 'event': 'semantic_repair_attempt'})
                continue
            return ArenaResponse(
                request_id=request.request_id,
                status='contract_error',
                final_response='The agent stopped because a model decision failed semantic validation.',
                steps=state.step,
                stop_reason='invalid_decision_semantics',
                tool_calls=traces,
                errors=errors,
                events=events,
                metrics=Metrics(model_calls=state.step),
            )

        events.append({'step': state.step, 'event': 'decision_validated', 'status': decision.status, 'action': decision.action})
        if decision.status != 'continue':
            return ArenaResponse(
                request_id=request.request_id,
                status=TERMINAL_STATUS_MAP[decision.status],
                final_response=decision.user_message or 'The agent stopped.',
                steps=state.step,
                stop_reason=decision.reason.replace(' ', '_')[:80],
                tool_calls=traces,
                errors=errors,
                events=events + state.observations,
                metrics=Metrics(model_calls=state.step),
            )

        ok = await _execute_tool(decision, state, fault, traces, errors)
        if not ok:
            return ArenaResponse(
                request_id=request.request_id,
                status='tool_error',
                final_response='A required tool failed after bounded retry attempts. No external action was taken.',
                steps=state.step,
                stop_reason=state.stop_reason or 'tool_failure',
                tool_calls=traces,
                errors=errors,
                events=events + state.observations,
                metrics=Metrics(model_calls=state.step),
            )

    return ArenaResponse(
        request_id=request.request_id,
        status='budget_exceeded',
        final_response='The run reached the configured maximum step budget before the packet readiness check could finish.',
        steps=state.step,
        stop_reason='step_budget_reached',
        tool_calls=traces,
        errors=errors,
        events=events + state.observations,
        metrics=Metrics(model_calls=state.step),
    )
