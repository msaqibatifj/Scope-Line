# ScopeLine submission record

> Source fixes are awaiting a final release commit and redeployment. The current
> public site is reachable, but the default Gemini provider returned 401 during
> verification. Update the source commit and reverify successful public runs before turning in.

- Full name: Muhammad Saqib Atif
- Roll number: i230769
- Class / section: E_A01
- University email: i230769@isb.nu.edu.pk
- GitHub username: msaqibatifj
- Agent name: ScopeLine
- Domain: Freelance scope drift monitoring
- GitHub repository URL: https://github.com/msaqibatifj/Scope-Line
- Final commit hash: [full 40-character Git commit hash]
- Working agent interface: https://scope-line.vercel.app/
- Health endpoint (GET): https://scope-line.vercel.app/health
- Arena endpoint (POST): https://scope-line.vercel.app/arena/run
- Manifest endpoint (GET): https://scope-line.vercel.app/arena/manifest
- API documentation: https://scope-line.vercel.app/docs
- Hosting provider: Vercel
- Default model / provider: gemini-3.5-flash-lite / Gemini selected for repaired source; current deployment still reports 3.1 and returned 401
- Other available models: gemini-3.1-flash-lite; groq/qwen3.8-27b backup; local-scripted test baseline
- Example input: Analyze request-001 for project-001 and draft a change request.
- Expected result: Returns evidence-backed scope drift and a private review-only draft.
- Cold-start / restart limitations: In-memory chats and drafts are lost when a single-worker service restarts.
- Repository access: invited (reported by the student)
- Public test results: evaluation/public_results.json

Before packaging, confirm that the repository, deployment, submission record, and generated PDF all refer to the same final commit. Run the public health and Arena checks from outside the local environment, extract the generated ZIP into a clean folder, and confirm the application starts from the README instructions.
