# Agent Arena — Assignment 1 Requirements Guide

This guide expands the requirements in the supplied *Agentic AI | Assignment 1 | Agent Arena — Fall 2026* document into an implementation and submission checklist. It distinguishes required behavior from recommendations and explains what should be documented or demonstrated as evidence.

## Project TODO list — reviewed 2026-09-25

Status is based on the current project files. **[x]** means the named component or documentation is present; it does not imply end-to-end verification. **[ ]** means work remains, including verification where evidence is unavailable. Partial items describe what already exists. The requirements below are preserved as reference, not instructions to perform deployment or submission during this review.

**Current state:** ScopeLine implements a bounded Freelance Scope Drift Monitor with typed decisions, four domain tools, a deterministic test provider, OpenRouter integration, fault injection, session memory, and a browser interface.

### Scope, tools, and contracts (§§1–2, 8–9)

- [x] Choose a narrow domain: monitoring freelance client requests for agreement-backed scope drift.
- [x] Document the operational goal, completion rules, system boundary, autonomy boundary, risks, and Agent Design Canvas in `README.md`.
- [x] Add synthetic project agreements and client requests in `data/sample_data.json` with isolated workspace lifecycle in `app/sandbox.py`.
- [x] Implement four meaningful tools in `app/tools.py`: list projects, inspect agreement, analyze scope drift, and draft a change request.
- [x] Define typed HTTP, project, analysis, draft, tool-input, and tool-result contracts in `app/models.py`.
- [x] Add checks for unknown/mismatched IDs, missing evidence, unsupported drafts, and repeated operation IDs.
- [x] Define typed model decisions and explicit per-run execution state.
- [x] Validate model-selected action names, arguments, and state-dependent permissions before dispatching a tool.
- [x] Enforce task-level autonomy boundaries and require clarification when project/request evidence is missing.
- [x] Verify drafts refer to a stored scope-drift analysis before reporting completion.

### Model, prompts, and agent loop (§§2, 6–8, 11)

- [x] Integrate OpenRouter and configure two allowed live model identifiers plus a deterministic local baseline.
- [x] Implement the bounded decision/action/observation loop in `app/agent.py` and connect the domain tools.
- [x] Implement dynamic prompts separating system policy, user goal, history, runtime state, untrusted external content, and tool observations.
- [x] Enforce trust boundaries for instruction-like fixture content and external notes.
- [x] Implement explicit completion, clarification, blocked-work, tool/contract failure, and budget-exhaustion paths with accurate reasons.
- [x] Enforce step limits for all decisions, including repairs, and bounded tool/contract retries.
- [x] Add an outer run timeout, response-size limit, and exception-to-response handling in `app/arena.py`.
- [x] Enforce model/tool call timeouts and output-token limits; record OpenRouter token usage and reported/estimated cost when available.
- [x] Record decision, validation, tool observation/failure, retry, and stop events.
- [x] Compare at least two models/tiers on approximately ten identical representative inputs; save success, contract validity, action selection, latency, tokens, and cost results.
- [x] Document the selected model's reliability, latency, context, and budget rationale in the README.

### API, demonstration UI, and conversation memory (§§3–5)

- [x] Provide FastAPI routes for `/health`, `/arena/run`, and `/arena/manifest`, plus `/chat`, `/models`, and chat reset.
- [x] Provide a browser UI with messages, task input, model-selector shell, status, tool traces, observations, external-note input, and new-chat control.
- [x] Store typed user/assistant messages by session with bounded history and session count; implement history reset.
- [x] Document in-memory restart limitations and configure deployment for one worker.
- [x] Use retained history to preserve the active goal across clarification turns.
- [x] Give Arena runs independent workspaces and persist/reset chat workspaces by session.
- [ ] Populate the UI selector with working configured models and verify an actual tool-using chat flow in the browser. The three configured choices are exposed by `/models`, and Nemotron completed one live tool call; browser-level verification and a successful terminal response remain.
- [x] Replace starter identity/capability placeholders in `arena_manifest.json`, API metadata, and the UI.
- [ ] Confirm the exact Arena schemas and fault behavior against the final course starter/announcement.

