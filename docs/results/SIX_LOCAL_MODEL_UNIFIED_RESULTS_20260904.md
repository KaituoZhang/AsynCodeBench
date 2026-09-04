# Six-Model AsynCodeBench Result Audit

Audit date: 2026-09-04.

The completed OpenRouter TVM-only campaign is analyzed separately in
[`TVM_FOUR_TASK_MODEL_ANALYSIS_20260904.md`](TVM_FOUR_TASK_MODEL_ANALYSIS_20260904.md).
It is not inserted into the 20-task aggregate below because OpenRouter was run
only on the four TVM tasks; treating 16 TVM cells as an 80-cell campaign would
produce an unmatched model comparison.

## Scope and selection

This report consolidates the available results for six locally served models
over the unified 20-task AsynCodeBench suite and its four execution
conditions. Each reported value is a task-macro average over one selected run
per available task--protocol cell.

| Model | Selected cells | Coverage | Recorded admission | Selection note |
| --- | ---: | --- | --- | --- |
| Qwen3.6-27B | 80 | 20/20 tasks, four protocols | 80/80 valid; 64 core cells marked aggregate-eligible, 16 extension cells retain their pre-promotion eligibility snapshot | Frozen index `qwen36_27_frozen_result_index.v1.json` |
| Gemma-4-26B-A4B | 64 | 16/20 tasks, four protocols | 64/64 valid and eligible | Validated standard-100 campaign; the four extension tasks were not run |
| Muse-Glimmer-30B | 80 | 20/20 tasks, four protocols | 80/80 valid and eligible | One unique valid cell per task and protocol |
| Qwen3-Coder-Next-FP8 | 80 | 20/20 tasks, four protocols | 80/80 valid and eligible | One unique valid cell per task and protocol, including recorded infrastructure retries |
| NVIDIA Nemotron-3.5-Lightning-30B-A3B-BF16 | 77 | 20/20 Single; 19/20 for each multi-agent protocol | 77/77 valid and eligible | Missing `apache-tvm-20018` Serial, Async private, and CAID cells |
| GLM-4.7-Flash | 80 | 20/20 tasks, four protocols | 80/80 valid and eligible | The invalid `simpy/caid_manager` v02 attempt is excluded in favor of its valid v03 retry |

The selected 77 extension-task cells were rechecked with the current run-health
auditor and all passed. The Qwen extension bundles preserve
`official_aggregate=false` because that field was frozen before the four tasks
were promoted; this historical metadata flag is not silently rewritten.

## Manager-policy qualification

The campaigns below predate commit `9682579`, which enforced a read-only CAID
manager for every official task. Their manager-mediated condition must
therefore be reported as **CAID+Repair (historical)**, not as the current
primary **CAID-RO** condition. In CAID+Repair the manager could author repairs
in the integrated repository. The Qwen frozen campaign contains one documented
task-specific read-only exception, `apache-tvm-20018`.

This qualification does not invalidate Single, Serial, or Async-private
outcomes. It does mean that the large Qwen CAID+Repair gain cannot be presented
as evidence for a read-only coordination manager.

## Primary dependency and functional outcomes

Macro ADPR gives every task equal weight. Micro ADPR pools dependency edges.
DRS-P and CAIL-P apply the run-local unresolved-dependency penalty; lower is
better. DRE is checkpoint-normalized; higher is better.

