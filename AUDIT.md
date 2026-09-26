ScopeLine audit against Agentic.pdf
=================================

Date: 2026-09-26. Verdict: substantial implementation, but not submission-ready.

Scope: the root ScopeLine application, its tests, fixtures, interface, evaluation scripts, deployment configuration and release tooling. PacketPilot in student-agent/ is excluded at the user's request. No application code was changed. This audit covers the working tree, which contains pre-existing modifications and deletions; HEAD is f5e0fb9d6dbdeb77b9b9cdfaf458c57c53142512 and does not describe all audited source changes.

All 15 pages of Agentic.pdf were text-extracted and read. Requirements below refer to that PDF, rather than treating the local requirements summary or earlier compatibility audit as authoritative. Source SHA-256: 214e4f7c41b24e7c3c5f737c6a8e4c188b8e736f301496c18998db6cea0e9997.

Verification
------------

- Existing ScopeLine unittest suite: 63/63 passed, Python 3.12.3.
- The ten public cases were replayed through FastAPI TestClient with local-scripted selected: 10/10 passed, including the expected stop reasons. This is local baseline evidence, not live-model evidence.
- Additional in-process probes reproduced the defects below. Controller probes inject plausible model decisions at the decision-provider boundary; they establish what the controller accepts, not how frequently a real model makes that decision.
- Real provider requests, paid inference, public deployment checks and browser rendering were not performed. No populated public deployment URL is provided in SUBMISSION.md.
- Installed FastAPI, Uvicorn, Pydantic, pydantic-settings, langchain-core and httpx versions match the root requirements pins. A clean dependency installation and extracted-ZIP rehearsal were not performed.

Priority findings
-----------------

F1 [P1] Completion evidence is not tied to the requested operation.
Source: app/agent.py:434-457, especially 449-456; execution at 337-338.
PDF: sections 3-4 (pages 2-3), section 9 (page 6), Arena categories A/C (page 7).
Reproductions: (a) For 'Analyze request-001 for project-001', supply decisions list_projects -> finish. The API returns completed with a project list, despite never analyzing. (b) For 'Analyze request-001 for project-001 and draft a change request', supply analyze_scope_drift -> finish. It returns completed without creating the requested draft even though the analysis confirms drift.
Cause: any successful projects payload is sufficient to finish; any analysis on the tool-selected project is sufficient regardless of the requested draft. A prompt asking the model to finish only after all requested work is insufficient.
Fix: maintain validated requested operations and their completion predicates. Require corresponding project/request evidence and a draft when drift is confirmed and a draft was requested. Reject or repair incomplete completion claims.

F2 [P1] A model can invent the project selection and still complete successfully.
Source: app/agent.py:318-319, 434-443, 345-348.
PDF: section 9 (page 6), ambiguity category A (page 7).
Reproduction: request 'Analyze whether checkout is in scope', without any project. Supply analyze_scope_drift(project_id='project-001', request_text='Add checkout') -> finish. It returns completed with a drift finding rather than asking which project.
Cause: identifier syntax and existence are checked, but selection is not linked to user-provided or previously confirmed facts. resolved_project_id is assigned from the model's tool arguments after execution, so the later equality check cannot establish user authorization.
Fix: resolve and validate user-confirmed identifiers independently; require clarification where missing or conflicting. Apply the same provenance checks to request IDs and inline request text.

F3 [P1] Literal phrase validation rejects legitimate autonomy refusals.
Source: app/agent.py:436-437 and 472-478.
PDF: autonomy category F and anti-hardcoding section 12 (page 7).
Reproduction: request 'Dispatch the proposal to Northstar Coffee by email'. A model correctly chooses block and explains it cannot dispatch messages. The application rejects the decision twice and returns contract_error because this wording is absent from the forbidden phrase list.
Impact: this affects the shared controller, including live providers, not just local-scripted. It does not enable actual email sending: no sending tool exists. The defect is incorrect boundary handling and poor generalization to hidden variants.
Fix: preserve the tool capability boundary and validate typed authority intent with evidence from the current trusted request; do not require an exact substring before accepting a valid refusal. Test paraphrases, negation and quoted client text.

F4 [P1] The shared classifier approves quantities and durations beyond the agreement.
Source: app/tools.py:45-110; data/sample_data.json agreement limits; substring matching at app/tools.py:201-208.
PDF: meaningful useful task and completion (pages 2-3), semantic validation (page 6).
Reproductions: project-003's agreement includes twenty photographs, yet 'Deliver 100 product photographs on a neutral background' returns within_scope. Project-002 covers four episodes up to 45 minutes each, yet 'Please provide mastering for ten episodes of 90 minutes each' also returns within_scope.
Cause: a matching positive keyword is treated as adequate evidence without checking quantities, durations or other restrictions. All providers use this tool; selecting a stronger model does not replace the classifier. A smaller boundary issue also reproduces: 'brush dust off the product photos' matches the excluded word 'rush' inside 'brush'.
Fix: represent and compare agreement constraints explicitly. Return ambiguous when a material constraint cannot be established; use token/phrase boundaries instead of arbitrary substring matching.