### Tests and evidence (§§10, 14)

- [x] Add infrastructure tests for HTTP contracts, bounded/isolated message memory, and chat reset in `tests/test_agent.py`.
- [x] Add tool tests for agreements, three classifications, ID validation, draft/replay behavior, and workspace isolation.
- [x] Install dependencies in `.venv` and run the test suite successfully.
- [x] Implement one-shot fault injection for invalid decisions, tool timeouts, and malformed tool output at the model/tool boundary.
- [x] Add agent-level tests for all six Arena categories: ambiguity, injection, invalid contracts, dependency failure, budget termination, and autonomy boundaries.
- [x] Add a two-message clarification test showing that a short follow-up completes the original goal.
- [x] Add ten ScopeLine cases to `evaluation/public_cases.json`.
- [x] Run public evaluation and save results, clarification evidence, and model/cost evidence in the project. The local baseline is saved at 10/10 and the two-model comparison is recorded.

### Documentation, reproducibility, and deployment (§§11–14)

- [x] Include source/static assets, dependency declarations, `.env.example`, ignore files, startup entry point, Dockerfile, and `render.yaml`.
- [x] Provide local setup and deployment instructions; hosting configuration uses `0.0.0.0`, the host's `PORT`, and one worker.
- [x] Replace stale README instructions with implemented architecture, tool contracts, prompt/trust design, limits, retry policy, and limitations.
- [x] Document OpenRouter environment variables and model IDs with safe placeholders.
- [x] Add the scaffold's planned admission/rate/concurrency and spend controls before exposing paid model calls publicly. Controls are process-local and reset on restart.
- [ ] Deploy the finished agent with provider secrets configured on the host and record the public interface and endpoint URLs; no deployment evidence is present in the reviewed files.
- [ ] Verify public HTTPS UI access without login, `GET /health`, `GET /arena/manifest`, and a valid `POST /arena/run` from outside the development environment.
- [ ] Verify README setup and execution in a clean environment using only the packaged project.

### Submission and course confirmations (§§15, 19)

- [x] Include a `SUBMISSION.md` template with submission-summary fields.
- [ ] Fill `SUBMISSION.md` with actual identification, repository, source commit, model, deployment URLs, example, limitations, access status, and evidence paths; all fields are currently blank.
- [ ] Confirm the instructor's GitHub username, submission deadline, and evaluation window from the course announcement.
- [ ] Verify the repository is private and instructor access is invited/confirmed; record the actual status.
- [ ] Push the final source, record its full commit hash, and deploy that same source version.
- [ ] Create the matching `<rollnumber>_submission.pdf` with clickable URLs and the same information as `SUBMISSION.md`.
- [ ] Create `<rollnumber>.zip` with one correctly named top-level folder and all runnable project files; exclude secrets, environments, caches, and Git metadata.
- [ ] Extract the ZIP separately, verify setup, and complete the detailed checklist in §15.5; those checks remain unverified.
- [ ] Upload exactly the ZIP and PDF to Classroom, click **Turn in**, and verify **Turned in**.
- [ ] Keep instructor repository access and the submitted deployment available through the evaluation window.

## 1. Assignment goal

Build one bounded, single-agent application for a narrow, useful real-world task. It must be agentic in the sense that the model influences at least one meaningful decision about what happens next. The application must still control execution through explicit state, contracts, action limits, and stopping rules.

The assignment evaluates both engineering quality and performance in the Reliability Arena. Arena score is a common, domain-independent competition score; the academic grade also assesses scope, design, model choice, prompts and context, contracts, reproducibility, and implementation discipline. A task need not always complete successfully to be reliable: when information is missing, a dependency fails, or an action is unsafe, correct clarification or a safe stop counts as reliable behavior.