| Model | Protocol | Cells | FSR | Pass | Macro ADPR | Micro ADPR | Unresolved/task | DRE | DRS-P | CAIL-P |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.6-27B | Single | 20 | 6/20 (30.0%) | 59.2% | 40.0% | 45.5% | 1.50 | 40.0% | 1.60 | 1.05 |
| Qwen3.6-27B | Serial | 20 | 5/20 (25.0%) | 61.5% | 45.8% | 49.1% | 1.40 | 19.8% | 6.71 | 4.25 |
| Qwen3.6-27B | Async private | 20 | 2/20 (10.0%) | 51.9% | 19.2% | 21.8% | 2.15 | 12.7% | 9.90 | 6.41 |
| Qwen3.6-27B | CAID+Repair | 20 | 14/20 (70.0%) | 93.2% | 76.7% | 81.8% | 0.50 | 18.4% | 8.90 | 3.90 |
| Gemma-4-26B-A4B | Single | 16 | 0/16 (0.0%) | 21.8% | 1.2% | 2.1% | 2.88 | 1.2% | 1.99 | 1.83 |
| Gemma-4-26B-A4B | Serial | 16 | 0/16 (0.0%) | 21.8% | 2.1% | 2.1% | 2.88 | 1.8% | 7.88 | 7.53 |
| Gemma-4-26B-A4B | Async private | 16 | 0/16 (0.0%) | 15.6% | 1.2% | 2.1% | 2.88 | 1.1% | 10.93 | 10.66 |
| Gemma-4-26B-A4B | CAID+Repair | 16 | 0/16 (0.0%) | 25.6% | 1.2% | 2.1% | 2.88 | 1.1% | 10.80 | 10.08 |
| Muse-Glimmer-30B | Single | 20 | 1/20 (5.0%) | 46.1% | 19.3% | 20.0% | 2.20 | 19.3% | 1.81 | 1.44 |
| Muse-Glimmer-30B | Serial | 20 | 2/20 (10.0%) | 48.0% | 15.0% | 18.2% | 2.25 | 6.1% | 7.48 | 6.08 |
| Muse-Glimmer-30B | Async private | 20 | 0/20 (0.0%) | 35.8% | 6.0% | 7.3% | 2.55 | 4.3% | 10.66 | 10.02 |
| Muse-Glimmer-30B | CAID+Repair | 20 | 2/20 (10.0%) | 44.1% | 15.8% | 20.0% | 2.20 | 5.8% | 11.53 | 9.60 |
| Qwen3-Coder-Next-FP8 | Single | 20 | 3/20 (15.0%) | 48.6% | 29.2% | 32.7% | 1.85 | 29.2% | 1.71 | 1.27 |
| Qwen3-Coder-Next-FP8 | Serial | 20 | 0/20 (0.0%) | 34.2% | 6.7% | 7.3% | 2.55 | 2.7% | 7.77 | 4.07 |
| Qwen3-Coder-Next-FP8 | Async private | 20 | 0/20 (0.0%) | 33.1% | 3.3% | 3.6% | 2.65 | 1.9% | 10.87 | 7.70 |
| Qwen3-Coder-Next-FP8 | CAID+Repair | 20 | 1/20 (5.0%) | 27.2% | 7.7% | 9.1% | 2.50 | 10.2% | 12.37 | 6.40 |
| NVIDIA Nemotron-3.5-Lightning-30B-A3B-BF16 | Single | 20 | 0/20 (0.0%) | 28.4% | 1.0% | 1.8% | 2.70 | 1.0% | 1.99 | 1.77 |
| NVIDIA Nemotron-3.5-Lightning-30B-A3B-BF16 | Serial | 19 | 0/19 (0.0%) | 28.9% | 0.0% | 0.0% | 2.79 | 0.0% | 8.00 | 7.08 |
| NVIDIA Nemotron-3.5-Lightning-30B-A3B-BF16 | Async private | 19 | 0/19 (0.0%) | 28.3% | 1.1% | 1.9% | 2.74 | 0.9% | 10.94 | 10.13 |
| NVIDIA Nemotron-3.5-Lightning-30B-A3B-BF16 | CAID+Repair | 19 | 0/19 (0.0%) | 28.2% | 0.0% | 0.0% | 2.79 | 4.7% | 12.00 | 10.83 |
| GLM-4.7-Flash | Single | 20 | 0/20 (0.0%) | 44.5% | 1.0% | 1.8% | 2.70 | 1.0% | 1.99 | 1.80 |
| GLM-4.7-Flash | Serial | 20 | 0/20 (0.0%) | 34.3% | 8.3% | 9.1% | 2.50 | 4.1% | 7.57 | 6.58 |
| GLM-4.7-Flash | Async private | 20 | 0/20 (0.0%) | 26.8% | 0.0% | 0.0% | 2.75 | 0.0% | 11.00 | 10.06 |
| GLM-4.7-Flash | CAID+Repair | 20 | 0/20 (0.0%) | 31.7% | 5.0% | 5.5% | 2.60 | 2.2% | 11.93 | 10.69 |

