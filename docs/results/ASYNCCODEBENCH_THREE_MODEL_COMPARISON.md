# Three-Model Comparison on AsynCodeBench

## Scope

This report compares DeepSeek V4 Flash, Qwen3.6-27B, and Gemma 4 26B-A4B over
the 16 official tasks and four protocols. All values are task-macro averages.

| Model | Serving | Selected runs | Run admission | Campaign status |
| --- | --- | ---: | --- | --- |
| DeepSeek V4 Flash | Hosted API | 64 | README reports all bundles admitted | Initial snapshot; raw bundles not distributed |
| Qwen3.6-27B | Local vLLM | 64 | 64/64 bundles individually valid | Descriptive mixed lineage |
| Gemma 4 26B-A4B | Local vLLM | 64 | 64/64 bundles individually valid | Valid standard-100 baseline |

Qwen uses the official `asyncodebench-v0.3-standard-100` profile throughout,
but its selected runs span four benchmark revisions and three generation
configuration hashes. It is suitable for descriptive comparison and figures,
not yet for a lineage-homogeneous official campaign claim.

## Core Dependency Metrics

| Model | Protocol | Success | Pass | ADPR ↑ | Unresolved ↓ | DRE ↑ | DRS ↓ | CAIL ↓ |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DeepSeek | Single | 100.0% | 99.0% | 100.0% | 0.000 | N/R | 1.000 | 0.000 |
| DeepSeek | Serial | 62.5% | 75.0% | 69.8% | 0.875 | N/R | 6.121 | 2.590 |
| DeepSeek | Async private | 50.0% | 74.8% | 69.8% | 0.875 | N/R | 7.131 | 5.037 |
| DeepSeek | CAID | 81.3% | 92.2% | 88.5% | 0.250 | N/R | 7.292 | 2.669 |
| Qwen | Single | 37.5% | 59.8% | 50.0% | 1.375 | 50.0% | 1.500 | 0.875 |
| Qwen | Serial | 25.0% | 57.5% | 51.0% | 1.375 | 22.1% | 6.579 | 4.131 |
| Qwen | Async private | 12.5% | 44.6% | 20.8% | 2.250 | 13.6% | 9.850 | 5.756 |
| Qwen | CAID | 87.5% | 96.3% | 95.8% | 0.125 | 23.1% | 8.131 | 2.902 |
| Gemma | Single | 0.0% | 22.2% | 1.3% | 2.875 | 1.25% | 1.988 | 1.975 |
| Gemma | Serial | 0.0% | 22.2% | 2.1% | 2.875 | 1.79% | 7.875 | 7.758 |
| Gemma | Async private | 0.0% | 15.6% | 1.3% | 2.875 | 1.07% | 10.925 | 10.900 |
| Gemma | CAID | 0.0% | 26.0% | 1.3% | 2.875 | 1.07% | 10.800 | 10.525 |

## Coordination Diagnostics for Local Models

| Model | Protocol | FSAR ↓ | IFR ↓ | SVR ↓ | MRR† |
| --- | --- | ---: | ---: | ---: | ---: |
| Qwen | Serial | 5.2% | 75.0% | 11.5% | 85.2% |
| Qwen | Async private | 17.7% | 87.5% | 31.8% | 40.9% |
| Qwen | CAID | 14.1% | 12.5% | 34.4% | 45.7% |
| Gemma | Serial | 45.3% | 100.0% | 27.6% | 54.7% |
| Gemma | Async private | 62.0% | 100.0% | 29.7% | 37.0% |
| Gemma | CAID | 52.2% | 100.0% | 36.3% | 45.1% |

† MRR is conditional on failed or repaired attempts. A high MRR does not imply
a clean trajectory and must be interpreted with FSAR.

## Main Findings

1. **Naive asynchrony is consistently risky.** Async private is faster than
   serial for all three models, but it increases CAIL in every case. For Qwen,
   it also reduces ADPR from 51.0% to 20.8% and raises FSAR from 5.2% to 17.7%.
2. **CAID can produce a large recovery when the model can use coordination.**
   Qwen CAID reaches 14/16 success and 95.8% ADPR, compared with 2/16 and 20.8%
   for async private. DeepSeek shows the same direction, though less strongly.
3. **Management cannot replace implementation capability.** Gemma CAID raises
   partial test pass to 26.0%, but success and ADPR remain at the floor.
4. **Traditional metrics conceal process quality.** Qwen CAID has excellent
   final outcomes but still has a 34.4% scope-violation rate and uses 10.9M
   tokens per task on average. AsynCodeBench exposes this cost and coordination
   burden rather than treating all successful trajectories as equivalent.
5. **DRS must be read with DRE and ADPR.** CAID creates more checkpoints, so its
   raw penalized DRS can be larger even when almost all dependencies eventually
   close. DRE supplies the checkpoint-normalized timing view.

## Sources

- Qwen selection: `qwen36_27_selected_runs.json`
- Qwen per-run data: `qwen36_27_standard100_per_run.csv`
- Qwen protocol aggregate: `qwen36_27_standard100_summary_by_protocol.csv`
- Three-model plotting data: `asynccodebench_three_model_comparison.csv`
