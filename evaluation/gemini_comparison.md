# Gemini Live Model Comparison Evidence

ScopeLine compares `gemini-3.1-flash-lite` and `gemini-3.5-flash-lite` on the same ten Arena cases in `evaluation/public_cases.json`. Both fallback paths were disabled for comparison, so a run that switches to local policy or Qwen does not count as a candidate success.

## Latest Run

The best current evidence is `evaluation/gemini_comparison_results_retry.json`, generated on 2026-09-26 with `MODEL_TIMEOUT_SECONDS=30`, `--in-process`, and `--delay 30`. The FastAPI transport was local, but model calls used the live Gemini API. `live_only` is true and `fallback_runs` is zero for both models.

| Model | Task success | Valid contracts | Correct actions | Avg latency | Tokens | Reported cost | Fallbacks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `gemini-3.1-flash-lite` | 9/10 | 10/10 | 10/10 | 5.91 s | 50,385 in / 706 out | $0.00 | 0 |
| `gemini-3.5-flash-lite` | 9/10 | 10/10 | 9/10 | 3.93 s | 50,733 in / 510 out | $0.00 | 0 |

## Remaining Failures

- `gemini-3.1-flash-lite` failed `List projects` on retry because the Gemini API returned HTTP 503.
- `gemini-3.5-flash-lite` failed `Missing project asks clarification` because it selected `list_projects` twice. ScopeLine rejected that with `list_projects is not the requested operation`, which is the intended controller behavior.

## First Run

`evaluation/gemini_comparison_results.json` was the first live-only run on 2026-09-26. It recorded 8/10 for 3.1 and 6/10 for 3.5. Failures were Gemini API 503s and read timeouts. The slower retry is the preferred evidence file because it reduced provider timing noise while preserving live-only execution.

## Selection

The project keeps `gemini-3.1-flash-lite` as the default candidate because it reached the project release target of 9/10 live-only successes, had 10/10 correct actions on the successful retry evidence, and its remaining failure was provider availability rather than a wrong autonomous decision. Qwen remains the runtime backup for transient primary-provider failures and is not counted as a comparison candidate.

The reported cost is the provider/API response under the configured free-tier assumption, not an independent billing receipt.
