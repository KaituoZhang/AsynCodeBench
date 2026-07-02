# DeepSeek-V3.2 TinyDB Experiment Report

Task: `commit0:tinydb`

Model: `deepinfra/deepseek-ai/DeepSeek-V3.2`

Runner adapter: `deepseek_json_delegation_adapter`

Evaluation date: 2026-07-01

This report is a failure-structure case study, not a successful solve result. All DeepSeek-V3.2 TinyDB protocols fail final evaluation. The run is still useful because AsyncCodeBench metrics expose how asynchronous execution changes dependency progress, integration burden, and artifact hygiene compared with final tests alone.

## How to Read These Metrics

The tables below are not intended to be read as ordinary coding benchmark results only. Traditional metrics tell us whether the final repository passed tests, but AsyncCodeBench is designed to expose how asynchronous multi-agent work resolves, delays, duplicates, or breaks cross-agent dependencies.

### Traditional Coding Metrics

- **Final tests / Final pass**: how many evaluator tests pass in the final integrated repository. This answers whether the task was solved, but it does not explain how the agents coordinated.
- **Cost**: API/provider billing cost. In these DeepSeek runs, `cost.json` reports `0.0`, so billing-grade cost requires DeepInfra dashboard/provider logs.
- **Tokens**: total model input/output token accounting from `cost.json`. CAID token accounting is marked unavailable when provider accounting is incomplete or clearly implausible.
- **Runtime / wall-clock time**: end-to-end workflow time. This helps distinguish efficient resolution from slow recovery-heavy resolution.

### AsyncCodeBench Dependency Metrics

- **ADPR (Async Dependency Pass Rate)**: `resolved_dependency_points / total_dependency_points`. It asks how many labeled async dependency points are resolved.
- **Final-integrated ADPR**: ADPR computed from the final integrated workspace / final evaluator checkpoint. This is the canonical run-level ADPR for paper tables.
- **Mean per-agent-view ADPR**: mean ADPR across individual agent event-log views. This is diagnostic only. It can show local or partial progress, but it should not be reported as canonical run-level success.
- **DRS (Dependency Resolution Step)**: the first checkpoint or logical iteration where a dependency point is observed resolved.
- **Strict DRS**: upstream and downstream probes pass in the same integrated checkpoint. This is conservative and preferred for main claims.
- **Composed DRS**: `max(upstream_resolution_step, downstream_resolution_step)`. This is useful diagnostically when upstream and downstream are observed separately.
- **Upstream resolution**: when the producer-side contract becomes correct.
- **Downstream resolution**: when the consumer-side code correctly adapts to the producer contract.
- **CAIL (Cross-Agent Integration Lag)**: `downstream_resolution_step - upstream_resolution_step`. It asks how long the consumer lagged after the producer-side contract was available.
- **SAD / SAD-proxy (Stale Assumption Duration)**: duration where a downstream agent continues working from stale producer assumptions. Current logs only support proxy candidates unless structured artifact-visibility logs are available.

### Coordination Diagnostics

- **Subagent artifact failure count**: subagent attempts that did not produce a usable committed/merged artifact.
- **Merge failure count**: artifacts that could not be textually merged because of conflicts.
- **Semantic integration failure**: the final integrated workspace fails evaluator tests after merge/integration.
- **Artifact hygiene violation count**: temporary, backup, prototype, or out-of-repo files left in the final patch.
- **Manager recovery / review burden**: evidence that the final result required manager review, reassignment, merge repair, or final recovery rather than clean independent subagent success.
- **Async overlap**: wall-clock interval where two or more agents were active concurrently. This confirms whether a protocol actually exercised asynchronous execution.

## Targeted AsyncCodeBench Analysis

The `tinydb` run is a different failure structure from `cachetools`. It does not show a strong nonzero CAIL pattern. Instead, it shows local dependency progress that fails to become final integrated progress.

### What Traditional Metrics Say

