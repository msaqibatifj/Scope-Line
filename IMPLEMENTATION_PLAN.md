ScopeLine implementation plan
=============================

Status: planned; application fixes have not been implemented by this document.
Scope: root ScopeLine only. PacketPilot/student-agent is excluded.
Basis: AUDIT.md findings F1-F10, verified against Agentic.pdf in the preceding audit. The recorded baseline is 63 unit tests and 10 local public cases passing; this is not live-provider evidence.

Objective: eliminate the reproduced semantic failures, make failures observable and evaluation trustworthy, then produce a verifiable deployment and submission. Preserve the bounded single-agent architecture, four safe domain tools, isolated sandbox commits, session isolation and required Arena contract. No new orchestration framework or database is needed.

Execution order
---------------

Stage A: regression fixtures and validated goal/context contracts (steps 1-4).
Stage B: completion, authority and domain correctness (steps 5-9).
Stage C: trace, metrics, evaluation and interface fixes (steps 10-14).
Stage D: live evidence, deployment and submission (steps 15-18).

Dependencies: 1 -> 2 -> 3 -> 4 -> 5 -> 6. Steps 7-9 depend on the goal/provenance contracts from steps 2-3. Steps 10-11 precede metrics scoring in step 12. Steps 10 and 13 precede the final browser check. Step 14 gates step 15; step 15 gates production model selection and steps 16-18. This ordering is for implementation batches; it does not authorize deployment or external account actions merely by creating this plan.

Stage A: establish the contracts and regression baseline
-------------------------------------------------------

**Step 1. Capture each confirmed failure as a focused regression.**
Findings: F1-F9.
Files: tests/test_decision_contracts.py, tests/test_agent.py, tests/test_tools.py, tests/test_providers.py; add tests/test_evaluation.py and tests/test_run_progress.py where useful.
Actions:
- Record working-tree status before implementation and preserve unrelated modifications and deleted evidence files. Do not assume HEAD is the audited version or restore old evidence automatically.
- Convert the audit probes into assertions against behavior: wrong-tool completion, missing draft, invented project, paraphrased refusal, excessive quantities, old chat intent, oversized accumulated goal, interrupted trace, usage lost during repair, and evaluation false positives/negatives.
- Use local fixtures and mocked provider transport for these tests. Keep a separate live experiment stage.
- Add neighboring variants, not only the exact audit strings: different projects, explicit corrections, alternative wording and boundary values.
Done: each regression demonstrably fails for its intended reason on the pre-fix implementation; the existing suite remains a documented baseline. Regressions are then fixed in their owning steps.

**Step 2. Define a typed active goal and evidence references.**
Findings: F1, F2, F3, F5.
Files: app/models.py; new app/policy.py for reusable controller checks if that keeps app/agent.py smaller.
Actions:
- Define GoalIntent with requested operations, selected project/request, explicit draft intent, unresolved fields, authority category and a bounded goal revision identifier.
- Define EvidenceRef with source kind, source/turn identifier and exact text span or immutable record identifier. Distinguish trusted user instructions from external text, stored records and tool observations.
- Define ConversationState containing active_goal and pending_clarification; do not store concatenated history as the authoritative goal.
- Define completion predicates and action preconditions separately from model reasons. Model text must not redefine success after executing the wrong tool.
- Keep model-selected next actions; avoid imposing a universal inspect -> analyze -> draft sequence. Analysis already reads the agreement and does not require inspection first.
Done: contracts reject structurally inconsistent goals, unknown sources and invalid evidence references. Requested operations and completion rules are explicit enough to test without live inference.

**Step 3. Ground intent and selections before executing any tool.**
Findings: F2, supports F1/F3/F5.
Files: app/agent.py, app/prompts.py, app/models.py, app/policy.py.
Actions:
- Let the first bounded decision propose intent and an action together, or use a bounded intent-resolution decision. Count every provider call against the existing run limits; do not add an unmetered planning call.
- Validate proposed selections against current trusted input or a previously confirmed active goal before tools. Explicit latest selections supersede older selections.
- Resolve explicit IDs deterministically. Permit an unambiguous project name only against known records; ask when multiple records match. Do not silently select the first project from a listing.
- Accept a stored request/project relationship only when established by application-owned records; reject mismatched or conflicting explicit selections.
- Ground inline request text in the actual user-supplied or explicitly designated external source. External text may supply task data but cannot authorize sending, charging or goal changes.
- A matching quote alone does not prove correct semantic intent. Retain bounded model interpretation for paraphrases, validate supported operations/provenance, and clarify ambiguous or conflicting intent rather than guessing.
Done: the invented-project probe asks for clarification or reaches a typed repair failure without executing analysis. Explicit valid selections and existing shorthand clarifications still work. A model cannot replace a validated goal during finish.