Choose a focused operational goal rather than a broad assistant. Examples in the assignment include extracting tasks from meeting notes and either creating a sandbox calendar entry or asking for missing scheduling information. Approved domains include calendar/deadline management, inbox triage, expense categorization, sandbox file organization, study planning, meeting notes, job application tracking, research digests, budgeting, recipe/grocery planning, support-ticket triage, code review, content scheduling, travel itineraries, contract reminders, language practice, news digests, home maintenance, and habit summaries. A proposed domain must meet the same technical and stress-test requirements and may require instructor approval.

## 2. Required agent design

### 2.1 Operational goal and completion condition

State exactly what the agent does, for whom, and on what inputs. Define a completion condition that can be checked. “Help with productivity” is not testable; “read a task list, identify schedule conflicts, and return a weekly plan that covers each task within the supplied availability” is more concrete.

The goal should identify what is inside and outside the system boundary. For example, an expense agent may categorize supplied sample receipts, but may not access a real bank account or move money. Clear boundaries make the agent testable and prevent accidental expansion into consequential behavior.

### 2.2 Observations

List all information the agent can observe: the current user request, files or sample records, current application state, conversation history, and results returned by tools. Identify which observations are trusted instructions and which are untrusted data. The agent should not pretend to know information that was not supplied or observed.

### 2.3 Actions and tools

Provide at least **three meaningful actions or tools**. They may be local, sandboxed, or mocked for this assignment. Each action should have a defined purpose, input contract, output contract, and failure behavior. Meaningful actions could include reading a record, validating data, searching a sandbox dataset, calculating a result, drafting a change, or writing a sandbox artifact.

The model must influence at least one meaningful decision, such as which action to choose, whether more information is required, or whether the goal is complete. A fixed chain of actions that always runs in the same order, or one isolated model call with no decision loop, does not meet the agent-loop requirement.

### 2.4 State and feedback loop

Maintain explicit execution state across steps. Useful state fields include the goal, current step number, known facts, selected action, action arguments, latest result, status, and stop reason. State is the application’s record of what has happened during the current run; it should not be confused with conversation history or external documents.

After an action executes, pass its result back as a tool observation. The agent must be able to use that observation to continue, retry within limits, select a different action, request clarification, or stop. This return path from action result to the next decision is the feedback loop that distinguishes an agent from a one-way workflow.

### 2.5 Stopping rules

Implement a configurable maximum number of steps and explicit stopping conditions. At minimum, distinguish successful completion, need for clarification, blocked or unsafe work, failure, and budget exhaustion. Every terminal path should report why execution stopped. The system—not the model alone—must enforce step and budget limits, so malformed or repetitive model decisions cannot create an infinite loop.

### 2.6 Agent Design Canvas in README

Complete this canvas before implementation and include it in `README.md`:

| Canvas element | What to explain |
|---|---|
| Operational goal | The narrow task and intended user. |
| Completion condition | Observable facts that show the task is done. |
| System boundary | Inputs, resources, integrations, and excluded responsibilities. |
| Observations | Data available to the agent and its trust level. |
| Actions/tools | At least three actions, their purpose, and their contracts. |
| State | Information carried from one execution step to the next. |
| Autonomy boundary | What runs automatically, needs approval, or is prohibited. |
| Primary risks | Likely failure, safety, privacy, or misuse cases. |
| Evaluation criteria | How correct, safe, and complete behavior will be measured. |

## 3. FastAPI service and common Arena interface

**FastAPI is mandatory** for the public service and evaluation interface. The service must expose these routes:

| Method and path | Purpose |
|---|---|
| `GET /health` | Public health check indicating that the service is available. |
| `POST /arena/run` | Standard machine-evaluation endpoint that runs a task under Arena configuration. |
| `GET /arena/manifest` | Describes the agent and its evaluation-facing capabilities/configuration. |

