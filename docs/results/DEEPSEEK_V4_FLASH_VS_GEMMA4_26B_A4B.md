# DeepSeek V4 Flash vs. Gemma 4 26B-A4B on AsynCodeBench

## Evaluation Scope

This comparison uses the 16 official AsynCodeBench tasks and all four
protocols. Each task-protocol cell was run once with the built-in OpenHands
adapter and the `asyncodebench-v0.3-standard-100` execution profile.

| Setting | DeepSeek V4 Flash | Gemma 4 26B-A4B |
| --- | --- | --- |
| Model | `openrouter/deepseek/deepseek-v4-flash-0731` | `openai/google/gemma-4-26B-A4B-it` |
| Serving | Hosted API | Local vLLM |
| Harness revision | `ddebb7d` | `ddebb7d` |
| OpenHands adapter | Built-in | Built-in |
| Tasks x protocols | 16 x 4 | 16 x 4 |
| Admitted runs | 64/64 | 64/64 |

DeepSeek values are transcribed from the repository README. Gemma values are
independently recomputed from the selected `run_bundle.json` and
`process_metrics_summary.json` artifacts documented in
`GEMMA4_26B_A4B_OH1292_RESULTS.md`.

## Main Comparison

Higher is better for final success, test pass rate, and ADPR. Lower is better
for penalized DRS and CAIL. Unresolved dependencies receive the run-local
`T + 1` penalty.

| Protocol | Model | Successful tasks | Mean pass | Mean ADPR | Penalized DRS | Penalized CAIL |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Single | DeepSeek | 16/16 (100.0%) | 99.0% | 100.0% | 1.000 | 0.000 |
| Single | Gemma | 0/16 (0.0%) | 22.2% | 1.3% | 1.988 | 1.975 |
| Serial specialists | DeepSeek | 10/16 (62.5%) | 75.0% | 69.8% | 6.121 | 2.590 |
| Serial specialists | Gemma | 0/16 (0.0%) | 22.2% | 2.1% | 7.875 | 7.758 |
| Async private | DeepSeek | 8/16 (50.0%) | 74.8% | 69.8% | 7.131 | 5.037 |
| Async private | Gemma | 0/16 (0.0%) | 15.6% | 1.3% | 10.925 | 10.900 |
| CAID manager | DeepSeek | 13/16 (81.3%) | 92.2% | 88.5% | 7.292 | 2.669 |
| CAID manager | Gemma | 0/16 (0.0%) | 26.0% | 1.3% | 10.800 | 10.525 |

## AsynCodeBench Coordination Diagnostics

These diagnostics are central to the benchmark rather than secondary
efficiency statistics. They distinguish failed subagent work, integration
failure, writable-scope violations, and manager recovery even when final
success has a floor or ceiling effect.

| Model | Protocol | FSAR | IFR | SVR | MRR |
| --- | --- | ---: | ---: | ---: | ---: |
| DeepSeek | All protocols | Not reported | Not reported | Not reported | Not reported |
| Gemma | Single | 0.0% | 0.0% | N/A | N/A |
| Gemma | Serial specialists | 45.3% | 100.0% | 27.6% | 54.7% |
| Gemma | Async private | 62.0% | 100.0% | 29.7% | 37.0% |
| Gemma | CAID manager | 52.2% | 100.0% | 36.3% | 45.1% |

`MRR` is a conditional recovery diagnostic, not an unconditional
higher-is-better score. It must be interpreted together with FSAR and the raw
number of failed attempts. DeepSeek values remain unreported because its
public aggregate does not contain the required raw process fields.

## Efficiency and Coordination Diagnostics

