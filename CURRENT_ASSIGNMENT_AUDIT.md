# ScopeLine: current assignment audit

Audited on **3 October 2026** against **Assignment 1 - Agentic AI.pdf**, especially sections 4-12, 15, and 19. Source revision: `14fc765c9f89dc7323bb207a2ac64c4deee611fa`. The working tree was clean at the start of this audit. This report is the only project change made during the audit.

**Verdict: the main application has most required infrastructure, but is not ready for a verified submission.** Existing tests pass; additional probes expose incorrect completion, classification, clarification, contract recovery, and budget handling. The current public deployment is reachable, but its default model returns an authentication error. Final submission metadata and artifacts are unfinished.

This is an evidence-backed review, not an estimated academic grade. Hidden Arena tests and instructor decisions determine the actual marks. The PDF is the requirements source; its submission instructions were not treated as authorization to deploy, invite collaborators, or turn in the assignment.

## Remediation update - 3 October 2026

The findings below describe the pre-fix snapshot. The user subsequently requested
all other issues be fixed, excluding production authentication. The repository now
contains the following repairs and verification:

- **100/100 tests pass**, including 20 new audit regression tests. The original
  unmatched-work test was corrected to expect ambiguity when agreement evidence
  is missing rather than treating absent evidence as confirmed drift.
- **10/10 current local public cases pass**. A three-turn clarification containing
  `add checkout to scope` now keeps project-001 and completes. Full responses and
  source hashes are in `evaluation/current_local_results.json`.
- Actual live two-model comparison on ten identical cases, both fallbacks disabled:
  **3.1: 9/10 tasks, 16/17 valid actual decisions, 16.77 s average;
  3.5: 10/10 tasks, 18/18 valid actual decisions, 2.99 s average.**
  3.1 had one provider ReadTimeout. Raw results are in
  `evaluation/current_comparison_results.json`. The comparison ran before the
  resulting default-selection change in app/config.py, as documented in
  `evaluation/current_model_comparison.md`. Gemini 3.5 is now the source default;
  explicit environment overrides still take precedence.
- User-supplied identity, repository, current deployment URLs and invited access
  status are filled in. PDF generation wraps fields, embeds a Unicode TrueType
  font and binds each URL to its own row. A rendered preview was inspected.

| Original issue | Remediation status |
| --- | --- |
| 1: Public provider authentication | Excluded at the user's request; production 401 remains. |
| 2: Skipped inspection | Fixed: all requested operations require evidence before finish. |
| 3: Excessive quantities | Fixed for supported agreement quantities: pages and aggregate photo counts are compared with agreement limits. |
| 4: Unrelated deliverable approved | Fixed: three-letter app/API terms are considered; unmatched work is ambiguous. |
| 5: Oversized valid input | Fixed: explicit input-budget response before typed state construction. |
| 6: Oversized final response | Fixed: marker fits the schema; complete draft/analysis text is preserved in bounded observations. |
| 7-8: Lost/replayed goals | Fixed: typed pending fields, reply merging and completion/reset cleanup. |
| 9-10: Paraphrases/compound requests | Fixed for the audited variants: operation grammar and independent completion tracking support these requests. |
| 11-12: Missing/inline request extraction | Fixed: command framing is separated from concrete client data. |
| 13: Authority/trust parsing | Fixed for the audited variants: client speech/colon bodies are data; clause-specific negation and contact synonyms are handled. |
| 14: Type coercion | Fixed: contracts use strict validation. |
| 15: Envelope repair/usage | Fixed: malformed envelope fields enter bounded ValueError repair with usage retained. |
| 16: Response size | Fixed: size-failure output omits oversized events and errors. |
| 17: Context limits | Fixed: configurable count and explicit truncation/omission flags; active goals are independent of retained history. |
| 18: Missing evidence as drift | Fixed: unknown deliverables produce low-confidence ambiguity. |
| 19: Comparison imports | Fixed: the documented direct command and --help run from the repository root. |
| 20: Model evidence/metrics | Refreshed: outages and synthetic faults are separated from actual decisions; token/cost coverage and rationale recorded. |
| 21: Metadata/artifacts | Identity and links completed; final source packaging requires a source commit. Deployment match and Classroom confirmation remain external. |
| 22: Release helper | Fixed: metadata validation, links, font/wrapping, source-provenance check and environment/secret-file filtering. |