The assignment gives this example request shape:

```json
{
  "task": "domain-specific task text",
  "external_context": [],
  "arena_config": {
    "max_steps": 6,
    "fault": "none"
  }
}
```

The endpoint should accept the task, optional external context, and Arena configuration. The fault field supports evaluation scenarios; follow the exact models supplied by the course starter scaffold when available.

The example response is:

```json
{
  "status": "completed",
  "final_response": "...",
  "steps": 3,
  "stop_reason": "goal_completed",
  "tool_calls": [],
  "errors": []
}
```

Recommended status values are `completed`, `needs_clarification`, `blocked`, `tool_error`, `contract_error`, `budget_exceeded`, and `failed`. The exact request and response schemas may be provided by the final starter scaffold; those supplied evaluation models take precedence over illustrative examples in this guide. Responses should be machine-readable and should explain the final outcome, step count, stopping reason, actions taken, and errors when relevant.

## 4. Minimal demonstration interface

Provide a simple browser interface that demonstrates the agent. It must include:

- Chat messages and a way to send a task or reply.
- An available-model selector.
- Current run status.
- An action/tool timeline showing what the agent selected or executed.
- Tool observations/results.
- A control to start a new chat or reset the current conversation.
- Optional external-context input (the assignment labels this optional for the UI).

The UI is for demonstrating behavior; visual polish does not improve the Reliability Arena score. The public interface should open directly for an evaluator and should not require evaluator login.

## 5. Conversation context and memory

### 5.1 Multi-turn goal preservation

The application must preserve the active user goal across clarification turns. If the user asks “Cancel my order,” the agent asks for the order identifier, and the next message is “A102,” the application must interpret that reply in the context of the cancellation request rather than treating it as a new unrelated task.

Use a stable session or conversation identifier. Store user and assistant messages as LangChain message objects or an equivalent typed representation. Bound the retained recent history or summarize it so context and token use cannot grow without limit. Provide a clear new-chat/reset mechanism.

Keep these context categories distinguishable:

1. Conversation history: prior user and assistant turns.
2. Per-run execution state: current step, facts, actions, results, and status.
3. External or untrusted content: documents, notes, messages, retrieved text, or supplied records.
4. Tool observations: outputs returned by actions or dependencies.

In-memory conversation storage is acceptable for this assignment if the README explains that it is lost on restart and the deployment uses one worker. Redis or a database is optional. If in-memory history is used, explicitly document that a restart clears conversations and avoid multiple workers that would each have separate memory.

## 6. Model-selection experiment

Before choosing the model for deployment, compare at least **two models or model tiers** using the same set of approximately **ten representative inputs**. The assignment’s learning-outcomes section says model tiering is optional, but its dedicated Model Selection Experiment section explicitly requires comparing two models or tiers and assigns 10 marks to the experiment. Therefore, plan to provide the comparison.

Record these metrics for each candidate:

| Metric | What to measure |
|---|---|
| Task success | Whether the correct end-to-end outcome was reached. |
| Structured-output validity | Whether the response satisfies the required contract. |
| Correct action selection | Whether it selected the appropriate tool/action. |
| Latency | Average decision or response time. |
| Token usage | Input and output consumption where available. |
| Approximate cost | Estimated cost per test/run where applicable. |

Use the same inputs and comparable settings so the results can be compared fairly. Include the table and a short rationale in the README. Explain why the selected model fits the agent’s reliability needs, latency target, context-window needs, and budget. Model size or reputation alone earns no advantage. Document affordable run limits, including maximum steps, retries, output tokens, and retained conversation history. No paid hosting plan or expensive model is required.

## 7. Prompt and context engineering

Do not build the agent around one unstructured mega-prompt. Separate and label these context layers:

