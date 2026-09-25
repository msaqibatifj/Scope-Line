"""Typed tools for checking freelance requests against agreed project scope."""
from __future__ import annotations

import json
from typing import Callable

from app.models import (
    AnalyzeScopeDriftInput,
    ChangeRequestDraft,
    DraftChangeRequestInput,
    InspectAgreementInput,
    ListProjectsInput,
    ScopeAnalysis,
    ScopeFinding,
    ToolError,
    ToolResult,
)
from app.sandbox import Sandbox, SandboxError


class ScopeDriftTools:
    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox

    def list_projects(self, args: ListProjectsInput) -> ToolResult:
        # Step 1: return only bounded, application-owned project summaries.
        try:
            return ToolResult(ok=True, projects=self.sandbox.all_projects()[:args.max_results])
        except (SandboxError, ValueError) as error:
            return self._error(self._normalize(error))

    def inspect_agreement(self, args: InspectAgreementInput) -> ToolResult:
        # Step 2: expose the agreed deliverables and exclusions for one project.
        try:
            project = self.sandbox.project(args.project_id)
            requests = [
                self.sandbox.request(request_id)
                for request_id in sorted(self.sandbox.requests)
                if self.sandbox.requests[request_id]['project_id'] == args.project_id
            ]
            return ToolResult(ok=True, projects=[project], requests=requests)
        except (SandboxError, ValueError) as error:
            return self._error(self._normalize(error))

    def analyze_scope_drift(self, args: AnalyzeScopeDriftInput) -> ToolResult:
        # Step 3: compare request language with explicit agreement evidence.
        try:
            project = self.sandbox.project(args.project_id)
            request_text = args.request_text
            if args.request_id:
                request_text = self.sandbox.request(args.request_id, args.project_id).request_text
            assert request_text is not None
            lowered = request_text.lower().replace('-', ' ')
            within_signals, outside_signals = self.sandbox.project_signals(args.project_id)
            matched_within = [signal for signal in within_signals if signal in lowered]
            matched_outside = [signal for signal in outside_signals if signal in lowered]
            findings: list[ScopeFinding] = []

            for signal in matched_outside[:5]:
                findings.append(ScopeFinding(
                    category='explicit_exclusion',
                    evidence=signal,
                    explanation='The request matches work explicitly excluded from the agreement.',
                ))

            revision_words = ('revision', 'change', 'update', 'make it', 'replace')
            revision_request = any(word in lowered for word in revision_words)
            if revision_request and project.revisions_used >= project.revision_limit:
                findings.append(ScopeFinding(
                    category='revision_limit',
                    evidence=f'{project.revisions_used} of {project.revision_limit} revisions already used',
                    explanation='The agreed revision allowance has been exhausted.',
                ))

            if findings:
                classification = 'scope_drift'
                confidence = 'high'
                suggested_action = 'Review a written change request with the client before accepting the added work.'
            elif matched_within:
                findings.extend(ScopeFinding(
                    category='deliverable_match',
                    evidence=signal,
                    explanation='The request matches an agreed deliverable or an available revision.',
                ) for signal in matched_within[:5])
                classification = 'within_scope'
                confidence = 'medium'
                suggested_action = 'Confirm scheduling details, then continue under the existing agreement.'
            else:
                findings.append(ScopeFinding(
                    category='missing_evidence',
                    evidence=request_text[:300],
                    explanation='The request is not specific enough to map to a deliverable or exclusion.',
                ))
                classification = 'ambiguous'
                confidence = 'low'
                suggested_action = 'Ask the client for concrete deliverables, quantity, format, and deadline.'

            analysis = ScopeAnalysis(
                analysis_id=self.sandbox.next_analysis_id(),
                project_id=args.project_id,
                request_text=request_text,
                classification=classification,
                confidence=confidence,
                findings=findings,
                suggested_action=suggested_action,
            )
            self.sandbox.analyses[analysis.analysis_id] = analysis
            return ToolResult(ok=True, projects=[project], analysis=analysis)
        except (SandboxError, ValueError) as error:
            return self._error(self._normalize(error))

    def draft_change_request(self, args: DraftChangeRequestInput) -> ToolResult:
        # Step 4: create a private draft only; never send or alter an agreement.
        signature = json.dumps(['draft', args.model_dump()], sort_keys=True)
        replay = self._replay(args.operation_id, signature)
        if replay is not None:
            return replay
        try:
            project = self.sandbox.project(args.project_id)
            analysis = self.sandbox.analyses.get(args.analysis_id)
            if analysis is None:
                raise SandboxError('unknown_analysis_id', f'Unknown analysis ID: {args.analysis_id}')
            if analysis.project_id != args.project_id:
                raise SandboxError('analysis_project_mismatch', 'The analysis belongs to another project.')
            if analysis.classification != 'scope_drift':
                raise SandboxError('change_request_not_supported', 'A change-request draft requires confirmed scope drift.')
            evidence = '; '.join(finding.evidence for finding in analysis.findings)
            draft = ChangeRequestDraft(
                draft_id=self.sandbox.next_draft_id(),
                project_id=args.project_id,
                analysis_id=args.analysis_id,
                subject=f'Scope change for {project.project_name}',
                body=(
                    f'Hi {project.client},\n\nThanks for the additional request: "{analysis.request_text}"\n\n'
                    f'This appears to extend beyond our current agreement because it involves: {evidence}. '
                    'I can prepare a separate estimate and timeline for your approval before starting this work. '
                    f'The current reference rate is {project.currency} {project.hourly_rate:g}/hour; no fee or deadline '
                    'will change until we both approve the written change.\n\nBest,'
                ),
            )
            self.sandbox.drafts[draft.draft_id] = draft
            result = ToolResult(ok=True, operation_id=args.operation_id, projects=[project], analysis=analysis, draft=draft)
            self.sandbox.operations[args.operation_id] = (signature, result.model_copy(deep=True))
            return result
        except (SandboxError, ValueError) as error:
            return self._error(self._normalize(error), args.operation_id)

    def _replay(self, operation_id: str, signature: str) -> ToolResult | None:
        existing = self.sandbox.operations.get(operation_id)
        if existing is None:
            return None
        if existing[0] == signature:
            return existing[1].model_copy(deep=True)
        return ToolResult(ok=False, operation_id=operation_id, error=ToolError(
            code='operation_id_conflict',
            message='Operation ID was already used for a different action.',
        ))

    @staticmethod
    def _normalize(error):
        if isinstance(error, SandboxError):
            return error
        return SandboxError('invalid_fixture_data', 'The project data could not be read safely.')

    @staticmethod
    def _error(error: SandboxError, operation_id: str | None = None) -> ToolResult:
        return ToolResult(ok=False, operation_id=operation_id, error=ToolError(code=error.code, message=str(error)))


TOOLS: dict[str, Callable] = {
    'list_projects': ScopeDriftTools.list_projects,
    'inspect_agreement': ScopeDriftTools.inspect_agreement,
    'analyze_scope_drift': ScopeDriftTools.analyze_scope_drift,
    'draft_change_request': ScopeDriftTools.draft_change_request,
}