These fixes close the reproduced local defects; they do not claim universal
natural-language understanding or a guaranteed hidden-test score. The parser's
supported operations and quantity formats are deliberately bounded. Serverless
process-local session lifetime is documented. Public redeployment of this repaired
source, production authentication and Classroom Turned in confirmation still need
to happen before submission can be called complete.

## Scope and verification

The submitted application is the repository-root ScopeLine app. Root deployment configuration and the release allowlist target that app. The nested `student-agent/` is a separate tracked implementation and is excluded from the release allowlist; its earlier review findings are not counted as fresh findings against ScopeLine here. Avoid confusing that folder's README or startup commands with the root app.

Verified during this audit:

- **80/80 unit tests passed** using `python -m unittest discover -s tests -v`.
- **10/10 public cases passed locally**, using FastAPI TestClient with `local-scripted` and the comparison runner's outcome checks.
- Additional direct HTTP, tool, controller, provider-envelope, response-size, and release-metadata probes produced the failures below.
- Local settings currently report live models enabled and a Gemini credential present. No credential values were printed. Presence does not establish that the credential or selected model works.
- GET requests to the historical deployment `https://scopeline-i230769.vercel.app/health`, `/models`, and `/arena/manifest` each returned **404, DEPLOYMENT_NOT_FOUND**. The user subsequently supplied the current deployment, **https://scope-line.vercel.app/**. Its interface, `/health`, `/arena/manifest`, `/models`, `/style.css` and `/app.js` returned **HTTP 200**.
- A public POST to the current `/arena/run` with `List projects`, six steps and no injected fault returned HTTP 200 with **status `failed`, stop reason `model_call_failed`, one step, and no tool calls**. The default Gemini provider returned **401 Unauthorized**. The trace selected `gemini-3.1-flash-lite`; no fallback occurred. This is a real public dependency check, distinct from the offline tests.
- Browser appearance was not visually verified. Static assets and interface controls exist, but that is not proof of the complete browser interaction flow.

Local deterministic results demonstrate controller behavior; they do not replace the requirement for a model to influence a meaningful decision.

## Assignment coverage

| Requirement | Current assessment | Evidence / remaining gap |
| --- | --- | --- |
| Narrow operational goal; nine-part design canvas | Present | README defines scope monitoring, evidence, completion, boundaries and risks. Custom-domain approval, if required, remains an external check. |
| At least three meaningful tools | Present | Four tools: list, inspect, analyze and private draft. |
| Genuine model decision and feedback loop | Implemented; current live run unverified | Live providers choose typed actions; results feed subsequent decisions. Offline tests alone are insufficient evidence. |
| State, stopping and bounded repair | Partial | Typed state, six-step ceiling and one decision repair exist; completion and oversized-input defects remain. |
| FastAPI health, manifest, Arena contract | Present; live execution blocked | Current public health and manifest work; Arena returns a typed model-authentication failure. |
| Stable sessions, typed bounded history, reset | Partial | LangChain messages and reset exist; active-goal reconstruction fails on legitimate replies. |
| Configurable budgets and usage/cost | Partial | Limits and provider usage tracking exist; truncation, size enforcement and malformed-envelope usage have gaps. |
| Dynamic trust-separated context | Partial | Separate system/user/history/state/untrusted/observations layers exist. Authority and intent checks still confuse user instructions with embedded client text. |
| Typed schema and semantic validation | Partial | Pydantic models, allowlists and repair exist; wrong-type coercion and semantic failures are reproducible. |
| Two-model comparison on roughly ten identical cases | Historical evidence present | Two Gemini candidates have ten-case evidence from 26 September. Eight app source hashes differ now; metrics also conflate outer response validity with model-output validity. |
| Minimal UI | Controls/assets present | Chat, model selection, status, trace, observations, context and reset are implemented. Public/browser verification remains incomplete. |
| README diagrams, setup, limitations | Mostly present | Architecture and folder diagrams exist. Documented comparison command fails; selection wording is inconsistent. |
| Public verification and current release provenance | Partial | Current URL verified; default-model Arena run fails authentication. No current deployed commit evidence. |
| ZIP, separate linked PDF and matching metadata | Incomplete | SUBMISSION.md has placeholders; no final artifacts in `dist/`; release helper defects remain. |
| Repository access and Classroom turn-in | Not verifiable from code | Require external confirmation. No invitations or submission actions performed. |

