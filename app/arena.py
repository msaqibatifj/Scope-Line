"""Common boundary; ordinary Arena requests have no chat memory."""
import asyncio
import logging
from time import perf_counter
from app.agent import run_agent
from app.config import settings
from app.models import ArenaResponse, Metrics
from app.sandbox import Sandbox
log = logging.getLogger('arena')
async def execute(request, history=None, model='unconfigured', sandbox=None):
    started = perf_counter()
    request = request.model_copy(deep=True)
    request.arena_config.max_steps = min(request.arena_config.max_steps, settings.max_steps)
    owns_sandbox = sandbox is None
    progress = {'steps': 0, 'tool_calls': [], 'errors': [], 'events': [], 'usage': {}}
    try:
        if owns_sandbox:
            sandbox = Sandbox.create()
        async with asyncio.timeout(settings.run_timeout_seconds):
            result = await run_agent(request, history or [], model, sandbox=sandbox, progress=progress)
            result = ArenaResponse.model_validate(result)
    except TimeoutError:
        usage = progress.get('usage') or {}
        result = ArenaResponse(request_id=request.request_id, status='budget_exceeded',
            final_response='The run timed out after preserving completed trace evidence.',
            stop_reason='time_budget_reached',
            steps=min(int(progress.get('steps') or 0), request.arena_config.max_steps),
            tool_calls=progress.get('tool_calls') or [],
            errors=progress.get('errors') or [],
            events=progress.get('events') or [],
            metrics=Metrics(
                model_calls=min(int(progress.get('steps') or 0), request.arena_config.max_steps),
                input_tokens=usage.get('input_tokens'),
                output_tokens=usage.get('output_tokens'),
                estimated_cost_usd=usage.get('estimated_cost_usd'),
            ))
    except Exception as error:
        usage = progress.get('usage') or {}
        result = ArenaResponse(request_id=request.request_id, status='failed',
            final_response='The run stopped due to an internal error.', stop_reason='internal_error',
            steps=min(int(progress.get('steps') or 0), request.arena_config.max_steps),
            tool_calls=progress.get('tool_calls') or [], errors=(progress.get('errors') or []) + [
                {'type': 'internal_error', 'message': str(error)[:500] or type(error).__name__}
            ], events=progress.get('events') or [], metrics=Metrics(
                model_calls=min(int(progress.get('steps') or 0), request.arena_config.max_steps),
                input_tokens=usage.get('input_tokens'), output_tokens=usage.get('output_tokens'),
                estimated_cost_usd=usage.get('estimated_cost_usd'),
            ))
    finally:
        if owns_sandbox and sandbox is not None:
            sandbox.cleanup()
    result.metrics.latency_ms = (perf_counter() - started) * 1000
    if len(result.model_dump_json().encode()) > 50000:
        result = ArenaResponse(request_id=request.request_id, status='failed',
            final_response='Response exceeded the size limit; reduce requested output or inspect the tool observations.',
            stop_reason='response_too_large', steps=result.steps, tool_calls=result.tool_calls,
            errors=[{'type': 'response_size', 'message': 'Response exceeded 50,000 bytes; oversized trace and errors omitted.', 'omitted_errors': len(result.errors)}],
            events=[{'step': result.steps, 'event': 'trace_omitted', 'reason': 'response_size_budget', 'omitted_events': len(result.events)}], metrics=result.metrics)
    log.info('request=%s status=%s steps=%s', request.request_id, result.status, result.steps)
    return result
