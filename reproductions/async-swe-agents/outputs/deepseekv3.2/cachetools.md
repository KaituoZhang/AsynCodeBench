# DeepSeek-V3.2 Cachetools Experiment Report

Task: `commit0:cachetools`

Model: `deepinfra/deepseek-ai/DeepSeek-V3.2`

Runner adapter: `deepseek_json_delegation_adapter`

Evaluation date: 2026-07-01

This report is a failure-structure case study, not a successful solve result. All DeepSeek-V3.2 cachetools protocols fail final evaluation. The value of this run is that AsyncCodeBench metrics reveal asynchronous coordination failure structures that final scores alone hide.

## Canonical Metrics Table

ADPR convention: `final_integrated_ADPR` is the canonical run-level dependency score computed from the final evaluator checkpoint. `mean_per_agent_view_ADPR` is diagnostic only and averages ADPR across agent event-log views.

| Mode | Final tests | Final success | Final-integrated ADPR | Mean per-agent-view ADPR | FSR | Subagent artifact failures | Merge failures | Semantic integration failure | Hygiene violations | Async overlap | Runtime | Tokens |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| single | 166/215 | false | 0.0 | 0.0 | 0.0 | 0 | 0 | false | 0 | 0.0s | 410.7s | 718102 |
| serial_specialists | 198/215 | false | 0.2 | 0.2 | 0.0 | 2 | 0 | true | 0 | 0.0s | 1700.0s | 1441639 |
| async_private | 179/215 | false | 0.2 | 0.6 | 0.0 | 2 | 0 | true | 0 | 729.3s | 806.5s | 1389591 |
| CAID_multi | 198/215 | false | 0.2 | 0.6 | 0.0 | 4 | 1 | false | 4 | 826.4s | 5211.9s | unavailable |

## ADPR Interpretation

- `final_integrated_ADPR`: ADPR computed from the final integrated workspace / final evaluator checkpoint. Use this in main paper tables.
- `mean_per_agent_view_ADPR`: mean ADPR across agent event-log views. Use this as a diagnostic, not as canonical run-level ADPR.

| Mode | Final-integrated ADPR | Mean per-agent-view ADPR | Per-agent-view ADPR |
| --- | ---: | ---: | --- |
| single | 0.0 | 0.0 | async_dependency_resolution_single_agent_events.json=0/5=0.0 |
| serial_specialists | 0.2 | 0.2 | async_dependency_resolution_decorator_agent_events.json=1/5=0.2; async_dependency_resolution_key_agent_events.json=1/5=0.2 |
| async_private | 0.2 | 0.6 | async_dependency_resolution_decorator_agent_events.json=5/5=1.0; async_dependency_resolution_key_agent_events.json=1/5=0.2 |
| CAID_multi | 0.2 | 0.6 | async_dependency_resolution_engineer1_events.json=3/5=0.6; async_dependency_resolution_engineer2_events.json=5/5=1.0; async_dependency_resolution_manager_events.json=1/5=0.2 |

## Failed Attempt / Integration Metrics

| Mode | Subagent artifact failures | Merge failures | Semantic integration failure |
| --- | ---: | ---: | --- |
| single | 0 | 0 | false |
| serial_specialists | 2 | 0 | true |
| async_private | 2 | 0 | true |
| CAID_multi | 4 | 1 | false |

## Artifact Hygiene

Definition: `artifact_hygiene_violation_count` is the number of generated temporary, backup, prototype, or out-of-repo files left in the final patch.

| Mode | Violation count | Files |
| --- | ---: | --- |
| single | 0 | None |
| serial_specialists | 0 | None |
| async_private | 0 | None |
| CAID_multi | 4 | src/cachetools/func.py.backup; test_decorator.py; test_keys_impl.py; test_prototype.py |

## Dependency-Level DRS / CAIL Details

`N/A` means a complete dependency resolution was not observed for that dependency point in that event-log view.

### single

Report: `async_dependency_resolution_single_agent_events.json`; ADPR: `0/5 = 0.0`

| Dependency | DRS | Upstream | Downstream | CAIL | Composed DRS |
| --- | ---: | ---: | ---: | ---: | ---: |
| `keys_to_func.untyped_key_contract` | N/A | N/A | N/A | N/A | N/A |
| `keys_to_func.typed_key_contract` | N/A | N/A | N/A | N/A | N/A |
| `keys_to_cachedmethod.typed_method_key_contract` | N/A | N/A | N/A | N/A | N/A |
| `core_to_func.wrapper_metadata_contract` | N/A | N/A | N/A | N/A | N/A |
| `core_to_func.maxsize_and_lock_contract` | N/A | N/A | N/A | N/A | N/A |