## Confirmed issues, ordered by impact

Priority meanings: **P1** = submission blocker or materially incorrect result; **P2** = reliability/contract defect; **P3** = documentation or helper robustness defect. These are engineering priorities, not assigned marks.

### 1. Current deployment cannot execute its default model — P1

**Requirement:** PDF sections 4, 15, 15.1 and 19 require public endpoints reachable during evaluation.

The user confirmed **https://scope-line.vercel.app/** as the current deployment. Its interface, assets, health and manifest are available. A public Arena POST for `List projects` fails on the first default-model call: Gemini returns **401 Unauthorized**, and the app reports `failed / model_call_failed` with no tool execution. `/models` reports `ready: true / live_model_configured`, which checks configuration presence rather than successful provider authentication. Authentication errors correctly do not trigger a backup, but the configured primary must work for the evaluator.

The historical URL in `evaluation/public_results.json` is unavailable. `SUBMISSION.md` contains placeholder URLs rather than the current address. The saved 10/10 result from 26 September does not establish present functional availability.

**Needed:** correct the production Gemini credential/authentication configuration, redeploy if needed, then verify a successful public Arena run. Record the current URLs and corresponding final deployed commit. A 401 alone does not establish whether the credential is missing, invalid, revoked, or otherwise configured incorrectly.

### 2. Completion can skip an explicitly requested inspection — P1

**Location:** `app/agent.py:583`, especially the early draft branch in `_validate_finish_evidence`.

For `Inspect agreement for project-001 and analyze request-001 and draft a change request`, a controlled provider sequence of analysis → draft → finish returns `completed`, with only analysis and draft in the tool trace. The requested inspection never happens. The draft branch returns before checking the other requested operations.

This probe controls provider output to exercise the shared validator; the defect can affect any provider, and is not merely a local policy limitation.

**Needed:** require successful evidence for every requested operation before accepting finish, including when drafting is requested.

### 3. Agreement quantity checks approve excessive work — P1

**Location:** `app/tools.py:234`, `app/tools.py:267`.

Direct tool probes:

| Agreement | Request | Actual result | Required reasoning |
| --- | --- | --- | --- |
| Five-page website | `Please deliver ten responsive pages.` | `within_scope` | Ten pages exceed five. Page counts are not checked. |
| Twenty photographs | `Please deliver 10 photos plus 15 photos on a neutral background.` | `within_scope` | The total is 25. The parser returns the first count rather than interpreting the combined quantity. |

**Needed:** model agreement quantities explicitly and compare the entire requested deliverable, including aggregates. Do not let a matching style signal override a breached limit.

### 4. Matching one deliverable can approve unrelated additional work — P1

**Location:** `app/tools.py:289`.

`Please use a neutral background and build a custom app.` for project-003 returns `within_scope`. The token regex accepts words of four or more letters, while the material-term set contains three-letter `app` and `api`. Those terms are never captured by that regex. The neutral-background match then approves the combined request.

Adding `mobile` changes the same request to `scope_drift`, showing wording-dependent classification.

**Needed:** inspect every requested deliverable; unknown additional work must not inherit approval from another clause.

### 5. Valid longer HTTP input causes an internal error — P1

**Location:** `app/agent.py:261`, `app/models.py:101`.

