"""HTTP contracts and Freelance Scope Drift Monitor domain contracts."""
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ExternalContext(Contract):
    source: str = Field(min_length=1, max_length=100)
    content: str = Field(max_length=10000)
    trust: Literal['untrusted'] = 'untrusted'


class Fault(Contract):
    type: Literal['none', 'tool_timeout', 'malformed_tool_output', 'invalid_agent_decision'] = 'none'
    trigger: Literal['first_matching_operation'] = 'first_matching_operation'


class ArenaConfig(Contract):
    max_steps: int = Field(default=6, ge=1, le=6)
    fault: Fault = Field(default_factory=Fault)

    @field_validator('fault', mode='before')
    @classmethod
    def accept_assignment_shorthand(cls, value):
        return {'type': value} if isinstance(value, str) else value


class ArenaRequest(Contract):
    arena_version: Literal['0.1'] = '0.1'
    request_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1, max_length=80)
    task: str = Field(min_length=1, max_length=10000)
    external_context: list[ExternalContext] = Field(default_factory=list, max_length=20)
    arena_config: ArenaConfig = Field(default_factory=ArenaConfig)

    @field_validator('task')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Task must not be blank')
        return value


class ToolTrace(Contract):
    step: int = Field(ge=1, le=6)
    tool: str
    attempt: int = Field(default=1, ge=1, le=3)
    outcome: Literal['success', 'timeout', 'malformed_output', 'rejected', 'exception']
    latency_ms: float = Field(default=0, ge=0)


ToolName = Literal['list_projects', 'inspect_agreement', 'analyze_scope_drift', 'draft_change_request']


# One model decision: use one safe tool, ask a question, finish, or block.
class AgentDecision(Contract):
    status: Literal['call_tool', 'ask_clarification', 'finish', 'block']
    tool: ToolName | None = None
    arguments: dict = Field(default_factory=dict)
    user_message: str | None = Field(default=None, max_length=1000)
    reason: str = Field(default='', max_length=500)

    @model_validator(mode='after')
    def validate_status_shape(self):
        if self.status == 'call_tool' and self.tool is None:
            raise ValueError('call_tool decisions require a tool')
        if self.status != 'call_tool' and self.tool is not None:
            raise ValueError('only call_tool decisions may select a tool')
        if self.status != 'call_tool' and self.arguments:
            raise ValueError('terminal decisions must not contain tool arguments')
        return self


class FinishInput(Contract):
    reason: str = Field(min_length=1, max_length=500, description='Briefly explain why the requested task is complete.')


class TerminalInput(FinishInput):
    user_message: str = Field(min_length=1, max_length=1000, description='A concise clarification question or boundary explanation for the user.')


class Metrics(Contract):
    latency_ms: float = Field(default=0, ge=0)
    model_calls: int = Field(default=0, ge=0, le=6)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)


class AgentRunState(Contract):
    """Validated state carried only within one bounded agent run."""
    goal: str = Field(min_length=1, max_length=12000)
    current_task: str = Field(min_length=1, max_length=10000)
    requested_operations: list[Literal['list', 'inspect', 'analyze', 'draft']] = Field(default_factory=list, max_length=4)
    requested_project_id: str | None = Field(default=None, pattern=r'^project-\d{3}$')
    requested_request_id: str | None = Field(default=None, pattern=r'^request-\d{3}$')
    step: int = Field(default=0, ge=0, le=6)
    resolved_project_id: str | None = Field(default=None, pattern=r'^project-\d{3}$')
    resolved_request_id: str | None = Field(default=None, pattern=r'^request-\d{3}$')
    pending_clarification: str | None = Field(default=None, max_length=500)
    completed_actions: list[ToolName] = Field(default_factory=list, max_length=6)
    observations: list[dict[str, Any]] = Field(default_factory=list, max_length=6)
    provider_usage: dict[str, float | int | None] = Field(default_factory=dict)
    deadline_monotonic: float = Field(gt=0)