All four modes fail final evaluation:

- `single`: 20/201, with 65 errors.
- `serial_specialists`: 51/201.
- `async_private`: 27/201.
- `CAID_multi`: 55/201.

Traditional metrics show severe task failure, but they do not explain whether any async dependency work made progress.

### What ADPR Reveals

Canonical final-integrated ADPR is 0.0 for every mode. This means none of the labeled TinyDB async dependency points are resolved in the final integrated evaluator view.

However, per-agent views reveal partial local progress:

- `serial_specialists`: query agent ADPR = 3/3, state agent ADPR = 0/3, mean = 0.5.
- `async_private`: query agent ADPR = 3/3, state agent ADPR = 0/3, mean = 0.5.
- `CAID_multi`: every agent view ADPR = 0/3.

This is a useful AsyncCodeBench signal: one side of the decomposition can appear locally resolved while the final integrated workspace remains unresolved.

### What DRS / CAIL Reveal

For `tinydb`, most CAIL values are unavailable rather than large. This is not empty information. It means the benchmark did not observe complete upstream/downstream resolution for those dependency views.

- `serial_specialists`: query-agent view has CAIL=0 for all three dependencies, but state-agent view has unresolved dependencies.
- `async_private`: query-agent view has CAIL=0 for all three dependencies, but state-agent view has unresolved dependencies.
- `CAID_multi`: CAIL observed = 0/9 and unresolved dependency views = 9.

So `tinydb` does not say "downstream lagged after upstream by many steps." It says "local query-layer dependency progress never integrated into the final state/database stack." That is still an async coordination failure, but a different one from cachetools.

### What Async Overlap Reveals

- `serial_specialists`: overlap = 0.0s
- `async_private`: overlap = 573.5s
- `CAID_multi`: overlap = 870.0s

The async runs really overlap, but final-integrated ADPR remains 0.0. In `async_private`, concurrency makes the result worse than serial by final tests: 27/201 vs 51/201.

### What Coordination Diagnostics Reveal

- `serial_specialists`: subagent artifact failures = 2, semantic integration failure = true.
- `async_private`: subagent artifact failures = 2, merge failure count = 1.
- `CAID_multi`: subagent artifact failures = 4, merge failure count = 1.

This shows that the asynchronous protocols do not merely fail because the underlying coding task is hard. They also fail through coordination channels: artifacts do not merge cleanly, subagent outputs are not usable, and local dependency progress does not become integrated dependency progress.

### TinyDB Claim

This run supports the following claim:

> On `tinydb`, final-integrated ADPR remains 0.0 despite local query-agent dependency progress in serial and async-private views. Async execution introduces real overlap but does not convert local dependency progress into integrated success, illustrating an integration failure mode distinct from the CAIL-heavy `cachetools` case.

## Metric-by-Metric Findings Against AsyncCodeBench Criteria

This section gives the targeted AsyncCodeBench interpretation. `tinydb` should not be read as a normal solve-rate result; it is mainly evidence about failed integration under decomposition.

### Final Pass / Final Tests

The traditional view says all modes fail, with `CAID_multi` highest at 55/201 and `serial_specialists` next at 51/201. That is useful, but it is not enough. It does not explain whether the multi-agent decomposition made partial progress, where that progress happened, or why it failed to become a final integrated solution.

### ADPR

The key result is that final-integrated ADPR is `0.0` for every mode. Under the canonical AsyncCodeBench view, none of the labeled TinyDB async dependencies are resolved in the final integrated workspace.

However, the per-agent views are not uniformly empty:

- `serial_specialists`: query agent ADPR = `3/3`, state agent ADPR = `0/3`
- `async_private`: query agent ADPR = `3/3`, state agent ADPR = `0/3`
- `CAID_multi`: all available agent views are `0/3`

