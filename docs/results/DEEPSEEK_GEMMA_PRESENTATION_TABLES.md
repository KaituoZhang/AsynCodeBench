# Presentation Tables: DeepSeek V4 Flash, Qwen3.6-27B, and Gemma 4 26B-A4B

## Presentation Figures

| Figure | Best use | PNG | PDF |
| --- | --- | --- | --- |
| Dependency and coordination profile | **Main benchmark figure:** ADPR, unresolved dependencies, DRS, and CAIL | [PNG](figures/asynccodebench_dependency_profile.png) | [PDF](figures/asynccodebench_dependency_profile.pdf) |
| Local-model coordination diagnostics | **Why final success is insufficient:** FSAR, IFR, SVR, and MRR | [PNG](figures/local_model_coordination_diagnostics.png) | [PDF](figures/local_model_coordination_diagnostics.pdf) |
| Async speed-quality tradeoff | Core asynchronous collaboration finding | [PNG](figures/async_speed_quality_tradeoff.png) | [PDF](figures/async_speed_quality_tradeoff.pdf) |
| Conventional outcomes | Supporting context only: success, pass rate, and ADPR | [PNG](figures/model_protocol_performance.png) | [PDF](figures/model_protocol_performance.pdf) |

Use PNG files in slides and PDF files in the paper or other vector-based
documents.

## Metric Key

| Metric | What it reveals | Direction |
| --- | --- | --- |
| ADPR | Fraction of labeled producer-consumer dependencies closed in the final integrated workspace | Higher |
| DRE | Checkpoint-normalized dependency-resolution efficiency | Higher |
| DRS | First integrated checkpoint at which a dependency is resolved | Lower |
| CAIL | Delay between producer availability and downstream consumer resolution | Lower |
| FSAR | Fraction of subagent attempts that fail to yield a usable artifact | Lower |
| IFR | Fraction of runs with merge, import, or semantic integration failure | Lower |
| SVR | Fraction of scoped attempts that modify files outside assigned ownership | Lower |
| MRR | Recovery among failed or repaired attempts | Conditional |

Strict `SAD/SAR` is not plotted because the current traces do not provide
complete dependency-version visibility. The available stale-assumption value
is a proxy and should remain a case-study diagnostic rather than a main
cross-protocol aggregate.

## Table 1. Core AsynCodeBench Dependency Metrics

| Model | Protocol | ADPR ↑ | Unresolved ↓ | DRE ↑ | Penalized DRS ↓ | Penalized CAIL ↓ |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| DeepSeek | Single | 100.0% | 0.000 | N/R | 1.000 | 0.000 |
| DeepSeek | Serial | 69.8% | 0.875 | N/R | 6.121 | 2.590 |
| DeepSeek | Async private | 69.8% | 0.875 | N/R | 7.131 | 5.037 |
| DeepSeek | CAID | 88.5% | 0.250 | N/R | 7.292 | 2.669 |
| Qwen | Single | 50.0% | 1.375 | 50.0% | 1.500 | 0.875 |
| Qwen | Serial | 51.0% | 1.375 | 22.1% | 6.579 | 4.131 |
| Qwen | Async private | 20.8% | 2.250 | 13.6% | 9.850 | 5.756 |
| Qwen | CAID | 95.8% | 0.125 | 23.1% | 8.131 | 2.902 |
| Gemma | Single | 1.3% | 2.875 | 1.25% | 1.988 | 1.975 |
| Gemma | Serial | 2.1% | 2.875 | 1.79% | 7.875 | 7.758 |
| Gemma | Async private | 1.3% | 2.875 | 1.07% | 10.925 | 10.900 |
| Gemma | CAID | 1.3% | 2.875 | 1.07% | 10.800 | 10.525 |

`N/R` means not reported in the DeepSeek README aggregate. DRS and CAIL use
the documented run-local `T + 1` penalty for unresolved dependencies.

## Table 2. Coordination Diagnostics