### serial_specialists

Report: `async_dependency_resolution_decorator_agent_events.json`; ADPR: `1/5 = 0.2`

| Dependency | DRS | Upstream | Downstream | CAIL | Composed DRS |
| --- | ---: | ---: | ---: | ---: | ---: |
| `keys_to_func.untyped_key_contract` | N/A | 31 | N/A | N/A | N/A |
| `keys_to_func.typed_key_contract` | N/A | 31 | N/A | N/A | N/A |
| `keys_to_cachedmethod.typed_method_key_contract` | 31 | 31 | 31 | 0 | 31 |
| `core_to_func.wrapper_metadata_contract` | N/A | 31 | N/A | N/A | N/A |
| `core_to_func.maxsize_and_lock_contract` | N/A | 31 | N/A | N/A | N/A |

Report: `async_dependency_resolution_key_agent_events.json`; ADPR: `1/5 = 0.2`

| Dependency | DRS | Upstream | Downstream | CAIL | Composed DRS |
| --- | ---: | ---: | ---: | ---: | ---: |
| `keys_to_func.untyped_key_contract` | N/A | 31 | N/A | N/A | N/A |
| `keys_to_func.typed_key_contract` | N/A | 31 | N/A | N/A | N/A |
| `keys_to_cachedmethod.typed_method_key_contract` | 31 | 31 | 31 | 0 | 31 |
| `core_to_func.wrapper_metadata_contract` | N/A | 31 | N/A | N/A | N/A |
| `core_to_func.maxsize_and_lock_contract` | N/A | 31 | N/A | N/A | N/A |

### async_private

Report: `async_dependency_resolution_decorator_agent_events.json`; ADPR: `5/5 = 1.0`

| Dependency | DRS | Upstream | Downstream | CAIL | Composed DRS |
| --- | ---: | ---: | ---: | ---: | ---: |
| `keys_to_func.untyped_key_contract` | 9 | 9 | 9 | 0 | 9 |
| `keys_to_func.typed_key_contract` | 9 | 9 | 9 | 0 | 9 |
| `keys_to_cachedmethod.typed_method_key_contract` | 9 | 9 | 9 | 0 | 9 |
| `core_to_func.wrapper_metadata_contract` | 9 | 9 | 9 | 0 | 9 |
| `core_to_func.maxsize_and_lock_contract` | 9 | 9 | 9 | 0 | 9 |

Report: `async_dependency_resolution_key_agent_events.json`; ADPR: `1/5 = 0.2`

| Dependency | DRS | Upstream | Downstream | CAIL | Composed DRS |
| --- | ---: | ---: | ---: | ---: | ---: |
| `keys_to_func.untyped_key_contract` | N/A | 5 | N/A | N/A | N/A |
| `keys_to_func.typed_key_contract` | N/A | 5 | N/A | N/A | N/A |
| `keys_to_cachedmethod.typed_method_key_contract` | 31 | 5 | 31 | 26 | 31 |
| `core_to_func.wrapper_metadata_contract` | N/A | 31 | N/A | N/A | N/A |
| `core_to_func.maxsize_and_lock_contract` | N/A | 31 | N/A | N/A | N/A |

### CAID_multi

Report: `async_dependency_resolution_engineer1_events.json`; ADPR: `3/5 = 0.6`

| Dependency | DRS | Upstream | Downstream | CAIL | Composed DRS |
| --- | ---: | ---: | ---: | ---: | ---: |
| `keys_to_func.untyped_key_contract` | N/A | 4 | 30 | 26 | 30 |
| `keys_to_func.typed_key_contract` | N/A | 4 | 30 | 26 | 30 |
| `keys_to_cachedmethod.typed_method_key_contract` | 4 | 4 | 4 | 0 | 4 |
| `core_to_func.wrapper_metadata_contract` | 30 | 4 | 30 | 26 | 30 |
| `core_to_func.maxsize_and_lock_contract` | 30 | 4 | 30 | 26 | 30 |

Report: `async_dependency_resolution_engineer2_events.json`; ADPR: `5/5 = 1.0`

| Dependency | DRS | Upstream | Downstream | CAIL | Composed DRS |
| --- | ---: | ---: | ---: | ---: | ---: |
| `keys_to_func.untyped_key_contract` | 16 | 16 | 16 | 0 | 16 |
| `keys_to_func.typed_key_contract` | 16 | 16 | 16 | 0 | 16 |
| `keys_to_cachedmethod.typed_method_key_contract` | 16 | 16 | 16 | 0 | 16 |
| `core_to_func.wrapper_metadata_contract` | 16 | 16 | 16 | 0 | 16 |
| `core_to_func.maxsize_and_lock_contract` | 16 | 16 | 16 | 0 | 16 |