This is the most important `tinydb` signal: local query-layer work can look dependency-complete while the final integrated system remains dependency-incomplete. That is exactly why AsyncCodeBench separates final-integrated ADPR from per-agent-view ADPR.

### DRS and CAIL

Unlike `cachetools`, `tinydb` is not a strong positive-CAIL case. The query-agent views resolve all three dependency probes at step 2 with `CAIL=0`, while the state-agent and CAID views mostly remain unresolved.

That means the failure mode is not "downstream eventually catches up after a long lag." The failure mode is "one side of the decomposition becomes locally consistent, but the other side and final integration never resolve the labeled dependencies."

### SAD / SAD-proxy

As with `cachetools`, strict SAD is not available without dependency-version visibility logs. The current `SAD-proxy=0` should not be over-interpreted. In `tinydb`, unresolved dependency views and the final-integrated ADPR gap are stronger evidence than SAD-proxy.

### Failed Subagents, Merge, and Integration Diagnostics

The multi-agent protocols show coordination burden even though no mode solves the task:

- `serial_specialists`: subagent artifact failures = `2`, semantic integration failure = `true`
- `async_private`: subagent artifact failures = `2`, merge failures = `1`
- `CAID_multi`: subagent artifact failures = `4`, merge failures = `1`

This matters because it separates "model did not solve TinyDB" from "the async protocol produced unusable or hard-to-integrate artifacts." Those are different failure explanations.

### Manager Recovery / Integration Burden

`tinydb` shows that CAID-style decomposition does not automatically improve integration. CAID has the highest final test count in this DeepSeek run, but it also has more failed artifacts and no per-agent dependency-resolution signal under the current analyzer. This should be reported as recovery-heavy and integration-limited, not as clean CAID success.

### Scope and Boundary Interpretation

No artifact hygiene violations are retained in the current TinyDB accounting, so this case should not be used as the main scope/hygiene example. Use `cachetools` for artifact hygiene, and use `tinydb` for the local-progress-versus-final-integration gap.

### Bottom Line for TinyDB

`tinydb` supports the AsyncCodeBench thesis through a different failure mode from `cachetools`: final-integrated ADPR stays at 0.0, while serial and async-private query agents show local ADPR of 1.0. The async issue is not mainly lag; it is failure to integrate local dependency progress into the final database-state stack.


## Async Coordination Metrics

This is the main AsyncCodeBench view. It separates actual concurrency, dependency-resolution lag, stale/missing-communication proxies, and integration burden from traditional final test counts.

| Mode | Async overlap | Final-integrated ADPR | Mean per-agent ADPR | CAIL observed | CAIL max | CAIL mean | Nonzero CAIL | Unresolved dep views | DRS observed | SAD-proxy | Missing-comm proxy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| single | 0.0s | 0.0 | 0.0 | 0/3 | N/A | N/A | 0 | 3 | 0 | 0 | 0 |
| serial_specialists | 0.0s | 0.0 | 0.5 | 3/6 | 0 | 0.0 | 0 | 3 | 3 | 0 | 0 |
| async_private | 573.5s | 0.0 | 0.5 | 3/6 | 0 | 0.0 | 0 | 3 | 3 | 0 | 0 |
| CAID_multi | 870.0s | 0.0 | 0.0 | 0/9 | N/A | N/A | 0 | 9 | 0 | 0 | 0 |

Per-report CAIL summaries:

- `single`: async_dependency_resolution_single_agent_events.json: no observed CAIL, unresolved=3
- `serial_specialists`: async_dependency_resolution_query_agent_events.json: CAIL max=0, nonzero=0, unresolved=0; async_dependency_resolution_state_agent_events.json: no observed CAIL, unresolved=3
- `async_private`: async_dependency_resolution_query_agent_events.json: CAIL max=0, nonzero=0, unresolved=0; async_dependency_resolution_state_agent_events.json: no observed CAIL, unresolved=3
- `CAID_multi`: async_dependency_resolution_engineer_1_events.json: no observed CAIL, unresolved=3; async_dependency_resolution_engineer_2_events.json: no observed CAIL, unresolved=3; async_dependency_resolution_manager_events.json: no observed CAIL, unresolved=3