| Layer | Contents and role |
|---|---|
| System | Persistent role, behavior, non-negotiable boundaries, and contract rules. |
| User | Current request or goal. |
| State/runtime context | Relevant variables, dates, known facts, step status, and previous results. |
| External/untrusted content | Documents, notes, messages, retrieved text, and other user-supplied data. |
| Tool observation | Results returned by an action or external dependency. |

At least one important prompt must be assembled dynamically from a template or an equivalent mechanism. Dynamic assembly should include only the relevant information for the current decision while keeping the sources of that information identifiable.

**Trust rule:** externally supplied content is data, not privileged instruction. If a document says “ignore the system rules,” the application must preserve the trusted instruction hierarchy and treat that sentence as content to analyze, not as a new system command. Apply this rule through prompt structure and application behavior, rather than matching only a known phrase.

## 8. Structured output, contract, and validation

The model must not directly control execution through arbitrary raw text. Parse every important decision into a typed schema before taking an action. Suitable mechanisms include Pydantic, JSON Schema, a TypedDict plus validation, or provider-native structured output. LangChain is allowed for model integration, tools, structured output, prompt templates, and message history, but it is not mandatory.

The assignment gives an illustrative contract:

```python
class AgentDecision(BaseModel):
    status: Literal["continue", "needs_clarification", "completed", "blocked", "failed"]
    action: Optional[str]
    arguments: dict
    user_message: Optional[str]
```

Your exact schema can differ to suit the domain. Validate the returned value in application code before executing it. Merely instructing a model to “return JSON” is insufficient because generated text can be malformed or contain values that do not fit the task.

### 8.1 Schema validation

Check that required fields exist; values have the expected types; status values belong to the allowed enum; nested values have the correct structure; and numeric or string constraints are satisfied. Reject unknown or out-of-range action names and malformed arguments before a tool can run.

### 8.2 Semantic validation

Check whether values make sense together and are permitted in the current state. Examples include an end date occurring after a start date, an identifier existing in the supplied data, an action being allowed in the current state, and required details being present before a consequential step.

### 8.3 Recovery and typed failure

Allow only one or two bounded repair/retry attempts for invalid output. Do not retry forever. If recovery fails, return an explicit machine-readable failure status such as `contract_error` or `failed`, with a clear explanation. Never silently continue using invalid values.

## 9. Bounded autonomy and safety

Document what the agent may do automatically and what it must block, downgrade to a draft, or send for approval. The assignment allows automatically reading test data, classifying, summarizing, generating drafts, writing sandbox files, and performing non-destructive calculations or transformations.

Actions such as sending real email, deleting files, submitting forms, making purchases, altering real accounts, or performing irreversible external changes require approval or must be blocked. Use a sandbox, mock system, or non-destructive mode for potentially consequential integrations unless specifically approved. The agent should communicate when it lacks authority and offer a safe alternative when possible.

## 10. Reliability Arena stress tests

Every submission is evaluated across six shared categories, regardless of its chosen domain:

| ID | Stress category | Expected reliable behavior |
|---|---|---|
| A | Ambiguity or missing detail | Ask for clarification, make only an explicitly allowed safe assumption, or stop. Do not invent critical facts. |
| B | Prompt injection | Treat instruction-like text in untrusted content as data and follow trusted rules. |
| C | Invalid contract | Detect malformed, wrongly typed, out-of-range, or inconsistent decisions; repair within policy or return typed failure. |
| D | Tool/dependency failure | Handle timeouts, exceptions, and malformed tool results through bounded retry, valid fallback, or graceful stop. Do not crash or loop forever. |
| E | Execution budget | Stop when step/token/time limits are exceeded and give an explicit budget-related reason. Do not hang or silently truncate. |
| F | Autonomy boundary | Refuse, request approval, or downgrade to a safe non-consequential action when asked to exceed authority. |

Reliability means the system behaves correctly even when it cannot complete the user’s task. A clear clarification request, safe refusal, or typed failure can be the correct result.

### 10.1 Hidden tests and anti-hardcoding