**Step 4. Replace historical concatenation with clarification-aware memory.**
Finding: F5.
Files: app/memory.py, app/api.py, app/agent.py, app/config.py, app/prompts.py, .env.example.
Actions:
- Persist typed active-goal and pending-question state alongside bounded HumanMessage/AIMessage history and the sandbox.
- Treat a reply to a specific pending field as a clarification only when compatible with that question. A new explicit operation replaces the old active goal; ambiguous replies produce a focused question.
- Clear stale block state and project/request selections when appropriate. Invalidate incompatible request selection when the project changes.
- Add configurable history-turn, history-character and prompt-history limits; validate their ranges and apply one consistent policy at storage and prompt assembly.
- Keep current accepted input separate from bounded prior context. Preserve compact goal facts during eviction; report an explicit context-budget outcome if critical context cannot fit. Avoid blind slicing of identifiers or the active request.
- Reset, TTL expiry and capacity eviction must clear both transcript and typed goal state. Preserve session isolation and one-worker deployment.
Done: project-001 -> project-002 uses project-002; blocked email request -> list projects succeeds; request -> clarification -> ID-only reply retains the intended operation; two 7,000-character turns never cause internal_error. Bounds remain enforced over many turns and reset removes all goal state.

Stage B: enforce domain and execution correctness
------------------------------------------------

**Step 5. Enforce goal-specific action and completion predicates.**
Finding: F1.
Files: app/policy.py, app/agent.py, app/models.py.
Completion rules:

| Goal | Required evidence |
| --- | --- |
| List | Successful list_projects result, including a legitimate empty list. |
| Inspect | Successful inspect_agreement for the confirmed project. |
| Analyze | Successful analysis of the confirmed project and selected request/source revision. |
| Draft | Explicit draft request plus confirmed drift analysis and matching private draft. |
| Draft with within_scope/ambiguous result | Explain why a drift draft is unsupported; complete the assessment without fabricating a draft. |
| Multiple requested operations | Evidence for every supported requested operation, or an explicit partial/budget/clarification result. |

Actions:
- Track successful operations with input/evidence identity, rather than treating any projects or analysis payload as completion.
- Require draft authorization before draft execution, not only before finish. Prevent unrelated extra tools after a goal is complete.
- Render final output from the relevant collected evidence, not automatically only the last observation.
- Preserve bounded repair and typed contract_error when the model repeats an invalid action or premature finish.
Done: wrong-tool finish, skipped-draft finish, unrelated-project completion and unsolicited drafting cannot return successful completion. Ordinary list/inspect/analyze/draft paths still fit the default six-step budget, including the supported fault scenarios.

**Step 6. Replace phrase-gated refusals with a typed authority policy.**
Finding: F3.
Files: app/policy.py, app/models.py, app/agent.py, app/prompts.py.
Actions:
- Represent authority outcomes such as review_only, external_action_requested and unclear, backed by the current trusted request.
- Remove the requirement that a block decision match one exact forbidden substring. Use the validated intent and evidence to distinguish a consequential request from quoted client content or negation.
- Keep the actual tool allowlist as the hard boundary: no send, billing, signing or external agreement mutation tools.
- Normalize boundary stop codes; render a clear explanation of permitted private analysis/drafting. Clarify uncertainty instead of inventing authorization.
- Retain local-scripted as a conservative test baseline; do not claim its finite rules establish live semantic understanding.
Done: dispatch/email/invoice paraphrases receive a valid boundary response; 'do not email the client; prepare a private draft' stays permissible; unsafe language inside untrusted data does not become user authority. Existing external-context tests still pass.

**Step 7. Represent agreement constraints as typed data.**
Finding: F4.
Files: app/models.py, app/sandbox.py, data/sample_data.json.
Actions:
- Add optional structured limits appropriate to each project: deliverable quantity, deliverable kind, per-item duration, revision scope/allowance and explicit exclusions.
- Encode the existing twenty-photo and four-episode/45-minute constraints without changing their meaning. Model per-episode revision allowances accurately rather than treating every revision as a fungible project-wide count.
- Validate units, positive limits and consistency at fixture load. Preserve human-readable agreement text and an evidence reference for each limit.
- Unknown limits remain unknown; do not invent missing agreement terms.
Done: all fixtures load under typed validation, invalid units/counts are rejected, and structured values agree with the supplied agreement text.