Interpretation notes:

- `tinydb` shows real asynchronous overlap, but final-integrated ADPR remains 0.0 for every protocol.
- The per-agent query-layer views can look solved while the final integrated workspace remains unresolved. This is an async coordination/integration failure pattern, even when CAIL is mostly 0 or unavailable.
- Missing CAIL values are meaningful here: they indicate dependencies that never reached a complete upstream/downstream resolution in that event-log view.

## Canonical Metrics Table

ADPR convention: `final_integrated_ADPR` is the canonical run-level dependency score computed from the final evaluator checkpoint. `mean_per_agent_view_ADPR` is diagnostic only and averages ADPR across agent event-log views.

| Mode | Final tests | Errors | Skipped | Final success | Final-integrated ADPR | Mean per-agent-view ADPR | FSR | Subagent artifact failures | Merge failures | Semantic integration failure | Hygiene violations | Async overlap | Runtime | Tokens |
| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| single | 20/201 | 65 | 1 | false | 0.0 | 0.0 | 0.0 | 0 | 0 | false | 0 | 0.0s | 603.4s | 739263 |
| serial_specialists | 51/201 | 0 | 1 | false | 0.0 | 0.5 | 0.0 | 2 | 0 | true | 0 | 0.0s | 1441.4s | 1690412 |
| async_private | 27/201 | 0 | 1 | false | 0.0 | 0.5 | 0.0 | 2 | 1 | false | 0 | 573.5s | 692.8s | 1578186 |
| CAID_multi | 55/201 | 0 | 1 | false | 0.0 | 0.0 | 0.0 | 4 | 1 | false | 0 | 870.0s | 4929.5s | unavailable |

## ADPR Interpretation

- `final_integrated_ADPR`: ADPR computed from the final integrated workspace / final evaluator checkpoint. Use this in main paper tables.
- `mean_per_agent_view_ADPR`: mean ADPR across agent event-log views. Use this as a diagnostic, not as canonical run-level ADPR.

| Mode | Final-integrated ADPR | Mean per-agent-view ADPR | Per-agent-view ADPR |
| --- | ---: | ---: | --- |
| single | 0.0 | 0.0 | async_dependency_resolution_single_agent_events.json=0/3=0.0 |
| serial_specialists | 0.0 | 0.5 | async_dependency_resolution_query_agent_events.json=3/3=1.0; async_dependency_resolution_state_agent_events.json=0/3=0.0 |
| async_private | 0.0 | 0.5 | async_dependency_resolution_query_agent_events.json=3/3=1.0; async_dependency_resolution_state_agent_events.json=0/3=0.0 |
| CAID_multi | 0.0 | 0.0 | async_dependency_resolution_engineer_1_events.json=0/3=0.0; async_dependency_resolution_engineer_2_events.json=0/3=0.0; async_dependency_resolution_manager_events.json=0/3=0.0 |

## Failed Attempt / Integration Metrics

| Mode | Subagent artifact failures | Merge failures | Semantic integration failure |
| --- | ---: | ---: | --- |
| single | 0 | 0 | false |
| serial_specialists | 2 | 0 | true |
| async_private | 2 | 1 | false |
| CAID_multi | 4 | 1 | false |

## Artifact Hygiene

Definition: `artifact_hygiene_violation_count` is the number of generated temporary, backup, prototype, or out-of-repo files left in the final patch.

| Mode | Violation count | Files |
| --- | ---: | --- |
| single | 0 | None |
| serial_specialists | 0 | None |
| async_private | 0 | None |
| CAID_multi | 0 | None |

## Dependency-Level DRS / CAIL Details

`N/A` means a complete dependency resolution was not observed for that dependency point in that event-log view.

