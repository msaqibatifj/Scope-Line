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
5. Finish only from validated agreement, analysis, or draft evidence; otherwise repair once or stop with a typed contract error.

One repair is allowed for an invalid decision. Tool timeouts and malformed outputs
are retried within `MAX_TOOL_RETRIES`. Each tool attempt operates on an isolated
sandbox copy and commits only after its typed result succeeds before the run
deadline. Arena fault injection affects only the first matching operation.

## Architecture and contracts

```text
Browser / Arena request
        |
     FastAPI routes
        |
  timeout + response guard
        |
 typed agent state and decision loop
   |          |             |
prompt     validator      sandbox tools
layers       |             |
   +------ validated observations ------+
        |
  typed Arena response, trace, metrics
```

Every provider decision is validated as an `AgentDecision` before execution. A
tool decision can select only one registered tool and must satisfy that tool's
Pydantic input model. Semantic checks then require user-selected project/request
provenance, the correct action order, and evidence for every requested operation
before `finish` can produce `completed`. A failed validation gets one repair
attempt; otherwise the run returns `contract_error`.

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
  agent.py       bounded loop, local decisions, provider adapters, fault handling
  models.py      HTTP, decision, tool-input, and tool-output contracts
  tools.py       agreement inspection, analysis, and drafting tools
  sandbox.py     isolated per-run/per-chat project workspace
  prompts.py     trust-separated dynamic context
  providers.py   model routing, provider preflight, and cost tracking
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
and a configurable bounded history until reset, eviction, process restart, or TTL expiry.
The browser workspace has separate Chat and Context tabs. Text pasted into Context
stays attached to the current review and is always submitted as untrusted external
data; starting a new review clears it.

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

## Gemini and Groq setup

ScopeLine compares two Gemini candidates and uses Qwen as the sole runtime backup:

| Role | ScopeLine model ID | Provider API model ID |
| --- | --- | --- |
| Candidate A | `gemini-3.1-flash-lite` | `gemini-3.1-flash-lite` (Google) |
| Candidate B (selected default) | `gemini-3.5-flash-lite` | `gemini-3.5-flash-lite` (Google) |
| Backup | `groq/qwen3.8-27b` | `qwen/qwen3.8-27b` (Groq) |
| Offline tests | `local-scripted` | No provider call |

Set `GEMINI_API_KEY` and `GROQ_API_KEY` in your local `.env` or host secrets.
The two Gemini models share the Gemini key; Qwen uses a separate Groq key.
The existing OpenRouter adapter remains available for historical reproducibility,
but OpenRouter is not used by these three model IDs.

```env
MODEL_PROVIDER=gemini
MODEL_NAME=gemini-3.5-flash-lite
ALLOWED_MODELS=local-scripted,gemini-3.1-flash-lite,gemini-3.5-flash-lite,groq/qwen3.8-27b
FALLBACK_MODELS=groq/qwen3.8-27b
ENABLE_LIVE_MODELS=true
GEMINI_API_KEY=
GROQ_API_KEY=
ALLOW_MODEL_FALLBACK=true
ALLOW_LOCAL_FALLBACK=false
DIRECT_API_FREE_TIER=true
SPEND_LIMIT_USD=0
MODEL_TIMEOUT_SECONDS=10
MAX_HISTORY_MESSAGES=12
MAX_HISTORY_CHARS=20000
MAX_HISTORY_MESSAGE_CHARS=2000
MAX_EXTERNAL_CONTEXT_CHARS=4000
```

`DIRECT_API_FREE_TIER=true` declares that the Gemini and Groq keys use free-tier
accounts with paid billing disabled. This setting does not change provider billing;
provider-side quotas enforce free usage. For paid accounts, set it to `false` and
configure a positive `SPEND_LIMIT_USD`. The process-local guard uses returned cost
when available; unknown paid pricing remains `null` rather than being reported as
zero. It is not a provider billing cap. Token usage is recorded for successful
parsed responses. Use synthetic assignment fixtures for evaluation.

Each call selects exactly one domain tool or terminal decision (`finish`,
`ask_clarification`, `block`) over the providers' OpenAI-compatible HTTPS APIs.
Each function's schema is generated from its Pydantic input contract, including
required fields, permitted arguments and length/range constraints. The application
validates the selected function before execution; it never strips invalid fields
to conceal a contract error. When the model chooses `finish`, the final response is
rendered from the validated tool evidence rather than an unsupported model claim.
Gemini uses minimal thinking; Qwen uses instruct mode. No additional SDK is needed.