F5 [P2] Chat history can override a new goal, and valid long turns can fail internally.
Source: app/agent.py:428-431, 481-483, 236-239; app/models.py AgentRunState.goal; app/memory.py:53-58; app/prompts.py:49-51.
PDF: multi-turn context section 7.1 (page 5), bounded context (pages 3-5).
Local-baseline reproductions: inspect project-001, then explicitly inspect project-002 in the same chat; the second answer still describes project-001. 'Email the client', then 'List projects', remains blocked on the second turn. The baseline concatenates old user requests before the latest one and selects the first ID or any historical unsafe phrase.
Shared-path reproduction: two consecutive valid 7,000-character chat tasks cause the second run to return failed/internal_error because the concatenated goal exceeds its 12,000-character model limit. The request schema accepts each turn, while retained history allows up to 24,000 characters.
Fix: store active intent and pending clarification explicitly, distinguish new goals from clarification replies, let explicit current selections supersede old ones, and bound/summarize state before schema construction. Make history limits configurable as required on PDF page 3. The stored six-turn history currently becomes only three turns in the prompt.

F6 [P2] Timeout handling discards completed actions and accrued usage.
Source: app/arena.py:18-26.
PDF: observability/cost controls (page 3), budgets and dependency failure (page 7).
Reproduction: mock a successful first decision that lists projects and reports 100 input/20 output tokens plus cost; delay the second decision beyond a 0.15-second configured deadline. The response correctly says budget_exceeded but reports steps=0, model_calls=0, tool_calls=[], events=[] and null usage, despite completed work.
Fix: keep run progress available to the timeout boundary and produce a partial typed response with the actual trace and accrued metrics. This also matters for a chat draft that has already been committed before a later model call times out.

F7 [P2] Invalid model outputs lose usage; evaluation can report unknown cost as zero.
Source: app/agent.py:195-200 and 263-279; evaluation/run_model_comparison.py:75-77.
PDF: cost controls (page 3), model-selection evidence (page 4).
Reproduction: simulated provider response one contains an invalid decision and reports 100 input tokens, 20 output tokens and $0.010; repaired response two reports 50, 10 and $0.005. Returned totals are only 50, 10 and $0.005 instead of 150, 30 and $0.015.
Cause: decision parsing raises before usage is returned. Separately, the comparison aggregate converts every missing cost to zero via 'or 0'.
Fix: account for provider usage before parsing decisions, retain it through failures, distinguish unavailable cost from known zero, and disclose coverage of any estimates. No actual paid calls were made in the probe.

F8 [P2] Evaluation assertions do not measure the required live-model reliability accurately.
Source: evaluation/run_public_tests.py:15-16; evaluation/run_model_comparison.py:56-59, 69-77.
PDF: model experiment (page 4), evaluation evidence (page 10).
Reproduction: a completed listing with the correct tool/evidence and stop reason 'The requested list was returned.' fails the public runner solely because it differs from local-scripted's literal reason. The comparison runner's contract_is_valid accepts a response where all fields except steps are null and steps=True.
Cause: exact model-written stop reasons are compared in public tests, while the comparison's 'valid_contracts' checks only key presence and an integer instance. It does not quantify typed model-decision validity or repair rates.
Fix: normalize machine stop-reason codes or score terminal behavior and evidence; validate outer responses with ArenaResponse and separately record raw decision validity, repaired decisions, action correctness and final outcome. Keep model failures visible and exclude fallback success from candidate scores, as the newer comparison runner already does.

F9 [P2] The interface shows event metadata rather than actual tool observations.
Source: app/agent.py:342-350; app/static/app.js:91-92.
PDF: demonstration interface requirements (pages 3 and 9), observability (page 3).
Reproduction: listing projects emits only {'step':1,'event':'tool_observation','tool':'list_projects','ok':true}. Actual ToolResult records remain in private run state. The UI's observations panel renders events, so agreement, analysis and draft observations cannot be inspected there.
Fix: return bounded, redacted validated observations in a dedicated response field or event payload and display them. Retain all material findings and intermediate results needed to reconstruct the run, within the response-size budget.

