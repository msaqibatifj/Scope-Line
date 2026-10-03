# Current model comparison - 3 October 2026

Both candidates ran the same ten cases in `public_cases.json` through the local
FastAPI app with real provider HTTPS inference. Both fallback paths were disabled.
Raw per-case responses, metrics, faults and source hashes are in
`current_comparison_results.json`; local controller and clarification evidence is
in `current_local_results.json`.

| Metric | Gemini 3.1 Flash-Lite | Gemini 3.5 Flash-Lite |
| --- | ---: | ---: |
| Task successes | 9/10 | 10/10 |
| Correct actions | 9/10 | 10/10 |
| Valid outer Arena responses | 10/10 | 10/10 |
| Valid actual model decisions | 16/17 | 18/18 |
| Valid first actual decision | 8/9 known runs | 10/10 |
| Runs requesting decision repair | 2 | 1 |
| Average latency | 16.77 s | 2.99 s |
| Input tokens | 46,487 (9/10 runs known) | 49,132 (10/10 known) |
| Output tokens | 671 (9/10 runs known) | 560 (10/10 known) |
| Estimated cost | $0 across 9 known runs; one unknown | $0 across all 10 runs |
| Fallback runs | 0 | 0 |

The 3.1 analysis case failed with a provider ReadTimeout. A successfully constructed
outer error response is not counted as valid model output. Synthetic invalid
decisions are excluded from actual-model validity and reported separately; a
provider outage without a decision is unknown rather than valid. One synthetic
repair case is present for each candidate.

**Selected default: Gemini 3.5 Flash-Lite.** In this small experiment it completed
every case, produced valid actual decisions and had substantially lower latency.
Its reported token total was slightly higher, but output usage was lower. Costs
are estimates under the configured free-tier assumption, not billing receipts.
Ten cases do not prove future availability or hidden-test performance.

The application uses six steps, one decision repair, at most two tool retries,
40 seconds per run and 512 output tokens per decision. Benchmark provider timeout
was 30 seconds; the production timeout remains a bounded configurable setting.
History retains 12 messages/20,000 characters, limits each history message to 2,000
characters and each untrusted item to 4,000 characters. The selected model is used
for short typed actions rather than exploiting its maximum context window.

Source hashes identify the uncommitted repaired implementation used in the run.
The process could not capture Git revision because Windows Git ownership checks
rejected that checkout. The runner now handles the workspace ownership explicitly.
After the experiment, only `app/config.py`'s default-model choice changed from 3.1
to the experimentally selected 3.5; the decision, tool and session code remained
the tested implementation. This selection change intentionally follows the experiment.

The current public site is https://scope-line.vercel.app/. These are local API /
live provider results, not verification that the repaired code is deployed there.
Public verification observed the old default 3.1 returning 401. Redeployment and
production authentication remain required before submission.
