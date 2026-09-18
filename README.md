# Sandbox File Janitor

Sandbox File Janitor organizes a small application-owned fixture collection. It can
list files, identify exact content duplicates, rename one selected file, and move a
bounded set of selected files into an existing sandbox folder. It does not delete
files, access user or host folders, run commands, execute arbitrary code, or use
network access.

## Completion rules

- Inspection is complete only when the response is backed by a successful sandbox observation.
- Rename and move tasks are complete only when the resulting path is verified and content is preserved.
- Ambiguous file requests require clarification before a mutation.
- Unsupported requests, including deletion, are blocked and may suggest moving files into `Review`.

## Design canvas

| Element | Decision |
| --- | --- |
| Goal | Organize a small fixture collection using safe inspection, rename, and move operations. |
| Completion | Verified inspection or verified mutation with preserved content. |
| Boundary | A temporary application-owned sandbox only; no arbitrary paths. |
| Observations | Request, bounded history, inventory, tool results, state, and untrusted notes. |
| Actions | List files, find exact duplicates, rename one file, move selected files. |
| State | Goal, step count, observations, attempts, operation IDs, budgets, and stop reason. |
| Autonomy | Only sandbox moves and renames; deletion and host access are blocked. |
| Risks | Wrong selection, collisions, traversal, repeat writes, injection, and unbounded execution. |
| Evaluation | Correctness, clarification, isolation, validation, recovery, and bounded termination. |

## Sandbox behavior

`data/sample_data.json` defines 16 safe fixtures, including three exact-duplicate
pairs, similar names with different content, filename collisions, spaces, a Unicode
filename, and instruction-like text for injection testing. Every sandbox starts from
these fixtures. File IDs remain stable while paths can change after a verified rename
or move. Arena runs will use fresh sandboxes; chat persistence comes later.

## Start locally on Windows
Use Python 3.12 or newer. Extract this folder first, then open a terminal inside it.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe run.py
```

Open http://127.0.0.1:8000/ for the interface or /docs for API requests.
Stop with Ctrl+C in the server terminal. If port 8000 is occupied, stop your old
server or change PORT in .env to 8001 and open that port. Do not run two servers
on the same port. On macOS/Linux use python3 and .venv/bin/python equivalents.

## What to implement
1. Choose a narrow domain and complete the design canvas below.
2. Replace data/sample_data.json with safe sandbox data.
3. Define typed decisions and state in models.py; implement at least three tools.
4. Write prompts.py and model integration. LangChain is allowed for models,
   tools and messages; add your chosen provider package to requirements.txt.
5. Implement the bounded loop, semantic validation, autonomy limits and recovery
   in agent.py. Read request.arena_config.max_steps; count repair attempts too.
6. Implement controlled fault injection at the model/tool boundary. The wrapper
   parses faults but DOES NOT simulate them for you.
7. Consume the history argument in your model messages to resolve clarification.
   Add configured model identifiers to api.py /models and validate selection.
8. Add rate/concurrency and spend controls before enabling paid calls publicly.
9. Replace the starter manifest and examples, test, deploy and submit.

## File map
- main.py: FastAPI composition and static files.
- api.py: routes, selected-model validation, session handoff.
- config.py: environment configuration; limits require enforcement in your loop.
- models.py: public contracts; add domain-specific state/decisions.
- agent.py, prompts.py, tools.py: student TODOs.
- memory.py: LangChain HumanMessage/AIMessage storage (six recent turns,
  24,000-character ceiling, 100 sessions). In-memory only; one worker. New chat
  clears server history; browser reload starts a new session. Not long-term memory.
- arena.py: timeout wrapper, response bound, safe event logging.
- static/: basic chat, selector, external note, status and observations.

## Arena contract
GET /health; GET /arena/manifest; POST /arena/run. POST /chat is for the UI.
Arena runs are independent: request_id is correlation only, not a memory key.
Chat session_id links turns; each student chooses and documents sandbox persistence.

The minimal request printed in the assignment works:
```json
{"task":"Your domain task","external_context":[],"arena_config":{"max_steps":6,"fault":"none"}}
```
The equivalent expanded fault is {"type":"none"}. Types: none, tool_timeout,
malformed_tool_output, invalid_agent_decision. Trigger the first matching operation
once per run. Supply request_id if desired; omitted IDs are generated.
External entries are {"source":"note","content":"text","trust":"untrusted"}.
Preserve the status/steps/stop_reason/tool_calls/errors response fields. Tool names
are domain-specific. Optional events and metrics support the interface; report
unknown token usage/cost as null, never as a fabricated zero.
`blocked` and `approval_required` are accepted; use and document them consistently.

## Test without spending API credits
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
The bundled tests check infrastructure only. They are NOT the hidden evaluator.
Add your own scripted-model tests. Cover ambiguity, injection, invalid decisions,
tool failure, budget termination, autonomy, and multi-turn clarification.

With the server running:
```powershell
.\.venv\Scripts\python.exe evaluation/run_public_tests.py --url http://127.0.0.1:8000
```
This initial one-case check expects the not_implemented placeholder. Replace it
with actual domain cases and expected outcomes. After model integration, this HTTP
runner can cost money. Run deliberately; do not repeatedly call paid models on CI.

## Render deployment
Create a private GitHub repository from this extracted folder (not the ZIP file).
Give the instructor access as announced in Google Classroom. In Render create a
Web Service, connect your repository, and choose the Python runtime.
- Build: pip install -r requirements.txt
- Start: uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
- Health check: /health
Select the free instance if available; confirm the displayed plan before deploying.
render.yaml is an optional Blueprint alternative. Dockerfile is another option.
Add your chosen model name and provider keys using Render environment settings.
Never commit .env. No keys are needed to deploy the incomplete scaffold.
Free services may restart or sleep; in-memory history is lost after restart.
Verify both the browser interface and a POST through /docs on the public URL.
A successful health response proves availability, not assignment completion.
Deployment has not been performed for you by this ZIP.

References: https://render.com/docs/deploy-fastapi
and https://docs.langchain.com/oss/python/langchain/messages

## Complete your project documentation
- Problem and measurable completion condition
- Design canvas: goal, completion, system boundary, observations, actions,
  state, autonomy boundary, primary risks, evaluation criteria
- Architecture diagram and file map
- Model comparison: two models/tiers on approximately ten common inputs;
  success, contract validity, action choice, latency, tokens and estimated cost
- Prompt/context design, session isolation, reset and memory limitations
- Typed schema and semantic validation rules
- Loop, retry/time/token/step limits and stop conditions
- Tool/fault handling and test evidence
- Setup, deployment, limitations and submission links

## Google Classroom submission
Rename the outer project folder to your lowercase roll number, e.g. i221234.
Prepare i221234.zip plus i221234_submission.pdf. Include SUBMISSION.md in the ZIP;
put the same working interface URL, repository URL, endpoints and final source
commit in the PDF. Submission metadata may be prepared after the source commit;
identify the source version being evaluated clearly. Exclude .env, .venv, .git,
node_modules, caches and secrets. Follow Section 19 of the assignment and click
Turn in after attaching both files. Pushes alone are not official submissions.