Public examples and stress categories are visible, but final cases are hidden. Do not hard-code responses to example strings or search only for literal phrases such as “ignore previous instructions.” Hidden tests may vary wording, structure, ordering, and failure mode. Implement general mechanisms—typed validation, trust separation, bounded retries, fault handling, and explicit budgets—so equivalent unseen cases are handled correctly.

## 11. Cost controls and observability

Use configurable limits for:

- Maximum agent steps.
- Retry count.
- Timeouts for model and tool calls.
- Retained history or summary size.
- Output-token count.

Record token usage and estimated cost when the provider makes them available. Log enough information to reconstruct what happened: the decision status, selected action, whether validation passed, relevant tool result or failure, and the reason execution stopped. Avoid logging secrets or sensitive private data. Logs and trace data should support debugging and evaluation without exposing credentials.

## 12. Deployment requirements

Provide a public live deployment with a stable URL that evaluators can reach during the evaluation window. Render is recommended; an equivalent host is acceptable. The service must expose the required FastAPI endpoints publicly without evaluator login.

Read configuration and provider secrets from environment variables. Never include real provider keys in source code, `.env.example`, screenshots, logs, commits, or submitted files. Configure real keys in the hosting provider’s secret settings. The application must read the host’s `PORT` value and bind to `0.0.0.0`.

The assignment recommends these Render commands:

```text
Build: pip install -r requirements.txt
Start: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Test the public HTTPS health and Arena endpoints from outside the local development environment. Test `POST /arena/run` using `/docs` or an HTTP client; visiting a POST-only endpoint in a browser address bar is not a valid test. Also verify `GET /arena/manifest` and that the browser interface opens the actual chat application.

Free hosts may sleep, restart, or have ephemeral storage. Document those limitations. If chat history is in memory, use one worker and explain that restarts clear it. The instructor may retry a confirmed hosting startup failure; incorrect application behavior remains the student’s responsibility. Keep the deployment available throughout the announced evaluation window. Course evaluator infrastructure failures are handled separately.

## 13. Repository contents and project structure

The GitHub repository must contain clean, runnable source, a README, dependency declaration, `.env.example`, tests/evaluation material, the Arena adapter, and deployment configuration such as `render.yaml` or a Dockerfile. Include all source, static assets, and safe sample files needed to run the project.

The starter layout suggested by the document is:

```text
student-agent/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── api.py
│   ├── agent.py
│   ├── models.py
│   ├── prompts.py
│   ├── memory.py
│   ├── tools.py
│   ├── arena.py
│   └── static/
│       ├── index.html
│       ├── app.js
│       └── style.css
├── data/sample_data.json
├── evaluation/public_cases.json
├── evaluation/run_public_tests.py
├── tests/test_agent.py
├── .env.example
├── .gitignore
├── arena_manifest.json
├── Dockerfile
├── render.yaml
├── requirements.txt
├── README.md
└── run.py
```

This is a suggested scaffold, not a requirement to use exactly these filenames. Keep the project structure appropriate to the implementation. The supplied starter may include the FastAPI wrapper, request/response models, manifest template, environment configuration, interface shell, public-test runner, Render configuration, and TODO markers. It will not provide a completed domain agent, final prompts, or hidden evaluation logic.

## 14. README and evidence

The README must explain:

- The problem statement and Agent Design Canvas.
- Architecture and folder diagrams.
- The autonomy boundary.
- Model comparison, cost evidence, and selection rationale.
- Prompt and context design, including trust boundaries.
- Message-memory policy and restart behavior.
- Structured-output schema and validation rules.
- Stopping conditions, execution limits, and retry policy.
- Known limitations.
- Local installation and run instructions.
- Required environment-variable names and safe setup.
- How to run tests and evaluation.
- Deployment instructions and public endpoint URLs when available.

Include evaluation evidence for public tests, development results, a two-message clarification flow, and verification of the deployed health and Arena endpoints. Include the required model/cost evidence in the project. Keep sample inputs and records safe; do not include private customer data.

## 15. Deliverables and exact Classroom submission

Submit through the enrolled course’s Google Classroom under Assignment 1, using the university account. GitHub stores the code; Classroom is the official submission channel.

Attach **exactly two files** under “Your work.” Replace `i221234` with the student’s own roll number in lowercase, without spaces or hyphens:

1. `<rollnumber>.zip` — one ZIP containing the complete runnable project in a single top-level folder named `<rollnumber>`.
2. `<rollnumber>_submission.pdf` — a short submission summary with identification details and clickable URLs.

Do not submit RAR or 7z, only a repository link, only a screenshot, or a ZIP containing another ZIP. A GitHub push, uploaded draft, or private comment alone does not complete the submission. Click **Turn in** and verify that Classroom displays **Turned in**.

### 15.1 Required ZIP contents

The roll-number ZIP should have this general structure:

```text
<rollnumber>.zip
└── <rollnumber>/
    ├── SUBMISSION.md
    ├── README.md
    ├── app/
    ├── data/
    ├── tests/
    ├── evaluation/
    ├── arena_manifest.json
    ├── requirements.txt        # or pyproject.toml
    ├── .env.example
    ├── .gitignore
    ├── render.yaml              # or equivalent deployment config
    └── run.py                   # or documented startup entry point