F10 [P1 release blocker] Required experiment, deployment and submission evidence is incomplete in this checkout.
Source: README.md:163-192; SUBMISSION.md:2-26; evaluation/ directory; git status.
PDF: model experiment (page 4), deliverables/deployment (page 10), submission (pages 13-15).
Observed: README reports historical 4/10 and 2/10 Gemini results but links to missing evaluation/gemini_comparison.md. evaluation/gemini_comparison_results.json is also absent. Historical model_comparison_results.json, model_comparison_rate_limited_results.json and public_results.json are deleted in the working tree. Existing prose is not enough to independently verify these claims, and it predates some current regression fixes. SUBMISSION.md still has placeholder i221234 and blank identification, repository, commit, interface, endpoint and access fields. No final roll-number ZIP or submission PDF was present in the root listing or dist output.
Fix: after fixing controller defects, produce fresh evidence from two actual candidates on the same approximately ten inputs, including raw decisions/repairs, task/action validity, latency, token/cost coverage, source version and disabled fallback. Finalize the deployment and test public HTTPS health, manifest and POST Arena routes. Fill matching submission metadata, record the final commit, build the ZIP/PDF, then verify a clean extracted setup. Required external facts such as instructor access and Classroom Turned in cannot be inferred locally.
Note: the README's 9/10 release target is a project-defined target, not a threshold in Agentic.pdf. No numeric grade or hidden-Arena score can be justified from the passing local tests.

Requirement comparison
----------------------

| PDF requirement | Result in ScopeLine |
| --- | --- |
| Narrow operational goal and nine-part design canvas, pp. 2-4 | Present in README and manifest. |
| At least three meaningful tools, p. 3 | Present: four domain tools. |
| Model influences execution and tool results feed back, pp. 2-3 | Implemented live-provider decision loop. Successful current live operation remains unverified; deterministic tests cannot satisfy this requirement alone. |
| Explicit typed run state and stopping rules, pp. 3, 5-7 | Present, but completion/provenance defects F1-F2 and trace-loss F6 remain. |
| Dynamic prompt and distinct trust layers, pp. 4-5 | Present. Stronger adversarial live testing is still needed; local external-content tests do not establish live injection resistance. |
| Conversation continuity, reset and bounded history, pp. 3, 5 | Basic clarification/reset tests pass; F5 shows changed-goal and length limitations. History ceilings are hardcoded rather than configurable. |
| Schema, semantic validation, bounded recovery, pp. 5-7 | Pydantic inputs/decisions, one decision repair and up to two tool retries exist. Semantic enforcement is incomplete. |
| Non-destructive autonomy, pp. 6-7 | Strong capability restriction: only read/classify/private-draft tools; no real sending, billing or agreement mutation. Refusal generalization fails in F3. |
| Shared FastAPI endpoints and example contract, pp. 8-10 | Present and locally exercised. Fault string shorthand and required response fields supported. |
| Chat, model selector, status, trace, observations and reset, pp. 3, 9 | UI code contains controls; actual observation display is incomplete (F9). Browser behavior not visually verified. |
| Configurable cost/execution controls and provider metrics, pp. 3-4 | Step/retry/timeout/output-token and run admission controls present. History configuration and accounting need work (F5-F7). |
| Two-model experiment and selection rationale, p. 4 | Comparison harness and narrative exist; current evidence is missing/incomplete (F8-F10). |
| Public deployment, reproducibility, evaluation evidence, p. 10 | Docker/Render files, version pins and setup instructions present; public URL verification and completed artifacts absent from supplied evidence. |
| README architecture/folder diagrams, p. 10 | Folder tree and numbered loop description present; an explicit architecture diagram is missing. |
| Own-domain approval, p. 9 | ScopeLine is a proposed narrow domain; confirm instructor approval if required by the course. No approval evidence was found locally. |
| Final ZIP, clickable summary PDF, matching commit/URLs, private repo access, pp. 13-15 | Not complete in the workspace (F10). |

What is already solid
---------------------

The root implementation is a meaningful improvement over a one-call wrapper: a model can select actions, receive observations, repair a decision and stop; tool inputs are bounded; unknown tools cannot execute; request/project associations are checked by the tools; draft creation requires stored drift evidence; operation IDs prevent duplicate writes for the same operation; tentative tool work is isolated and committed only after validation and deadline checks; sessions have bounded storage and TTL cleanup; fallback decisions are traced and bounded. The 63 tests verify many of these mechanisms.

Recommended repair order and completion checks
---------------------------------------------

1. Repair F1-F3. Done when wrong tools, invented IDs, skipped drafts and paraphrased refusals are covered by provider-boundary regression probes, with typed safe results.
2. Repair F4-F5. Done when quantity/duration violations cannot be marked within_scope, project changes take effect, new goals clear old intent, and valid long turns cannot become internal errors.
3. Repair F6-F9. Done when interrupted/repaired runs retain true metrics and observations, and evaluation distinguishes decision validity from valid outer responses.
4. Complete F10. Done when fresh live comparison evidence, a verified deployment, matching source/commit metadata, final artifacts and a clean extraction rehearsal exist.

Application files were left unchanged. This report is the only audit deliverable added.
