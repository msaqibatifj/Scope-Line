# Model Comparison Evidence

## Status

The deterministic `local-scripted` baseline is verified by the automated suite
and passed all ten public cases. Both OpenRouter models were run against the same
ten synthetic cases on 2026-09-25 using one API key.

## Models

| Model | Provider | Status | ScopeLine alignment |
| --- | --- | --- | --- |
| `local-scripted` | Local deterministic | Dependency fallback: 10/10 public cases | Repeatable control-flow and fault baseline. |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | OpenRouter | 0/10 initial comparison | Better reasoning candidate, but inconsistent decision-tool compliance. |
| `cohere/north-mini-code:free` | OpenRouter | 1/10 initial comparison | Slightly better action selection, but inconsistent and frequently slow. |

The OpenRouter models are compared on control decisions, not writing style:
selecting the correct tool, requesting missing evidence, respecting the review-only
boundary, finishing from observations, and returning a valid typed contract.

## Initial comparison

| Model | Task success | Valid outer contract | Correct action | Avg latency | Tokens | Cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Nemotron 3 Ultra Free | 0/10 | 10/10 | 2/10 | 23.23 s | 2,610 in / 789 out | $0.00 |
| North Mini Code Free | 1/10 | 10/10 | 3/10 | 19.85 s | 3,560 in / 2,743 out | $0.00 |

The outer contracts remained valid because ScopeLine converted provider failures
into bounded typed responses. Most task failures came from missing/invalid decision
tool calls or the 40-second timeout.

## Follow-up

The adapter was changed to force the named `submit_agent_decision` function and to
give malformed provider decisions one contract-repair attempt. Nemotron then
completed `List projects` in two steps at 12.49 seconds (2,240 input tokens, 451
output tokens, $0 reported cost). North still timed out. A complete post-fix rerun
was attempted, but OpenRouter returned HTTP 429 for the free endpoints. That run is
preserved in `evaluation/model_comparison_rate_limited_results.json`.

The deployment default is Nemotron because the course requires a model to influence
meaningful execution decisions and it completed the post-fix tool loop. The local
policy is retained only as a traced fallback for transient provider failure; North
remains the secondary comparison model. Neither free endpoint should handle
confidential client data or be treated as production-reliable.

## Common inputs

Use the ten cases in `evaluation/public_cases.json`. They cover project listing,
agreement inspection, explicit drift, draft chaining, ambiguity, blocked client
contact, budget exhaustion, decision repair, tool retry, and prompt injection.

## Metrics

Results are saved in `evaluation/model_comparison_results.json`. The repeatable
runner is `evaluation/run_model_comparison.py`. It records task success, contract
validity, action choice, latency, prompt/completion tokens, reported cost, and
provider failures after every case.

Official references:

- https://openrouter.ai/docs/quickstart
- https://openrouter.ai/docs/guides/features/structured-outputs
- https://openrouter.ai/nvidia/nemotron-3-ultra-550b-a55b:free
- https://openrouter.ai/cohere/north-mini-code:free