Report: `async_dependency_resolution_manager_events.json`; ADPR: `1/5 = 0.2`

| Dependency | DRS | Upstream | Downstream | CAIL | Composed DRS |
| --- | ---: | ---: | ---: | ---: | ---: |
| `keys_to_func.untyped_key_contract` | N/A | 99 | N/A | N/A | N/A |
| `keys_to_func.typed_key_contract` | N/A | 99 | N/A | N/A | N/A |
| `keys_to_cachedmethod.typed_method_key_contract` | 99 | 99 | 99 | 0 | 99 |
| `core_to_func.wrapper_metadata_contract` | N/A | 99 | N/A | N/A | N/A |
| `core_to_func.maxsize_and_lock_contract` | N/A | 99 | N/A | N/A | N/A |

## Cost and Token Accounting

- CAID token/cost accounting is marked unavailable because `cost.json` reports only 19,148 tokens for a 5211.9s run, which is not credible for this workflow.
- For billing-grade cost, use DeepInfra dashboard/provider logs with input tokens, output tokens, total tokens, and cost USD.
- Non-CAID rows retain `total_tokens` from `cost.json`, but `cost_usd=0.0` should not be treated as provider billing truth without dashboard confirmation.

## Raw Artifact Index

Raw run directories are indexed in `cachetools_deepseek_v32_artifact_index.json`. Each run has per-file SHA-256 checksums and a combined checksum over the indexed artifacts. Raw artifact directories are retained under WSL:

- `single`: `reproductions/async-swe-agents/outputs/repro_commit0/cachetools/deepseek_v32_single_i30`
- `serial_specialists`: `reproductions/async-swe-agents/outputs/repro_commit0/cachetools/deepseek_v32_serial_2agents_s30`
- `async_private`: `reproductions/async-swe-agents/outputs/repro_commit0/cachetools/deepseek_v32_async_private_2agents_s30`
- `CAID_multi`: `reproductions/async-swe-agents/outputs/repro_commit0/cachetools/deepseek_v32_caid_multi_2agents_m30_s30`

## Final Conclusion

All DeepSeek-V3.2 cachetools protocols fail final evaluation. However, AsyncCodeBench metrics reveal different failure structures under similar final scores. In particular, `serial_specialists` and `CAID_multi` both reach 198/215 final tests, but `CAID_multi` shows greater per-agent dependency progress together with substantial asynchronous coordination burden: nonzero overlap, repeated CAIL lag in agent views, failed subagent/artifact attempts, integration burden, and artifact hygiene violations.

This result is best reported as a failure-structure case study: final scores hide failure structure, while AsyncCodeBench dependency and coordination metrics expose asynchronous coordination failures.

## Reproduction Command

```bash
cd ~/AsynccodeBench/Asynccodebench
METRICS=manifests/pilot/v0.3/metrics/commit0_cachetools_async_metrics.json
for RUN in   reproductions/async-swe-agents/outputs/repro_commit0/cachetools/deepseek_v32_single_i30   reproductions/async-swe-agents/outputs/repro_commit0/cachetools/deepseek_v32_serial_2agents_s30   reproductions/async-swe-agents/outputs/repro_commit0/cachetools/deepseek_v32_async_private_2agents_s30   reproductions/async-swe-agents/outputs/repro_commit0/cachetools/deepseek_v32_caid_multi_2agents_m30_s30
do
  for EVENTS in "$RUN"/agent_events/*.jsonl
  do
    [ -e "$EVENTS" ] || continue
    NAME=$(basename "$EVENTS" .jsonl)
    PYTHONPATH=src python3 scripts/analyze_async_dependency_resolution.py       --metrics "$METRICS"       --events "$EVENTS"       --final-test-output "$RUN/cachetools_test_output.txt"       --output "$RUN/async_dependency_resolution_${NAME}.json"
  done
  PYTHONPATH=src python3 scripts/analyze_async_dependency_resolution.py     --metrics "$METRICS"     --events /tmp/asynccodebench_empty_events.jsonl     --final-test-output "$RUN/cachetools_test_output.txt"     --final-logical-iteration 0     --output "$RUN/async_dependency_resolution_final_integrated.json"
  PYTHONPATH=src python3 scripts/analyze_run_process_metrics.py     --run-dir "$RUN"     --metrics "$METRICS"     --output "$RUN/process_metrics_summary.json"     --print-summary
done
```