## Coordination and resource diagnostics

| Model | Protocol | FSAR | IFR | SVR | MRR | Tokens | Runtime |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.6-27B | Single | 0.0% | 0.0% | N/A | N/A | 5.000M | 65.0 min |
| Qwen3.6-27B | Serial | 9.2% | 75.0% | 12.5% | 78.2% | 8.127M | 136.9 min |
| Qwen3.6-27B | Async private | 25.8% | 90.0% | 33.8% | 30.0% | 7.889M | 102.3 min |
| Qwen3.6-27B | CAID+Repair | 24.2% | 30.0% | 35.5% | 35.5% | 12.221M | 191.8 min |
| Gemma-4-26B-A4B | Single | 0.0% | 0.0% | N/A | N/A | 0.554M | 12.8 min |
| Gemma-4-26B-A4B | Serial | 45.3% | 100.0% | 27.6% | 54.7% | 3.106M | 44.3 min |
| Gemma-4-26B-A4B | Async private | 62.0% | 100.0% | 29.7% | 37.0% | 3.073M | 26.5 min |
| Gemma-4-26B-A4B | CAID+Repair | 52.2% | 100.0% | 36.3% | 45.1% | 4.855M | 46.3 min |
| Muse-Glimmer-30B | Single | 0.0% | 0.0% | N/A | N/A | 4.803M | 24.7 min |
| Muse-Glimmer-30B | Serial | 55.4% | 90.0% | 12.9% | 39.0% | 8.131M | 66.0 min |
| Muse-Glimmer-30B | Async private | 68.3% | 100.0% | 6.7% | 29.2% | 7.812M | 27.8 min |
| Muse-Glimmer-30B | CAID+Repair | 66.7% | 90.0% | 10.9% | 25.0% | 15.278M | 58.2 min |
| Qwen3-Coder-Next-FP8 | Single | 0.0% | 0.0% | N/A | N/A | 4.694M | 11.7 min |
| Qwen3-Coder-Next-FP8 | Serial | 83.8% | 100.0% | 52.1% | 11.2% | 9.220M | 21.2 min |
| Qwen3-Coder-Next-FP8 | Async private | 71.7% | 100.0% | 43.8% | 25.8% | 8.542M | 13.8 min |
| Qwen3-Coder-Next-FP8 | CAID+Repair | 84.1% | 95.0% | 54.7% | 10.2% | 17.545M | 35.5 min |
| NVIDIA Nemotron-3.5-Lightning-30B-A3B-BF16 | Single | 0.0% | 0.0% | N/A | N/A | 5.692M | 9.5 min |
| NVIDIA Nemotron-3.5-Lightning-30B-A3B-BF16 | Serial | 69.7% | 100.0% | 56.6% | 29.4% | 10.073M | 25.6 min |
| NVIDIA Nemotron-3.5-Lightning-30B-A3B-BF16 | Async private | 67.5% | 100.0% | 60.5% | 27.2% | 9.993M | 16.8 min |
| NVIDIA Nemotron-3.5-Lightning-30B-A3B-BF16 | CAID+Repair | 68.1% | 100.0% | 45.4% | 24.1% | 16.523M | 38.7 min |
| GLM-4.7-Flash | Single | 0.0% | 0.0% | N/A | N/A | 3.548M | 13.1 min |
| GLM-4.7-Flash | Serial | 69.6% | 100.0% | 47.9% | 29.6% | 6.459M | 32.7 min |
| GLM-4.7-Flash | Async private | 81.2% | 100.0% | 56.7% | 18.8% | 6.518M | 24.3 min |
| GLM-4.7-Flash | CAID+Repair | 75.3% | 100.0% | 48.5% | 23.9% | 12.474M | 42.1 min |

