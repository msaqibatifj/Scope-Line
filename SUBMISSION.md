# ScopeLine submission record

> Complete every bracketed field after deploying the final commit. The packaging
> script intentionally rejects placeholders, private URLs, and incomplete metadata.

- Full name: [your full name]
- Roll number: i230769
- Class / section: E_A01
- University email: [your university email]
- GitHub username: [your GitHub username]
- Agent name: ScopeLine
- Domain: Freelance scope drift monitoring
- GitHub repository URL: [https://github.com/USER/REPOSITORY]
- Final commit hash: [full 40-character Git commit hash]
- Working agent interface: [https://YOUR-APP.example]
- Health endpoint (GET): [https://YOUR-APP.example/health]
- Arena endpoint (POST): [https://YOUR-APP.example/arena/run]
- Manifest endpoint (GET): [https://YOUR-APP.example/arena/manifest]
- API documentation: [https://YOUR-APP.example/docs]
- Hosting provider: [Vercel, Render, or another public host]
- Default model / provider: [configured deployed model and provider]
- Other available models: gemini-3.5-flash-lite; groq/qwen3.8-27b backup; local-scripted test baseline
- Example input: Analyze request-001 for project-001 and draft a change request.
- Expected result: Returns evidence-backed scope drift and a private review-only draft.
- Cold-start / restart limitations: In-memory chats and drafts are lost when a single-worker service restarts.
- Repository access: [instructor invited / accepted / pending]
- Public test results: evaluation/public_results.json

Before packaging, confirm that the repository, deployment, submission record, and generated PDF all refer to the same final commit. Run the public health and Arena checks from outside the local environment, extract the generated ZIP into a clean folder, and confirm the application starts from the README instructions.