| Protocol | Model | Mean tokens | Mean runtime | FSAR | SVR |
| --- | --- | ---: | ---: | ---: | ---: |
| Single | DeepSeek | 1.685M | 15.2 min | Not reported | Not applicable |
| Single | Gemma | 0.554M | 12.8 min | 0.0% | Not applicable |
| Serial specialists | DeepSeek | 3.696M | 38.1 min | Not reported | Not reported |
| Serial specialists | Gemma | 3.106M | 44.3 min | 45.3% | 27.6% |
| Async private | DeepSeek | 4.004M | 20.8 min | Not reported | Not reported |
| Async private | Gemma | 3.073M | 26.5 min | 62.0% | 29.7% |
| CAID manager | DeepSeek | 6.452M | 33.9 min | Not reported | Not reported |
| CAID manager | Gemma | 4.855M | 46.3 min | 52.2% | 36.3% |

Runtime and token counts should primarily be compared across protocols within
the same model. DeepSeek used a hosted endpoint, Gemma used local vLLM, and the
models use different tokenizers.

## Presentation-Ready Findings

### 1. Asynchrony creates a speed-quality tradeoff

For DeepSeek, async private is 45.5% faster than serial specialists. Mean pass
rate and ADPR are nearly unchanged, but successful tasks fall from 62.5% to
50.0% and penalized CAIL rises from 2.590 to 5.037. Traditional pass rate alone
therefore hides a large increase in dependency-resolution delay.

Gemma exhibits the same direction: async private is about 40.2% faster than
serial, but pass rate falls by 6.6 percentage points, CAIL rises by 3.142, and
FSAR rises from 45.3% to 62.0%.

### 2. Manager coordination helps only when local capability is sufficient

Relative to async private, DeepSeek CAID recovers 5 successful tasks, raises
ADPR by 18.7 percentage points, and cuts CAIL by 2.368. This recovery costs
about 61% more tokens and 63% more runtime.

Gemma CAID raises partial test pass rate from 15.6% to 26.0%, but final success
and ADPR remain unchanged. It uses about 58% more tokens and 75% more runtime
than async private. A manager can reorganize work, but cannot compensate for
insufficient implementation and dependency-resolution capability.

### 3. Functional progress is not dependency closure

Gemma makes visible local progress: most task-protocol cells pass a nonzero
fraction of tests, and CAID reaches a 26.0% mean pass rate. Nevertheless, no
task is fully solved and only one of the 47 labeled dependencies is resolved
under each protocol on average. AsynCodeBench separates local coding progress
from successful producer-consumer integration.

### 4. Strong single-agent performance does not guarantee multi-agent gains

DeepSeek solves all tasks as a single agent, yet every multi-agent protocol
performs worse on final success. CAID recovers much of the loss, while naive
async private performs worst. More agents introduce coordination and
integration risks even when the base model is strong.

## Recommended Slide Narrative

1. **Traditional metrics hide coordination delay:** DeepSeek serial and async
   private have almost identical pass rate and ADPR, but CAIL nearly doubles.
2. **Parallel execution is faster, not automatically better:** both models
   obtain roughly 40-46% runtime reduction from async private while quality or
   coordination metrics degrade.
3. **Management is conditional, not universally beneficial:** CAID strongly
   helps DeepSeek but only improves partial progress for Gemma.
4. **AsynCodeBench explains failures below final success:** Gemma has a complete
   success-rate floor, yet ADPR, DRS, CAIL, FSAR, and SVR expose where the
   protocols differ.

## Reporting Limitations

- Each task-protocol cell has one run; no confidence intervals are available.
- DeepSeek raw bundles are not currently distributed as a validated public
  baseline, although the README records that all 64 selected runs passed
  admission checks.
- Gemma includes valid model-induced collection failures and evaluator
  timeouts; these remain failures rather than being discarded.
- Cross-model runtime, token, and cost comparisons are confounded by serving
  infrastructure and tokenizer differences.
- Protocol comparisons within each model are the strongest evidence.

## Sources

- DeepSeek aggregate: repository `README`, section `Initial DeepSeek V4 Flash
  Results`.
- Gemma aggregate: `docs/results/GEMMA4_26B_A4B_OH1292_RESULTS.md` and the 64
  selected local run bundles under
  `reproductions/async-swe-agents/outputs/asyncodebench/v0.3/gemma4-26b-a4b-v2/`.
