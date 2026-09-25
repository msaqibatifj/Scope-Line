# ScopeLine

ScopeLine is a privacy-aware Freelance Scope Drift Monitor. It compares a new
client request with the freelancer's recorded agreement, identifies evidence of
scope drift, asks for missing details, and can prepare a private change-request
draft. It never contacts a client or changes a commercial agreement.

## Completion rules

- An inspection is complete only after the agreement tool returns project evidence.
- An analysis is complete only after a request is classified as `within_scope`,
  `scope_drift`, or `ambiguous` with supporting findings.
- A draft is complete only when it refers to a stored `scope_drift` analysis.
- Missing project or request details produce `needs_clarification`.
- Sending, invoicing, charging, signing, or altering an agreement is blocked.

## Agent design canvas

| Element | Decision |
| --- | --- |
| Goal | Help freelancers recognize additional unpaid work before accepting it. |
| Completion | Return agreement-backed classification or a private reviewable draft. |
| Boundary | Application-owned sample agreements, requests, analyses, and drafts only. |
| Observations | User goal, bounded history, runtime state, untrusted notes, and validated tool results. |
| Actions | List projects, inspect agreement, analyze scope drift, draft change request. |
| State | Step count, observations, retries, analyses, drafts, operation IDs, and stop reason. |
| Autonomy | Read, classify, and draft; never communicate, contract, invoice, or charge. |
| Risks | Wrong project, vague request, prompt injection, invented terms, duplicate writes, and unbounded execution. |
| Evaluation | Evidence use, action choice, clarification, safety, contract validity, recovery, and termination. |

## How the loop works

1. Build separate prompt layers for policy, user goal, history, state, untrusted
   context, and tool observations.
2. Ask the selected provider for exactly one typed decision.
3. Validate the decision and domain-specific arguments before execution.
4. Execute at most one tool, record its result, and feed that observation back.
5. Finish, ask, block, fail safely, or stop when the six-step budget is reached.

One repair is allowed for an invalid decision. Tool timeouts and malformed outputs
are retried within `MAX_TOOL_RETRIES`. Arena fault injection affects only the first
matching operation.

## Tools

| Tool | Purpose | Important validation |
| --- | --- | --- |
| `list_projects` | Show bounded project summaries. | Maximum 100 records. |
| `inspect_agreement` | Return deliverables, exclusions, and recorded requests. | Requires a known project ID. |
| `analyze_scope_drift` | Compare request text with agreement evidence. | Requires a project plus request ID or text; stored request must belong to project. |
| `draft_change_request` | Create a private change-request draft. | Requires a stored drift analysis; operation IDs are replay-safe. |

The deterministic classifier matches explicit agreement signals and exhausted
revision allowances. A request with no defensible match is `ambiguous`, not guessed.
Client text and browser-supplied notes remain untrusted data even when they contain
instruction-like language.

## Project structure

```text
app/
  agent.py       bounded loop, local decisions, OpenRouter adapter, fault handling
  models.py      HTTP, decision, tool-input, and tool-output contracts
  tools.py       agreement inspection, analysis, and drafting tools
  sandbox.py     isolated per-run/per-chat project workspace
  prompts.py     trust-separated dynamic context
  providers.py   model allowlist, OpenRouter preflight, and cost tracking
  api.py         Arena and chat endpoints
  static/        ScopeLine browser interface
data/
  sample_data.json
evaluation/
  public_cases.json
  run_public_tests.py
tests/
  test_agent.py
  test_tools.py
```

Arena runs receive a fresh workspace. Chat sessions retain their private workspace
and up to six recent turns until reset, eviction, process restart, or TTL expiry.

## Run locally

Use Python 3.12 or newer.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
.venv/bin/python run.py
```

Open `http://127.0.0.1:8000/` for the interface or
`http://127.0.0.1:8000/docs` for API documentation.

## OpenRouter setup

The free `local-scripted` provider is always available for repeatable tests. To
enable the two OpenRouter comparison models, place the following in `.env`:

```env
MODEL_PROVIDER=openrouter
MODEL_NAME=local-scripted
ALLOWED_MODELS=local-scripted,nvidia/nemotron-3-ultra-550b-a55b:free,cohere/north-mini-code:free
ENABLE_LIVE_MODELS=true
OPENROUTER_API_KEY=sk-or-v1-your-key-here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_SITE_URL=
OPENROUTER_APP_NAME=ScopeLine
MAX_LIVE_REQUESTS_PER_MINUTE=10
SPEND_LIMIT_USD=0
```

`nvidia/nemotron-3-ultra-550b-a55b:free` is the reasoning-quality candidate.
`cohere/north-mini-code:free` is the fast comparison model with about 3B active
parameters. These free endpoints support tool calls but not `response_format`, so
the adapter requires one `submit_agent_decision` function call and then validates
its arguments with Pydantic before execution. No API key is returned by `/models`
or included in traces. OpenRouter's reported request cost is used when present.
The zero-dollar spend guard permits only model IDs ending in `:free`; a paid model
still requires an explicit positive budget before its first request.

The public default remains `local-scripted` because it passed all ten repeatable
evaluation cases, while the two free OpenRouter endpoints were inconsistent and
rate limited during the recorded comparison. Live choices remain available from
the UI for explicit testing. Each process admits at most
`MAX_LIVE_REQUESTS_PER_MINUTE` live runs and accumulates provider-reported cost
against `SPEND_LIMIT_USD`; both counters reset when the process restarts.

## Model selection evidence

The same ten cases were run against both live candidates. Nemotron scored 0/10
task successes at 23.23 seconds average latency; North scored 1/10 at 19.85
seconds. Both reported $0 cost, but contract-tool failures, timeouts, and subsequent
HTTP 429 responses made neither suitable as the evaluation default. Nemotron's 1M
context and stronger reasoning profile suit nuanced agreement review; North's 256K
context and smaller active footprint favor latency. ScopeLine needs far less context
than either limit, so observed reliability outranks context size. The post-fix
Nemotron smoke run completed correctly in 12.49 seconds, making it the preferred
experimental live choice. Full evidence is in
`evaluation/model_comparison.md` and `evaluation/model_comparison_results.json`.

Free endpoints are rate limited and their availability can change. Do not use the
NVIDIA free endpoint for confidential or personal client data; it is configured
here only for synthetic assignment fixtures. A production launch needs models and
provider policies approved for private commercial documents.

## API

- `GET /health`
- `GET /models`
- `GET /arena/manifest`
- `POST /arena/run`
- `POST /chat`
- `DELETE /chat/{session_id}`

Minimal Arena request:

```json
{
  "task": "Analyze request-001 for project-001 and draft a change request",
  "external_context": [],
  "arena_config": {"max_steps": 6, "fault": "none"}
}
```

Supported faults are `none`, `tool_timeout`, `malformed_tool_output`, and
`invalid_agent_decision`. Responses retain the assignment's machine-readable
status, step count, stop reason, tool trace, errors, events, and metrics.

## Verification

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python evaluation/run_public_tests.py --url http://127.0.0.1:8000
```

The test suite covers the four tools, three classifications, clarification,
multi-turn continuity, autonomy boundaries, untrusted input, replay safety,
session isolation, step exhaustion, invalid decisions, dependency faults, and
OpenRouter request construction without making a paid call.

## Deployment notes

Use one worker because chat memory and project workspaces are process-local.
For Render, use build command `pip install -r requirements.txt` and start command
`uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`. Configure the OpenRouter
key only in host secrets. Free-service restarts erase in-memory chats and drafts.

## Known limitations

- Agreement matching is evidence-oriented but keyword-based in the local baseline.
- ScopeLine is an operational aid, not legal advice or a substitute for contract review.
- Drafts are not sent and estimates are not finalized automatically.
- The included records are synthetic; production use needs authenticated tenant
  storage, encryption, durable audit/rate/spend counters, and explicit client consent.

OpenRouter references: https://openrouter.ai/docs/quickstart,
https://openrouter.ai/docs/guides/features/structured-outputs,
https://openrouter.ai/nvidia/nemotron-3-ultra-550b-a55b:free, and
https://openrouter.ai/cohere/north-mini-code:free.