On timeout, network failure, HTTP 429, or server error, the next configured,
credentialed model takes over with the existing tool observations and run state.
Each failed provider attempt consumes a decision step. Backups share the six-step
and 40-second run budgets, and every switch emits `provider_fallback`. Either Gemini candidate falls back directly to Qwen; the Gemini candidates never
fall back to each other, and Qwen never cycles back to Gemini.
Authentication failures and invalid model decisions follow typed failure/repair
handling instead of silently switching providers.

Automatic deterministic fallback is disabled by default. `local-scripted` remains
selectable for offline testing. Missing keys produce an explicit readiness/failure
state; they do not establish a successful live-model run.

## Model selection evidence and release gate

The historical comparison below used the same ten cases with both fallback paths disabled.
The first run saved `evaluation/gemini_comparison_results.json`; a slower retry with
`MODEL_TIMEOUT_SECONDS=30` and `--delay 30` saved `evaluation/gemini_comparison_results_retry.json`:

| Candidate | Best live-only task checks passed | Valid contracts | Mean run latency | Input / output tokens | Fallback runs |
| --- | ---: | ---: | ---: | ---: | ---: |
| Gemini 3.1 Flash-Lite | 9/10 | 10/10 | 5.91 s | 50,385 / 706 | 0 |
| Gemini 3.5 Flash-Lite | 9/10 | 10/10 | 3.93 s | 50,733 / 510 | 0 |

The remaining 3.1 retry failure was a Gemini API 503 on `List projects`. The remaining
3.5 retry failure was a correctly rejected model action: it selected `list_projects`
when the task needed a clarification. The project release target remains 9/10
live-only successes with no fallback. Those historical results selected 3.1. See
[evaluation/gemini_comparison.md](evaluation/gemini_comparison.md) for case results,
limitations, source provenance and raw evidence. Estimated cost was zero under the
configured free-tier assumption; this is not a provider billing receipt.

Historical OpenRouter evidence is excluded from the Gemini selection decision.

Before release, start the server with **both** `ALLOW_MODEL_FALLBACK=false` and
`ALLOW_LOCAL_FALLBACK=false`, then run the two Gemini candidates against the same
ten cases. The runner writes `evaluation/gemini_comparison_results.json`, keeping
historical results intact. A run that switches to any backup does not count as a
success for the originally selected model. Qwen is the runtime backup, not a candidate in this comparison. The runner refuses
to benchmark a server with either fallback switch enabled. Select the production
Gemini default after reviewing the comparison. The current selection is 3.5; current
source evidence is saved separately in `evaluation/current_comparison_results.json`.

The repaired implementation's 3 October comparison selected **Gemini 3.5 Flash-Lite**:

| Candidate | Task success | Valid model decisions | Mean latency | Input / output tokens | Known cost coverage |
| --- | ---: | ---: | ---: | ---: | --- |
| Gemini 3.1 Flash-Lite | 9/10 | 16/17 | 16.77 s | 46,487 / 671 | 9/10 runs, $0 known estimate |
| Gemini 3.5 Flash-Lite | 10/10 | 18/18 | 2.99 s | 49,132 / 560 | 10/10 runs, $0 estimated |

Both produced 10/10 valid outer Arena responses, which is a different metric from
valid model decisions. Neither used fallback. The 3.1 failure was a provider read
timeout. 3.5 completed every tested task with lower latency and fully valid actual
decisions, making it the better current default despite slightly higher input-token
usage. Read `evaluation/current_model_comparison.md` for coverage, injected-fault
handling, limitations and source provenance. An existing `.env` or hosting
`MODEL_NAME` setting overrides the default; set it to `gemini-3.5-flash-lite` to use
the selected candidate.

The task requires short structured decisions rather than long-form generation. The
retained history is bounded to 12 messages and 20,000 characters, each history
message to 2,000 characters, and each untrusted context item to 4,000 characters.
With at most six bounded tool observations and 512 output tokens per call, the
application keeps context bounded and does not depend on maximum context capacity.
The two candidates handled these bounded prompts in the recorded comparison. Context omissions are marked
in prompts and traces; the active pending goal is stored separately from history.
Verify provider limits when changing models or raising these settings.