| Model | Protocol | FSAR ↓ | IFR ↓ | SVR ↓ | MRR† |
| --- | --- | ---: | ---: | ---: | ---: |
| DeepSeek | Single / Serial / Async / CAID | N/R | N/R | N/R | N/R |
| Qwen | Single | 0.0% | 0.0% | N/A | N/A |
| Qwen | Serial | 5.2% | 75.0% | 11.5% | 85.2% |
| Qwen | Async private | 17.7% | 87.5% | 31.8% | 40.9% |
| Qwen | CAID | 14.1% | 12.5% | 34.4% | 45.7% |
| Gemma | Single | 0.0% | 0.0% | N/A | N/A |
| Gemma | Serial | 45.3% | 100.0% | 27.6% | 54.7% |
| Gemma | Async private | 62.0% | 100.0% | 29.7% | 37.0% |
| Gemma | CAID | 52.2% | 100.0% | 36.3% | 45.1% |

† `MRR` is conditional on failure and must be read together with FSAR: a high
recovery rate is not evidence of a clean trajectory. DeepSeek diagnostics are
not reconstructed because its public README does not expose the raw fields.

## Table 3. What Traditional Metrics Hide

| Serial → Async private | Traditional view | AsynCodeBench view | Interpretation |
| --- | --- | --- | --- |
| DeepSeek | Pass: -0.2 pp | DRS: +1.010; CAIL: +2.447 | Nearly identical pass rate hides much later dependency integration |
| Qwen | Success: -12.5 pp; Pass: -12.8 pp | ADPR: -30.2 pp; DRS: +3.271; CAIL: +1.625; FSAR: +12.5 pp | Naive asynchrony damages both dependency closure and artifact reliability |
| Gemma | Success: 0.0 pp; Pass: -6.6 pp | DRS: +3.050; CAIL: +3.142; FSAR: +16.7 pp | Faster execution increases unresolved coordination burden |

Both async-private runs are about 40--46% faster than serial specialists. The
speedup is therefore real, but the Dependency Checker metrics show that it is
not free.

## Table 4. CAID Recovery Relative to Async Private

| Model | ADPR change ↑ | CAIL change ↓ | FSAR change ↓ | Tokens | Runtime |
| --- | ---: | ---: | ---: | ---: | ---: |
| DeepSeek | +18.7 pp | -2.368 | N/R | +61.1% | +63.2% |
| Qwen | +75.0 pp | -2.854 | -3.6 pp | +43.5% | +79.3% |
| Gemma | 0.0 pp | -0.375 | -9.8 pp | +58.0% | +74.9% |

CAID recovers dependency closure for DeepSeek. For Gemma it reduces failed
subagent attempts slightly, but does not improve ADPR and increases SVR.

## Table 5. Conventional Outcomes and Efficiency

| Model | Protocol | Success | Mean pass | Tokens | Runtime |
| --- | --- | ---: | ---: | ---: | ---: |
| DeepSeek | Single / Serial / Async / CAID | 100.0 / 62.5 / 50.0 / 81.3% | 99.0 / 75.0 / 74.8 / 92.2% | 1.685 / 3.696 / 4.004 / 6.452M | 15.2 / 38.1 / 20.8 / 33.9 min |
| Qwen | Single / Serial / Async / CAID | 37.5 / 25.0 / 12.5 / 87.5% | 59.8 / 57.5 / 44.6 / 96.3% | 4.702 / 7.615 / 7.576 / 10.872M | 67.3 / 133.2 / 109.5 / 196.3 min |
| Gemma | Single / Serial / Async / CAID | 0.0 / 0.0 / 0.0 / 0.0% | 22.2 / 22.2 / 15.6 / 26.0% | 0.554 / 3.106 / 3.073 / 4.855M | 12.8 / 44.3 / 26.5 / 46.3 min |

## One-Slide Takeaway

> Traditional success and pass rate do not reveal whether producer-consumer
> dependencies close on time. ADPR, DRS, CAIL, FSAR, IFR, and SVR show that
> asynchronous speedups can coexist with delayed integration, failed
> artifacts, and scope violations; CAID only recovers these losses when the
> underlying model is capable enough.

Qwen is a descriptive mixed-lineage aggregate: all 64 selected bundles are
individually valid and use the official standard-100 profile, but they span
four benchmark revisions and three generation-configuration hashes. Keep this
qualification visible until a lineage-homogeneous campaign is rerun.