`Analyze project-001: ` followed by `neutral background ` repeated 250 times is below the HTTP task limit of 10,000 characters. The whole task is copied to `requested_request_text`, whose limit is 4,000. State construction fails before the first decision. The API returns `failed / internal_error`, zero steps, rather than clarification or an explicit budget/input-limit response.

**Needed:** reconcile input and state limits and validate the extracted request before constructing state. Avoid copying command framing into domain request text.

### 6. Output truncation itself violates the response contract — P1

**Location:** `app/agent.py:451`.

Calling `_response` with a 2,100-character final answer raises a Pydantic validation error. The retained 1,900 characters plus the truncation message exceed the 2,000-character schema limit. A long otherwise successful result can therefore become an internal failure.

The message also directs the user to a complete observation, but the trace retains only the first 1,000 draft-body characters (`app/agent.py:709`), so that promise is unsupported.

**Needed:** reserve space for the marker, preserve or make complete results retrievable, and report the output budget explicitly.

### 7. Clarification replies can discard the active goal and selected project — P1

**Location:** `app/agent.py:481`.

Verified chat sequence:

1. `Analyze scope drift` → asks for project.
2. `project-001` → asks for client request.
3. `add checkout to scope` → asks for project again.

The last reply contains `scope`, so `_has_operation_intent` treats it as a fresh task and discards the previous project selection. This violates the active-goal requirement in PDF section 7.1.

**Needed:** retain typed pending-goal state and merge clarification answers into it; do not decide whether an answer starts a new task solely by keywords.

### 8. Completed history is replayed as though still pending — P2

**Location:** `app/agent.py:481`, `app/api.py` chat-memory recording.

After `List projects` completes, sending `thanks` in the same session causes another `list_projects` run and returns completed. Goal reconstruction reads prior human messages without checking whether their tasks completed. This can repeat private drafting or analyses after a harmless acknowledgement.

**Needed:** distinguish active goals from completed conversation history.

### 9. Phrase matching rejects legitimate model interpretation — P2

**Location:** `app/agent.py:496`, `app/agent.py:532`.

`Read the contract for project-001` receives an unsupported-task clarification locally. More significantly, when a controlled provider correctly chooses `inspect_agreement` for that task, the shared validator rejects it twice and returns `contract_error`. The controller's short list of phrases overrides a valid model interpretation.

This is a hidden-variant risk under PDF section 12; it is not a claim that ordinary identifier parsing is prohibited.

**Needed:** represent validated user intent beyond literal phrases, while retaining identifier provenance and authority checks.

### 10. Combined project listing and inspection is rejected — P2

**Location:** `app/agent.py:532`.

`List projects and inspect agreement for project-001` returns `contract_error` without executing any tool. Listing is allowed only when the requested-operation list is empty or exactly `['list']`. A legitimate compound request is therefore rejected.

**Needed:** permit each explicitly requested safe operation and track its completion separately, or state a supported single-operation constraint with an appropriate clarification.

### 11. Missing request details are mistaken for concrete domain input — P2

**Location:** `app/agent.py:666`.

`Analyze scope drift for project-001 and draft a change request` returns `completed` with an ambiguous analysis of the command itself. There is no client request. Removing known command terms leaves connective words, which are interpreted as sufficient concrete request content.

**Needed:** ask for actual request details before executing analysis. An ambiguous supplied client request and an entirely missing request are different conditions.

### 12. Inline-request grounding rejects a correctly extracted request — P2

**Location:** `app/agent.py:551`.

For `Analyze scope for project-001: add checkout`, a controlled provider selecting project-001 with `request_text='add checkout'` returns `contract_error`. The validator requires exact equality with the whole command, including task framing. This needlessly rejects normal structured extraction by live models.

**Needed:** parse and store the trusted request span once, then validate against that span rather than the full user command.

### 13. Authority recognition depends on wording and crosses text boundaries — P2

**Location:** `app/agent.py:516`, `app/agent.py:632`.