Record task success, first-attempt model-decision validity, repaired decisions,
action selection, latency, available-token coverage, and cost. The runner validates
the typed outer response separately from raw model-decision validity. The project release target remains at least 9/10 live-only successes with
no autonomy or unsupported-completion failures. This is a project target, not a
threshold prescribed by the assignment. Restore model fallback after comparison.

Official provider references:
[Gemini 3.1](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite),
[Gemini 3.5](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite),
[Gemini API compatibility](https://ai.google.dev/gemini-api/docs/openai), and
[Groq Qwen 3.8 27B](https://console.groq.com/docs/model/qwen/qwen3.8-27b).

## API

- `GET /health`
- `GET /models`
- `GET /arena/manifest`
- `POST /arena/run`
- `POST /run` — alias with the same request, response, default model and execution limits
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
# Start a server with ALLOW_MODEL_FALLBACK=false and ALLOW_LOCAL_FALLBACK=false for comparison.
.venv/bin/python evaluation/run_model_comparison.py --url http://127.0.0.1:8000 --delay 20
# Or run the local API in-process, with real inference and fallback disabled automatically:
.venv/bin/python evaluation/run_model_comparison.py --in-process --delay 20
```

The test suite covers the four tools, conservative mixed/negated classifications, clarification,
multi-turn continuity, autonomy boundaries, untrusted input, replay safety,
session isolation, step exhaustion, invalid decisions, dependency faults, and
provider request construction without making a paid call.

## Deployment notes

Use one worker because chat memory and project workspaces are process-local.
For Vercel, `vercel.json` routes requests to `api/index.py`, which imports the
FastAPI ASGI app from `app.main`. Configure Gemini and Groq keys only in host
secrets. For Render, use build command `pip install -r requirements.txt` and start
command `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`. Free-service
restarts erase in-memory chats and drafts. `/models` reports whether the configured
live default is ready and the UI exposes degraded fallback mode when a transient
provider failure occurs.

The current public URL is https://scope-line.vercel.app/. Configuration readiness
means the provider is enabled and a credential is present; it does not authenticate
the credential. On 3 October, public health and manifest succeeded, while a default
Arena run returned a Gemini 401. Correct production authentication and redeploy the
repaired source before treating the public application as submission-ready.

On Vercel, process-local conversation state may disappear when requests reach a
different instance. Use the documented single-worker Render deployment or shared
session storage if stable cross-request sessions are required under scaling.

## Submission packaging

Copy `release/submission.example.json` outside the repository, fill every required
field only after deploying the recorded commit, then run:

```bash
.venv/bin/python -m pip install -r release/requirements.txt
.venv/bin/python release/prepare_submission.py --metadata /safe/path/submission.json
```

The command creates the required roll-number ZIP and clickable submission PDF in
`dist/`. It uses an allowlist and excludes secrets, environments, PDFs used as
references, Git metadata, and `student-agent/`. Extract the ZIP to a fresh folder,
install dependencies, run the tests, and verify the public URLs before upload.

The helper checks that the Git checkout matches `final_commit_hash` and the source
is clean (only generated `SUBMISSION.md` may differ). Commit the source first, then
put that hash in an external metadata file. The helper generates identical PDF and
Markdown fields after the source commit; this avoids a self-referential commit hash.
It rejects placeholder/private/reserved URLs, wraps long fields, embeds a TrueType
font and links each URL on its own row. Set `SUBMISSION_FONT` if your name requires
a font unavailable on the host. Inspect the rendered PDF before turning in.

Uncommitted review snapshots can be prepared by calling the generator functions,
but must be labeled as drafts and must not claim to represent the deployed commit.

Clarification replies update typed pending-goal fields. Completion, failure and
reset clear that goal, so acknowledgements do not replay completed operations.
Inline client text follows a colon or a `client says` marker and remains data;
use a request ID for stored requests. Safe compound operations are supported.
Each requested operation needs successful evidence before completion. Input over
the 4,000-character client-request limit receives an explicit budget stop; output
omissions and response-size failures are traced.

## Known limitations

- Agreement matching is evidence-oriented but keyword-based in the local baseline.
- ScopeLine is an operational aid, not legal advice or a substitute for contract review.
- Drafts are not sent and estimates are not finalized automatically.
- The included records are synthetic; production use needs authenticated tenant
  storage, encryption, durable audit/rate/spend counters, and explicit client consent.