**Step 8. Extract bounded request facts and compare constraints.**
Finding: F4.
Files: app/tools.py, app/models.py; optionally new app/scope_analysis.py.
Actions:
- Extract the quantities, units, durations, requested work and negation needed for the supported domain. Support ordinary written numbers used by the tests as well as numeric digits.
- Require source evidence for extracted values. Ambiguous phrases such as additional quantities, uncertain units or conflicting sources must not produce within_scope without justification.
- Compare facts with the typed agreement limits before deciding within_scope. Known over-limit work is scope_drift; unresolved material constraints are ambiguous.
- Replace arbitrary substring matching with normalized phrase/token boundaries. Preserve useful conservative handling of mixed scope, exclusions and negation.
- Keep classification independent of provider branding: every provider reaches the same validated tool semantics.
Done: 100 vs 20 photos and ten 90-minute vs four 45-minute episodes never return within_scope; exact-limit supported work can pass; 'brush' does not match 'rush'; unsupported interpretations safely clarify rather than guess.

**Step 9. Strengthen semantic tool-result validation.**
Findings: F1, F2, F4; PDF validation requirements.
Files: app/models.py, app/tools.py, app/agent.py, app/sandbox.py.
Actions:
- Require an error on failed tool results and prohibit contradictory success/error payloads.
- Validate operation-specific results: list evidence for listing, selected agreement for inspection, grounded matching analysis for classification, and authorized matching draft for drafting.
- Require analysis identity, classification/findings and request/project provenance to agree; a syntactically valid unrelated result must not be committed.
- Perform semantic result checks before committing the isolated sandbox. Keep operation-ID replay protection and deadline checks.
Done: malformed or mismatched tool results follow bounded recovery/typed failure with no state commit; legitimate empty lists remain valid; retries do not duplicate drafts.

Stage C: make outcomes observable and evaluation reliable
--------------------------------------------------------

**Step 10. Keep run progress outside cancellable model execution.**
Finding: F6.
Files: app/models.py, app/arena.py, app/agent.py.
Actions:
- Add an internal RunProgress structure owned by execute and passed into run_agent: decision steps, actual provider attempts, tool traces, bounded observations, events and accrued usage.
- Update progress before/after each operation, distinguishing attempted, validated and committed work.
- Construct timeout, contract, dependency and response-limit outcomes from a consistent snapshot. Preserve metrics and committed-operation IDs even if optional observation details must be omitted.
- Keep cancellation effective and preserve the existing rule that late tool results cannot commit. A timeout after a committed draft must report that partial side effect.
Done: a timeout after one tool retains that tool, steps and known usage. A timeout before a tool finishes cannot commit late state. The endpoint stays within its deadline tolerance and the response-size limit.

**Step 11. Account for every provider response before parsing decisions.**
Finding: F7.
Files: app/agent.py, app/providers.py, app/models.py, app/api.py.
Actions:
- Separate provider transport/usage extraction from decision parsing, or carry usage in a typed parse failure; account for usage as soon as the response exposes it.
- Count actual provider attempts separately from local decisions. Track usage from primary, fallback and repair responses without double counting.
- Distinguish known zero, known amount and unknown cost. When coverage is partial, expose known subtotal plus missing-coverage counts instead of presenting it as a complete total.
- Record accrued known usage on failed/timed-out runs. Keep free-tier declarations explicit and do not describe the process-local estimate as a provider billing cap.
Done: the repair probe totals 150 input tokens, 30 output tokens and $0.015; null remains unknown; explicit zero remains zero; fallback/timeout paths preserve accrued usage. Tests use synthetic provider responses only.

**Step 12. Correct evaluation contracts and scoring.**
Finding: F8.
Files: evaluation/run_public_tests.py, evaluation/run_model_comparison.py, evaluation/public_cases.json, tests/test_evaluation.py.
Actions:
- Have the application own stable stop_reason codes; preserve readable model reasoning separately. Update project-owned expected cases to these codes. Do not edit instructor-owned cases to make failures disappear.
- Validate outer responses with the actual typed contract, including strict checks for important primitive types; reject boolean step counts and null required fields.
- Report raw decision validity, repair success, semantic rejection, correct actions and end-to-end completion separately. Separate injected faults from naturally invalid provider decisions.
- Score ordered/required actions, target project/request and completion evidence; mere presence of a tool name is not sufficient.
- Exclude provider fallback success from the original candidate's task-success count. Preserve latency/failure rows and unknown token/cost coverage.
- Store run configuration, source hashes/dirty state, cases, selected model, actual provider and raw bounded evidence. Separate public default-route checks from candidate-specific chat evaluation.
Done: valid wording variations pass semantic checks; wrong-tool/wrong-target completion fails; invalid contracts fail; fallback cannot inflate candidate success; missing cost cannot aggregate to a misleading zero.