- `Do not charge; send the draft to the client` is not recognized as forbidden. Negation before `charge` incorrectly extends across the semicolon to `send`.
- `Notify the client with the proposal` is not recognized as forbidden. A correct model `block` decision is rejected by the shared validator and becomes `contract_error`.
- `Analyze project-001: the client says send the draft to the client` is recognized as a consequential user instruction even though the text introduces client speech for analysis.

No real messaging tool exists, so these probes did not send anything. The failure is incorrect boundary behavior and trust interpretation, affecting Arena categories B and F.

**Needed:** distinguish the user's authorized task from quoted/client data and interpret clause-specific negation and action intent.

### 14. Wrong-type numeric input is silently coerced — P2

**Location:** `app/models.py:8`, `app/models.py:190`.

`ListProjectsInput.model_validate({'max_results': True})` succeeds as `max_results=1`. Shared contracts forbid extra fields but do not enforce strict scalar types. PDF sections 9 and 11 require malformed/wrong-typed decisions to be detected; boolean-as-integer values are not detected here.

**Needed:** enforce strict types at model-decision/tool-input boundaries and retain bounded repair for violations.

### 15. Malformed provider envelopes bypass repair and lose reported usage — P2

**Location:** `app/agent.py:215`, `app/agent.py:750`.

A mocked HTTP 200 provider response containing `usage` but no `choices` raises `KeyError`; the exception carries no `provider_usage`. Only `ValueError` receives usage attachment and the bounded decision-repair path. Missing/empty/mis-typed envelope fields can instead become generic model failures.

**Needed:** validate the provider envelope, convert parsing failures to the typed contract-recovery path, and retain usage before parsing.

### 16. Response-size guard does not enforce its size ceiling — P2

**Location:** `app/arena.py:53`.

A controlled result with a 60,000-character event is changed to `response_too_large`, but the same events are copied into the replacement response. The emitted JSON is **60,498 bytes**, still above the 50,000-byte ceiling.

**Needed:** bound/compact events and other retained fields before serializing a size-failure response, then validate the final byte size.

### 17. Context is silently truncated and count limits disagree — P2

**Location:** `app/prompts.py:52`, `app/agent.py:481`, `app/agent.py:661`, `app/memory.py:58`.

Memory retention uses configurable `max_history_messages`, while provider context always takes six messages and goal reconstruction always scans twelve. Message/external content are sliced without an explicit omission signal. Combined-goal text is silently clipped at 10,000 characters, which can remove the newest clarification at the end.

These are code-inspection findings; an end-to-end long-history boundary probe was not run. PDF section 11 category E explicitly requires no silent truncation.

**Needed:** use consistent configurable history policy, preserve active-goal fields separately, and expose truncation or a budget-related stop when critical information cannot fit.

### 18. Absence of agreement evidence is presented as high-confidence drift — P2

**Location:** `app/tools.py:95`, `app/tools.py:110`.

`Please use a neutral background and build a custom mobile app.` becomes `scope_drift` with a `missing_evidence` finding. The shared `if findings` branch treats that missing evidence like an explicit exclusion and assigns high confidence. This overstates the evidence available from the sample agreement.

**Needed:** distinguish demonstrated exclusion/limit breach from unknown or conflicting work. Use clarification or ambiguous classification when evidence cannot establish the result.

### 19. Documented comparison runner fails from a clean shell — P1

**Location:** `evaluation/run_model_comparison.py:18`, README testing commands.

`python evaluation/run_model_comparison.py --help` fails with `ModuleNotFoundError: No module named 'app'` when the project root is not separately on PYTHONPATH. The new app import occurs before the later path setup. This breaks both documented URL and in-process invocation forms.

**Needed:** provide a module invocation or initialize imports correctly before importing app code, and verify the README command from a clean environment.

### 20. Current model-selection evidence and validity metric are incomplete — P1/P2

**Location:** `evaluation/gemini_comparison_results_retry.json`, `evaluation/run_model_comparison.py:181`, `README.md:196`.