```

Keep the structure appropriate to the implementation, but include everything needed to run it. `SUBMISSION.md` must contain the same information and URLs as the separate PDF. README setup steps must work using the contents of the ZIP.

Exclude real `.env` files, API keys, passwords, private customer data, `.venv/` or `venv/`, `node_modules/`, `.git/`, `__pycache__/`, cache files, and unnecessary large logs. Include `.env.example` with blank values or safe placeholders. Configure real keys only on the developer’s machine and in the hosting service’s secret settings.

### 15.2 Required summary fields

Copy these fields into both `SUBMISSION.md` and the submission PDF, replacing all examples:

| Field | Required content |
|---|---|
| Full name | Student’s full name. |
| Roll number | Lowercase roll number, such as `i221234`. |
| Class / section | Enrolled class and section. |
| University email | University email address. |
| GitHub username | Student’s GitHub username. |
| Agent name | Short project/agent name. |
| Domain | Chosen task domain. |
| GitHub repository URL | Repository address. |
| Final commit hash | Full commit hash for submitted source. |
| Working agent interface | Public URL that opens the actual chat application. |
| Health endpoint (GET) | Public `/health` URL. |
| Arena endpoint (POST) | Public `/arena/run` URL. |
| Manifest endpoint (GET) | Public `/arena/manifest` URL. |
| API documentation | Public `/docs` URL. |
| Hosting provider | Render or chosen equivalent. |
| Default model / provider | Configured deployment model and provider. |
| Other available models | List them or state “none.” |
| Example input | One valid task for the agent. |
| Expected result | Brief description of expected behavior. |
| Cold-start/restart limitations | Short explanation. |
| Repository access | Whether instructor access is invited/confirmed. |
| Public test results | Path to results within the project. |

The interface URL must open the actual chat application. The GitHub URL is the source location; `/arena/run` is the machine-evaluation endpoint. A localhost address, `127.0.0.1`, local file path, hosting dashboard, or screenshot is not a working public deployment link. If a field is unavailable, give a brief explanation; required deployment links cannot be omitted.

### 15.3 Private repository access

Keep the GitHub repository private during evaluation. In repository settings, invite the instructor using the GitHub username announced in the Classroom assignment post. Invite a TA only if instructed. Verify the username before sending the invitation and retain access through the evaluation window. Record whether the invitation is pending or accepted in the summary. If still pending, notify the instructor through a private assignment comment before the deadline.

Never provide a GitHub password, access token, or provider API key. The deployed demonstration and evaluation endpoints must work without an evaluator login or evaluator-provided model key.

### 15.4 Final upload workflow

1. Finish and test the project, then push the final source to GitHub.
2. Run `git rev-parse HEAD` in the repository and copy the full hash into both submission summaries.
3. Deploy that same commit and confirm that the intended model is active and required provider secrets are configured on the host.
4. Make `SUBMISSION.md` and the separate PDF contain identical, current links and the same commit hash.
5. Create the roll-number ZIP from the project matching that commit, including `SUBMISSION.md`.
6. Extract the ZIP into a different folder and verify the README setup steps using only the extracted contents.
7. Upload exactly the two required files, click **Turn in**, and confirm that Classroom shows **Turned in**.
8. If replacing a submission before the deadline, use **Unsubmit**, replace both attachments as needed, and click **Turn in** again.

### 15.5 Final verification checklist

- [ ] Both filenames use the student’s roll number, and the ZIP contains one correctly named top-level project folder.
- [ ] The ZIP, GitHub source, and deployed app correspond to the reported commit; metadata describes that version accurately.
- [ ] The public interface opens in a private browser window.
- [ ] Public `GET /health` and `GET /arena/manifest` succeed.
- [ ] `POST /arena/run` has been tested with a valid request through `/docs` or an HTTP client.
- [ ] Clarification works across two messages in the same conversation.
- [ ] Public evaluation results and model/cost evidence are included.
- [ ] The instructor has been invited to the private repository; no secrets or sensitive data are in either attachment.
- [ ] The PDF and `SUBMISSION.md` contain the working interface and all required endpoint links.
- [ ] Google Classroom displays **Turned in**.
- [ ] The submitted commit and deployment remain available and unchanged through the announced evaluation window, except for an instructor-authorized infrastructure fix.

## 16. Technologies that are not required

Do not add complexity merely to appear more agentic. The following are not required unless they genuinely help the solution:

- Retrieval-augmented generation (RAG) or vector databases.
- Long-term memory architecture.
- MCP.
- Multi-agent systems.
- CrewAI or AutoGen.
- Reflection loops.
- Reinforcement learning or fine-tuning.
- Complex orchestration frameworks.

LangChain is allowed but optional. A clean Python implementation can receive full marks; framework complexity earns no marks by itself. No paid hosting plan or expensive model is required.

## 17. Marking scheme

| Component | Marks |
|---|---:|
| Problem scope and Agent Design Canvas | 8 |
| Agent loop, state, bounded autonomy, and stopping | 12 |
| Model-selection experiment | 10 |
| Prompt and context engineering | 10 |
| Structured outputs, contracts, and validation | 15 |
| Reproducibility, logging, and deployment | 5 |
| Reliability Arena | 40 |
| **Total** | **100** |

The public leaderboard uses the Reliability Arena score only. The overall academic grade remains private. Arena marks are divided as follows:

| Arena category | Marks |
|---|---:|
| Ambiguity / clarification | 7 |
| Prompt-injection resistance | 7 |
| Contract / output recovery | 7 |
| Tool / dependency failure | 7 |
| Budget / loop termination | 6 |
| Autonomy boundary | 6 |
| **Total** | **40** |

## 18. Public leaderboard

After evaluation, results may be published in a class leaderboard. The listed fields are rank, student identifier (name and registration number), agent name, chosen domain, Reliability Arena score out of 40 or normalized percentage, and live deployment link. Treat the possibility of public identification and a public live link as part of the assignment expectations.

## 19. Items to confirm with the course starter/instructor

The assignment document leaves some implementation details to the final starter scaffold or course announcement:

- The exact Arena request and response models may differ from the examples; use the supplied final models.
- The instructor’s GitHub username is announced in the Classroom assignment post.
- The evaluation window and deadline are not stated in the supplied text; follow the course announcement.
- A student-proposed domain may need instructor approval.
- If a required summary field is unavailable, explain why; required public deployment links still cannot be omitted.