MRR is conditional on observed failure/recovery opportunities. Single-agent
SVR and MRR are not applicable. Local serving makes API cost zero, so tokens
and runtime are the useful resource measures. Runtime is descriptive because
server versions, GPU layouts, and serving concurrency were not identical
across models.

## Current CAID-RO evidence

The current read-only policy has 13 completed Qwen3.6 core-task cells:

| Condition | Completed cells | FSR | Pass | Macro ADPR | FSAR | IFR | SVR | Tokens | Runtime |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.6 CAID-RO | 13/20 | 0/13 | 38.7% | 14.1% | 27.1% | 100.0% | 38.8% | 13.164M | 158.7 min |

This is incomplete and covers a different task subset, so it must not be used
as a matched numerical contrast against the 20-cell CAID+Repair row. The
missing CAID-RO cells are `cachetools`, `deprecated`, `wcwidth`, and all four
extension tasks.

## Main findings

1. Qwen3.6 is the only model in these campaigns with substantial full-task and
   dependency closure. Its 14/20 CAID+Repair result demonstrates the value of
   manager-authored repair, not the effectiveness of the current read-only
   manager.
2. Async private is never the strongest quality condition for any of the six
   models. It is usually faster than Serial, but generally has lower ADPR and
   more unresolved dependencies, exposing the expected coordination penalty.
3. Qwen3-Coder-Next is substantially better as a single agent (3/20, 29.2%
   ADPR) than under the three multi-agent conditions. Its high FSAR and SVR
   show that decomposition and merge overhead dominate its available coding
   capability in this harness.
4. Muse-Glimmer makes useful partial progress and solves up to 2/20 tasks, but
   neither Serial nor CAID+Repair improves dependency closure over Single.
5. Gemma, Nemotron, and GLM show a final-success floor. GLM has relatively high
   partial test pass (44.5% under Single) and its Serial run reaches 8.3% macro
   ADPR, but it does not complete a full task. Partial pass must not be
   interpreted as final benchmark success.
6. Across the four extension tasks, the only full success among these selected
   campaigns is Qwen3.6 on `apache-tvm-20018` under Serial. This indicates that
   the extension tier is substantially harder and prevents ceiling effects.
7. The benchmark is discriminative, but these are one-seed descriptive runs.
   They support mechanism and failure-mode analysis, not seed-level
   significance claims or a pure model-speed ranking.

## Paper-use decision

- Use Single, Serial, and Async-private rows as descriptive six-model results,
  retaining the coverage caveats for Gemma and Nemotron.
- Put the historical manager-mediated rows in the **CAID+Repair ablation**
  table.
- Do not use those rows as the paper's primary **CAID-RO** result.
- Complete the seven missing Qwen CAID-RO cells and run CAID-RO for the other
  models before making a six-model claim about the primary read-only manager.
- For a fully matched 20-task model comparison, run the 16 missing Gemma
  extension cells and the three missing Nemotron cells.

## Evidence locations

- Qwen frozen selection:
  `docs/results/qwen36_27_frozen_result_index.v1.json`
- Gemma validated report:
  `docs/results/GEMMA4_26B_A4B_OH1292_RESULTS.md`
- Historical manager-policy archive:
  `ablations/caid_manager_repair_v1/`
- Core run bundles:
  `reproductions/async-swe-agents/outputs/asyncodebench/v0.3/`
- Extension run bundles:
  `reproductions/async-swe-agents/outputs/pr_hard/v0.4/`