### single

Report: `async_dependency_resolution_single_agent_events.json`; ADPR: `0/3 = 0.0`

| Dependency | DRS | Upstream | Downstream | CAIL | Composed DRS |
| --- | ---: | ---: | ---: | ---: | ---: |
| `query_to_table.search_cache_contract` | N/A | N/A | N/A | N/A | N/A |
| `operations_to_table.update_transform_contract` | N/A | N/A | 2 | N/A | N/A |
| `state_stack.shared_mapping_contract` | N/A | N/A | N/A | N/A | N/A |

### serial_specialists

Report: `async_dependency_resolution_query_agent_events.json`; ADPR: `3/3 = 1.0`

| Dependency | DRS | Upstream | Downstream | CAIL | Composed DRS |
| --- | ---: | ---: | ---: | ---: | ---: |
| `query_to_table.search_cache_contract` | 2 | 2 | 2 | 0 | 2 |
| `operations_to_table.update_transform_contract` | 2 | 2 | 2 | 0 | 2 |
| `state_stack.shared_mapping_contract` | 2 | 2 | 2 | 0 | 2 |

Report: `async_dependency_resolution_state_agent_events.json`; ADPR: `0/3 = 0.0`

| Dependency | DRS | Upstream | Downstream | CAIL | Composed DRS |
| --- | ---: | ---: | ---: | ---: | ---: |
| `query_to_table.search_cache_contract` | N/A | N/A | N/A | N/A | N/A |
| `operations_to_table.update_transform_contract` | N/A | N/A | N/A | N/A | N/A |
| `state_stack.shared_mapping_contract` | N/A | N/A | N/A | N/A | N/A |

### async_private

Report: `async_dependency_resolution_query_agent_events.json`; ADPR: `3/3 = 1.0`

| Dependency | DRS | Upstream | Downstream | CAIL | Composed DRS |
| --- | ---: | ---: | ---: | ---: | ---: |
| `query_to_table.search_cache_contract` | 2 | 2 | 2 | 0 | 2 |
| `operations_to_table.update_transform_contract` | 2 | 2 | 2 | 0 | 2 |
| `state_stack.shared_mapping_contract` | 2 | 2 | 2 | 0 | 2 |

Report: `async_dependency_resolution_state_agent_events.json`; ADPR: `0/3 = 0.0`

| Dependency | DRS | Upstream | Downstream | CAIL | Composed DRS |
| --- | ---: | ---: | ---: | ---: | ---: |
| `query_to_table.search_cache_contract` | N/A | N/A | N/A | N/A | N/A |
| `operations_to_table.update_transform_contract` | N/A | N/A | N/A | N/A | N/A |
| `state_stack.shared_mapping_contract` | N/A | N/A | N/A | N/A | N/A |

### CAID_multi

Report: `async_dependency_resolution_engineer_1_events.json`; ADPR: `0/3 = 0.0`

| Dependency | DRS | Upstream | Downstream | CAIL | Composed DRS |
| --- | ---: | ---: | ---: | ---: | ---: |
| `query_to_table.search_cache_contract` | N/A | N/A | N/A | N/A | N/A |
| `operations_to_table.update_transform_contract` | N/A | N/A | N/A | N/A | N/A |
| `state_stack.shared_mapping_contract` | N/A | N/A | N/A | N/A | N/A |

Report: `async_dependency_resolution_engineer_2_events.json`; ADPR: `0/3 = 0.0`

| Dependency | DRS | Upstream | Downstream | CAIL | Composed DRS |
| --- | ---: | ---: | ---: | ---: | ---: |
| `query_to_table.search_cache_contract` | N/A | N/A | N/A | N/A | N/A |
| `operations_to_table.update_transform_contract` | N/A | N/A | N/A | N/A | N/A |
| `state_stack.shared_mapping_contract` | N/A | N/A | N/A | N/A | N/A |