class ArenaResponse(Contract):
    arena_version: Literal['0.1'] = '0.1'
    request_id: str
    status: Literal['completed', 'needs_clarification', 'blocked', 'approval_required', 'tool_error', 'contract_error', 'budget_exceeded', 'failed']
    final_response: str = Field(min_length=1, max_length=2000)
    steps: int = Field(default=0, ge=0, le=6)
    stop_reason: str
    tool_calls: list[ToolTrace] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)
    events: list[dict] = Field(default_factory=list)
    metrics: Metrics = Field(default_factory=Metrics)


class ChatRequest(ArenaRequest):
    session_id: str = Field(min_length=16, max_length=80)
    model: str = Field(default='local-scripted', max_length=120)


class ProjectRecord(Contract):
    project_id: str = Field(pattern=r'^project-\d{3}$')
    client: str = Field(min_length=1, max_length=120)
    project_name: str = Field(min_length=1, max_length=160)
    agreed_deliverables: list[str] = Field(min_length=1, max_length=30)
    exclusions: list[str] = Field(default_factory=list, max_length=30)
    revision_limit: int = Field(ge=0, le=100)
    revisions_used: int = Field(ge=0, le=100)
    currency: str = Field(min_length=3, max_length=3)
    hourly_rate: float = Field(gt=0, le=100000)


class ClientRequestRecord(Contract):
    request_id: str = Field(pattern=r'^request-\d{3}$')
    project_id: str = Field(pattern=r'^project-\d{3}$')
    request_text: str = Field(min_length=1, max_length=4000)
    received_on: str = Field(min_length=10, max_length=10)


class ScopeFinding(Contract):
    category: Literal['deliverable_match', 'explicit_exclusion', 'revision_limit', 'missing_evidence', 'conflicting_evidence']
    evidence: str = Field(min_length=1, max_length=300)
    explanation: str = Field(min_length=1, max_length=500)


class ScopeAnalysis(Contract):
    analysis_id: str = Field(pattern=r'^analysis-\d{3}$')
    project_id: str = Field(pattern=r'^project-\d{3}$')
    request_text: str = Field(min_length=1, max_length=4000)
    classification: Literal['within_scope', 'scope_drift', 'ambiguous']
    confidence: Literal['high', 'medium', 'low']
    findings: list[ScopeFinding] = Field(min_length=1, max_length=20)
    suggested_action: str = Field(min_length=1, max_length=500)


class ChangeRequestDraft(Contract):
    draft_id: str = Field(pattern=r'^draft-\d{3}$')
    project_id: str = Field(pattern=r'^project-\d{3}$')
    analysis_id: str = Field(pattern=r'^analysis-\d{3}$')
    status: Literal['draft_only'] = 'draft_only'
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=4000)


class ToolError(Contract):
    code: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=500)


class ToolResult(Contract):
    ok: bool
    operation_id: str | None = Field(default=None, max_length=100)
    projects: list[ProjectRecord] = Field(default_factory=list, max_length=100)
    requests: list[ClientRequestRecord] = Field(default_factory=list, max_length=100)
    analysis: ScopeAnalysis | None = None
    draft: ChangeRequestDraft | None = None
    error: ToolError | None = None


class ListProjectsInput(Contract):
    max_results: int = Field(default=20, ge=1, le=100)


class InspectAgreementInput(Contract):
    project_id: str = Field(pattern=r'^project-\d{3}$')


class AnalyzeScopeDriftInput(Contract):
    project_id: str = Field(pattern=r'^project-\d{3}$')
    request_id: str | None = Field(default=None, pattern=r'^request-\d{3}$')
    request_text: str | None = Field(default=None, min_length=1, max_length=4000)

    @model_validator(mode='after')
    def require_request_source(self):
        if not self.request_id and not self.request_text:
            raise ValueError('request_id or request_text is required')
        return self


class DraftChangeRequestInput(Contract):
    project_id: str = Field(pattern=r'^project-\d{3}$')
    analysis_id: str = Field(pattern=r'^analysis-\d{3}$')
    operation_id: str = Field(min_length=1, max_length=100)
