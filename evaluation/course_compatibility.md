# Course Compatibility Audit

Reviewed on 2026-09-26 against `Agentic.pdf` and the available
`student-agent/` implementation. The two assignment PDFs in the workspace are
byte-for-byte identical. No separate final starter archive or announcement is
present locally.

## Arena contract

| Requirement | ScopeLine | Result |
| --- | --- | --- |
| `POST /arena/run` | Typed `ArenaRequest` to typed `ArenaResponse` | Compatible |
| Request task | Required nonblank `task` | Compatible |
| External context | Optional bounded `external_context` | Compatible |
| Step configuration | `arena_config.max_steps`, capped at 6 | Compatible |
| Fault shorthand | Accepts `"none"` and the typed fault object | Compatible extension |
| Response core | `status`, `final_response`, `steps`, `stop_reason`, `tool_calls`, `errors` | Compatible |
| Recommended statuses | All PDF statuses plus `approval_required` | Compatible extension |
| Required routes | `/health`, `/arena/run`, `/arena/manifest` | Compatible |

ScopeLine also returns request/version identifiers, events, and metrics. These are
additive response fields. The available `student-agent/` models use the same
request, response, fault, trace, metric, and six-step definitions.

## Fault behavior

The PDF defines stress categories but does not prescribe exact fault names beyond
the example value `none`. ScopeLine exposes one-shot `invalid_agent_decision`,
`tool_timeout`, and `malformed_tool_output` faults. Each is injected at its named
boundary, recorded in events/traces, bounded by repair/retry policy, and covered by
tests. This matches the available implementation and the PDF's invalid-contract,
dependency-failure, and budget expectations.

## Manifest

The PDF requires `GET /arena/manifest` but does not publish an exact manifest JSON
schema. ScopeLine reports the Arena version, identity, domain, description,
endpoints, supported faults, limits, and autonomy boundary. This contains the same
core fields as the available implementation.

## Default model decision

The PDF states that the model must influence at least one meaningful execution
decision. `local-scripted` is deterministic application policy and cannot satisfy
that requirement by itself. The current deployment default is Gemini 3.1 Flash-Lite through the Gemini API,
with Gemini 3.5 Flash-Lite as the other comparison candidate and Groq Qwen 3.8
27B as the sole runtime backup. The default is provisional pending comparison. The local
policy is selectable for offline tests; automatic local fallback is disabled.
Provider changes are recorded as `provider_fallback` and share run budgets.

The original OpenRouter deployment-default configuration was exercised locally
while OpenRouter returned HTTP 429, completing ten cases through local fallback.
That historical result is not evidence for Gemini or Groq. The latest live-only Gemini retry records 9/10 for 3.1 and 9/10 for 3.5, with no fallback runs. The remaining 3.1 failure was a provider 503; the remaining 3.5 failure was a controller rejection of an unsupported `list_projects` action during a clarification case. See `evaluation/gemini_comparison.md`.

## Remaining external confirmation

If the instructor announcement supplies models that differ from the PDF example,
those final models take precedence. That announcement or starter archive must be
added to the workspace for a byte-for-byte final comparison.