Report: `async_dependency_resolution_manager_events.json`; ADPR: `0/3 = 0.0`

| Dependency | DRS | Upstream | Downstream | CAIL | Composed DRS |
| --- | ---: | ---: | ---: | ---: | ---: |
| `query_to_table.search_cache_contract` | N/A | N/A | N/A | N/A | N/A |
| `operations_to_table.update_transform_contract` | N/A | N/A | N/A | N/A | N/A |
| `state_stack.shared_mapping_contract` | N/A | N/A | N/A | N/A | N/A |

## Cost and Token Accounting

- Token/cost values come from `cost.json` where available, but billing-grade costs should be verified against DeepInfra dashboard/provider logs.
- If provider accounting is incomplete, use `unavailable due to incomplete provider accounting` in paper cost tables.

## Raw Artifact Index

Raw run directories are indexed in `tinydb_deepseek_v32_artifact_index.json`. Each run has per-file SHA-256 checksums and a combined checksum over the indexed artifacts. Raw artifact directories are retained under WSL:

- `single`: `reproductions/async-swe-agents/outputs/repro_commit0/tinydb/deepseek_v32_single_i30`
- `serial_specialists`: `reproductions/async-swe-agents/outputs/repro_commit0/tinydb/deepseek_v32_serial_2agents_s30`
- `async_private`: `reproductions/async-swe-agents/outputs/repro_commit0/tinydb/deepseek_v32_async_private_2agents_s30`
- `CAID_multi`: `reproductions/async-swe-agents/outputs/repro_commit0/tinydb/deepseek_v32_caid_multi_2agents_m30_s30`

## Final Conclusion

All DeepSeek-V3.2 TinyDB protocols fail final evaluation. The final test scores show that serial_specialists and CAID_multi perform better than single and async_private, but no mode solves the task. The AsyncCodeBench metrics should be used as failure-structure evidence: they separate final-integrated dependency progress from per-agent views, expose asynchronous overlap, and distinguish subagent artifact failures, merge failures, semantic integration failures, and artifact hygiene issues.

This TinyDB result is best reported alongside cachetools as another model-sensitivity and asynchronous-coordination failure case rather than as a successful solve-rate result.

## Reproduction Command

```bash
cd ~/AsynccodeBench/Asynccodebench
METRICS=manifests/pilot/v0.3/metrics/commit0_tinydb_async_metrics.json
for RUN in   reproductions/async-swe-agents/outputs/repro_commit0/tinydb/deepseek_v32_single_i30   reproductions/async-swe-agents/outputs/repro_commit0/tinydb/deepseek_v32_serial_2agents_s30   reproductions/async-swe-agents/outputs/repro_commit0/tinydb/deepseek_v32_async_private_2agents_s30   reproductions/async-swe-agents/outputs/repro_commit0/tinydb/deepseek_v32_caid_multi_2agents_m30_s30
do
  for EVENTS in "$RUN"/agent_events/*.jsonl
  do
    [ -e "$EVENTS" ] || continue
    NAME=$(basename "$EVENTS" .jsonl)
    PYTHONPATH=src python3 scripts/analyze_async_dependency_resolution.py       --metrics "$METRICS"       --events "$EVENTS"       --final-test-output "$RUN/tinydb_test_output.txt"       --output "$RUN/async_dependency_resolution_${NAME}.json"
  done
  PYTHONPATH=src python3 scripts/analyze_async_dependency_resolution.py     --metrics "$METRICS"     --events /tmp/asynccodebench_empty_events.jsonl     --final-test-output "$RUN/tinydb_test_output.txt"     --final-logical-iteration 0     --output "$RUN/async_dependency_resolution_final_integrated.json"
  PYTHONPATH=src python3 scripts/analyze_run_process_metrics.py     --run-dir "$RUN"     --metrics "$METRICS"     --output "$RUN/process_metrics_summary.json"     --print-summary
done
```