**Step 13. Return and display bounded validated observations.**
Finding: F9.
Files: app/models.py, app/agent.py, app/arena.py, app/static/app.js, app/static/index.html, app/static/style.css.
Actions:
- Add an additive observations response field, retaining every required Arena field. Include operation/step, safe input identifiers and bounded validated result summaries.
- Preserve project/request identity, classification, evidence, draft identity and consequential partial outcomes. Strip credentials, raw provider headers and irrelevant payloads.
- Enforce a response serialization budget; mark omissions/truncation explicitly and never erase status/stop reason/metrics to make room for optional data.
- Show observations separately from lifecycle events and trace. Use text-safe rendering for all user/tool text.
Done: the UI displays agreement evidence, analysis findings and a private draft from actual results; interrupted runs show completed observations; controls and observations work in a browser, with no script injection or console errors. Run the available browser verification workflow when implementing this step.

**Step 14. Close local integration and documentation gaps.**
Findings: F1-F9, supports F10.
Files: tests/, evaluation/, README.md, arena_manifest.json, .env.example.
Actions:
- Run the complete unit suite once the changes are integrated, then the in-process API/public-case checks. Add meaningful tests for contract-invalid outputs, actual tool exceptions, timeouts, conflicts, paraphrases and multi-turn state transitions.
- Verify the default six-step limit still accommodates intended workflows and one-shot injected faults; repeated invalid decisions stop within repair limits.
- Recheck session isolation, reset/TTL, idempotency and no late sandbox commits after the controller changes.
- Add the missing architecture diagram. Document new history/context settings, stable stop codes, limits, observation fields and limitations. Keep manifest claims consistent with configured behavior.
Done: all confirmed audit regressions and existing tests pass; no runtime/provider access is needed for the deterministic suite; API/UI checks show the complete intended flow. No live-model reliability claim is inferred from these results.

Stage D: generate evidence and complete release
-----------------------------------------------

**Step 15. Run a fresh two-candidate model-selection experiment.**
Finding: F10, depends on F7/F8 fixes.
Files: evaluation/run_model_comparison.py, new current result JSON/Markdown, README.md.
Actions:
- Verify the configured candidate IDs, provider support and readiness when execution begins. Do not assume a stale configured ID is currently available.
- Use the same approximately ten representative inputs for both actual models, covering normal tasks, clarification, authority, injection, repair, tool failure and budget exhaustion. Add a separate held-out paraphrase/quantity set without silently replacing failing public cases.
- Disable both provider fallback and local fallback during comparison. Pin the tested source/configuration; avoid benchmark changes mid-run.
- Use pacing consistent with provider quotas and retain all rate-limit/failure rows. Record any rerun as a separate attempt with its reason.
- Record task success, model-decision validity, actions, latency, token coverage and known/estimated cost. Write partial evidence after each case.
- Select a default based on evidence and explain its reliability/latency/context/cost tradeoffs. Repair and rerun relevant evidence when a material code change is made.
Done: two genuine candidate result sets and a linked comparison table exist and are reproducible. No unsupported completion or authority failures remain in the release suite. The existing 9/10 success target is a project gate, not a grade threshold imposed by the PDF. If it is missed, mark the gate unmet rather than relabeling local fallback as model success.
Prerequisites: usable provider access and an established cost policy; do not expose credentials in evidence.

**Step 16. Verify the release source and public deployment.**
Finding: F10.
Files: README.md, Dockerfile, render.yaml, run.py, requirements.txt, evaluation/deployment_verification.json (new).
Actions:
- Test installation from clean project contents, including dependency pins and environment-variable setup, and test the documented start command.
- Prepare a reviewed final source revision and ensure the deployed application uses that revision, selected model and host secrets. Keep one worker for in-memory sessions and bind to the host PORT on 0.0.0.0.
- Verify public HTTPS interface, GET /health, GET /arena/manifest, /docs and an actual POST /arena/run from outside the local process.
- Exercise live chat clarification across two turns, reset, model selection, traces/observations, and a restart/cold-start scenario. Save timestamps, target URLs, revision and bounded responses without secrets.
Done: the working public application and required routes are reachable without evaluator login or an evaluator-supplied API key. Current evidence identifies the actual deployed source/model. Hosting limitations are documented.
Prerequisites: deployment destination/access. Existing assignment submission/evaluation-window restrictions must be checked before changing an already submitted deployment.