- Both saved Gemini comparisons identify source revision `f5e0fb9d6dbdeb77b9b9cdfaf458c57c53142512`. Current hashes differ for agent, api, arena, config, memory, models, prompts and tools. The historical 9/10 results are useful evidence but cannot certify the current controller.
- The published `10/10 valid contracts` describes typed outer Arena responses, not necessarily valid model decisions. A model failure converted into a typed failure still counts as an outer-contract success.
- The new first-attempt validity calculation means only 'no decision_rejected at step 1'. A provider failure before any decision can therefore count as valid; deliberately injected invalid decisions can penalize the model. It also says nothing about invalid later decisions.
- README calls the default selected in one paragraph and provisional in another. Its rationale discusses reliability/cost/latency but does not clearly connect the chosen model's context capacity to the retained-context budget.

**Needed:** repair the runner; separately score actual model decisions, injected faults, repair and outer response validity; rerun both candidates on the same final source; update the comparison table and selection rationale. Keep historical evidence clearly labeled.

### 21. Final submission record and release artifacts are unfinished — P1

**Location:** `SUBMISSION.md`, `release/submission.draft.json`, release output.

The submission record has bracketed identity, repository, commit, host/model and access fields. No final `i230769.zip` or `i230769_submission.pdf` exists in `dist/`. There is no clean-extraction rehearsal evidence or verified current deployment/source match.

Instructor access, any required custom-domain approval, university-account submission and Classroom's Turned in state cannot be established from local code. They remain verification items, not asserted failures.

**Needed:** complete real metadata, produce the required two artifacts from the final source, verify links and extracted startup, and confirm external submission/access requirements.

### 22. Release helper does not guarantee acceptable metadata or a correct PDF — P2

**Location:** `release/prepare_submission.py:33`, `:76`, `:86`, `:128`.

- Metadata validation accepts `https://localhost` as a public interface URL. This was reproduced with synthetic metadata. Placeholder detection checks only `PENDING_` and `.invalid`, so bracketed fields and `.example` hosts can also evade that limited check when other validations permit them. SUBMISSION.md's claim that private URLs are rejected is inaccurate.
- PDF link-row mapping searches for URL substrings and keeps the last matching row. For an interface URL that is the base of all endpoint URLs, its annotation lands on the API documentation row. Reproduced using the summary/row mapping.
- Text is cut at 150 characters without wrapping. Long URLs and metadata can be clipped or run beyond the page margin; final rendering verification is absent.
- Helvetica strings are converted through cp1252 but the PDF stream is encoded as UTF-8. For `René`, the emitted bytes include `c3 a9`, rather than the font's expected single-byte encoding. Other unsupported name characters become `?`.
- ZIP exclusion blocks only `.env` and `.env.local` by name within included directories. Other real-value files such as `.env.production` can be packaged if placed there. This is a packaging rule gap, not evidence that the current archive leaked a secret; no final archive exists, and the root `.env` is untracked and outside the allowlist.
- The summary directly indexes fields such as `hosting_provider` that are not in REQUIRED, so a metadata file passing required-field validation is not guaranteed to be renderable. This last point is based on code inspection.

**Needed:** validate exact field/public-URL requirements, bind link annotations to explicit labels, use a wrapping Unicode-capable PDF generator, render and inspect the final PDF, and broaden archive secret/config exclusions with an archive-content check.

## Recommended completion order

1. Correct completion/evidence validation, scope classification and active-goal handling. Add regression coverage for the concrete failures above.
2. Correct input/output budgeting, strict typing, malformed-envelope repair and response compaction.
3. Repair evaluation imports and metrics; rerun both live candidates on the final source without either fallback path.
4. Deploy that source, verify public UI/health/manifest/Arena POST, and capture current multi-turn evidence.
5. Complete metadata, repair the release helper, generate and inspect the two attachments, and rehearse installation from the extracted ZIP.

Do not interpret the passing 80-test suite, local 10-case run, historical public results, or visual polish as proof that the remaining assignment requirements are satisfied.