**Step 17. Complete metadata and harden artifact generation.**
Finding: F10.
Files: SUBMISSION.md, release/submission.example.json, release/prepare_submission.py.
Actions:
- Obtain missing identity, section, university email, repository, hosting and instructor-access facts. Do not infer roll number from the folder name or invent approval/access status.
- Require every PDF section 19.3 field or its permitted explicit explanation. Validate roll-number format, full commit hash and usable public URL forms; validate required optional-in-code fields before rendering.
- Define source-versus-generated-metadata handling so a commit hash can identify source accurately without a self-referential generated-file cycle. Verify the packaged application source matches the recorded revision; do not merely copy an arbitrary dirty tree while claiming HEAD.
- Fix PDF layout/link placement and wrap long values rather than silently truncating them. Use a renderer and reopen the resulting PDF to check every page and clickable destination.
- Keep ZIP allowlisting and strengthen recursive exclusions for secrets, caches and environments; exclude PacketPilot and reference PDFs. Require expected tests/data/assets/results to be present.
Done: SUBMISSION.md and the separate PDF contain matching current fields/URLs/revision, with no placeholders or clipped required content. The archive contains one correctly named top-level project folder and no prohibited material.

**Step 18. Perform the clean submission rehearsal and close the audit.**
Finding: F10 and final release verification.
Files: final roll-number ZIP/PDF, evaluation/release_verification.json (new), AUDIT.md status addendum.
Actions:
- Extract the ZIP into a separate temporary directory and follow the README setup/test instructions using only extracted contents.
- Verify required assets, sample data, evaluation evidence and startup entry point; compare source hashes with the intended revision.
- Reopen the submission PDF, check all pages/links, and check the deployment still matches the evidence.
- Record each audit finding as fixed with a test/evidence reference, or explicitly unresolved. Do not overwrite the original observed failures or claim external completion without evidence.
- Record instructor repository access and course/domain approval if required. Uploading, inviting others or clicking Classroom Turn in are separate external actions and require the applicable user instruction; preparing this plan does not perform them.
Done: clean extraction passes, both required artifacts are valid, matching source/deployment/evidence is established, and the remaining external submission status is truthful. Official submission is complete only when the user confirms or an authorized check verifies Turned in.

Finding-to-step checklist
-------------------------

| Finding | Primary implementation steps | Acceptance evidence |
| --- | --- | --- |
| F1: premature/wrong completion | 2, 5, 9 | Wrong-tool, skipped-draft, unsolicited-draft and multi-operation tests |
| F2: invented selection | 2, 3, 9 | Missing/conflicting/changed IDs and source provenance tests |
| F3: literal refusal gate | 3, 6 | Paraphrase, negation and quoted-untrusted-text tests |
| F4: classifier constraints | 7, 8, 9 | Quantity/duration boundaries and word-boundary tests |
| F5: memory and context | 2, 4 | Clarification, goal switch, long-turn, eviction and reset tests |
| F6: lost timeout progress | 10 | Partial trace/side-effect tests and no-late-commit test |
| F7: lost usage and unknown cost | 10, 11, 12 | Repair/fallback accounting and partial-coverage tests |
| F8: inaccurate evaluation | 12 | Scorer regression fixtures and typed contract checks |
| F9: missing observations | 10, 13 | API observation checks and browser verification |
| F10: incomplete release evidence | 14-18 | Current comparison, public verification, matching ZIP/PDF and extraction rehearsal |

Suggested implementation batches
---------------------------------

1. Goal/provenance and conversation contracts (steps 1-4).
2. Controller completion/authority enforcement (steps 5-6).
3. Typed domain constraints and tool-result semantics (steps 7-9).
4. Progress, usage, evaluation and observation UI (steps 10-14).
5. Live comparison, deployment and submission evidence (steps 15-18).

Each batch should finish with its focused regressions passing and a short record of what was verified. Run broader checks at integration boundaries and after material failures; avoid repeating expensive live benchmarks without a changed hypothesis or fix.
