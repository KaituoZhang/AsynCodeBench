# gpt-5.4-mini tinydb Experiment Report

Task: `commit0:tinydb`

Model: `openai/gpt-5.4-mini`

Runner adapter: `native-strict-checkpoints`

This report is an automatically generated AsyncCodeBench evaluation record.
At least one protocol reaches final success.

## Canonical Metrics Table

ADPR convention: `final_integrated_ADPR` is the canonical run-level dependency score for paper tables. `mean_per_agent_view_ADPR` is diagnostic only.

| Mode | Final tests | Final success | Final-integrated ADPR | Mean per-agent ADPR | Async overlap | Runtime | Tokens | Cost | Artifact failures | Non-merged attempts | Merge failures | Scope violations | Duplicated contracts | Hygiene violations |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| single | 200/201 | True | 1 | unavailable | 0s | 573.8s | 2997328 | $0.6742 | 0 | unavailable | 0 | 0 | 0 | 0 |
| serial_specialists | 192/201 | False | 1 | unavailable | 0s | 978.2s | 3637137 | $0.9227 | 2 | 0 | 0 | 0 | 16 | 0 |
| async_private | 115/201 | False | 0 | unavailable | 390.3s | 456.3s | 4295524 | $0.9607 | 2 | 0 | 0 | 0 | 6 | 0 |
| CAID_multi | 44/201 | False | 0 | unavailable | 140.7s | 681.9s | 3973078 | $0.97 | 4 | 0 | 0 | 0 | 0 | 0 |

## Per-Agent Dependency Views

| Mode | Final-integrated ADPR source | Mean per-agent ADPR | Per-agent-view ADPR |
| --- | --- | ---: | --- |
| single | strict_dependency_metrics.final_integrated_ADPR | unavailable |  |
| serial_specialists | strict_dependency_metrics.final_integrated_ADPR | unavailable |  |
| async_private | strict_dependency_metrics.final_integrated_ADPR | unavailable |  |
| CAID_multi | strict_dependency_metrics.final_integrated_ADPR | unavailable |  |

## DRS / CAIL / SAD Summary

| Mode | DRS observed | DRS min | DRS max | CAIL observed | CAIL unresolved | Nonzero CAIL | CAIL max | SAD-proxy | Missing-comm proxy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| single | 3 | 1 | 1 | 3 | 0 | 0 | 0 | 0 | 0 |
| serial_specialists | 3 | 4 | 4 | 3 | 0 | 0 | 0 | 0 | 0 |
| async_private | 0 | unavailable | unavailable | 0 | 3 | 0 | unavailable | 0 | 0 |
| CAID_multi | 0 | unavailable | unavailable | 0 | 3 | 0 | unavailable | 0 | 0 |

## Strict Dependency Diagnostics

This table is based on `dependency_probe_checkpoints.jsonl` and shows whether each protocol resolves producer-side, consumer-side, and integrated dependency probes.

| Mode | Dependencies | Upstream resolved | Downstream resolved | Integrated resolved | Unresolved dependencies | Upstream-only dependencies |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| single | 3 | 3 | 3 | 3 |  |  |
| serial_specialists | 3 | 3 | 3 | 3 |  |  |
| async_private | 3 | 1 | 0 | 0 | tinydb.query_to_table.search_cache_contract; tinydb.operations_to_table.update_transform_contract; tinydb.state_stack.shared_mapping_contract | tinydb.query_to_table.search_cache_contract |
| CAID_multi | 3 | 1 | 0 | 0 | tinydb.query_to_table.search_cache_contract; tinydb.operations_to_table.update_transform_contract; tinydb.state_stack.shared_mapping_contract | tinydb.query_to_table.search_cache_contract |

## Strict Per-Dependency Trace

| Mode | Trace |
| --- | --- |
| single | tinydb.query_to_table.search_cache_contract:up=1,down=1,DRS=1,CAIL=0<br>tinydb.operations_to_table.update_transform_contract:up=1,down=1,DRS=1,CAIL=0<br>tinydb.state_stack.shared_mapping_contract:up=1,down=1,DRS=1,CAIL=0 |
| serial_specialists | tinydb.query_to_table.search_cache_contract:up=3,down=3,DRS=4,CAIL=0<br>tinydb.operations_to_table.update_transform_contract:up=3,down=3,DRS=4,CAIL=0<br>tinydb.state_stack.shared_mapping_contract:up=3,down=3,DRS=4,CAIL=0 |
| async_private | tinydb.query_to_table.search_cache_contract:up=1,down=unavailable,DRS=unavailable,CAIL=unavailable<br>tinydb.operations_to_table.update_transform_contract:up=unavailable,down=unavailable,DRS=unavailable,CAIL=unavailable<br>tinydb.state_stack.shared_mapping_contract:up=unavailable,down=unavailable,DRS=unavailable,CAIL=unavailable |
| CAID_multi | tinydb.query_to_table.search_cache_contract:up=8,down=unavailable,DRS=unavailable,CAIL=unavailable<br>tinydb.operations_to_table.update_transform_contract:up=unavailable,down=unavailable,DRS=unavailable,CAIL=unavailable<br>tinydb.state_stack.shared_mapping_contract:up=unavailable,down=unavailable,DRS=unavailable,CAIL=unavailable |

## Interpretation Notes

This run is suitable for success-case analysis: final pass is achieved, and dependency/coordination metrics explain the process differences between protocols.

Important conventions:

- Use `final_integrated_ADPR` in main paper tables.
- Use `mean_per_agent_view_ADPR` to discuss local or partial dependency progress.
- Treat `SAD-proxy` as candidate evidence until dependency-version visibility logs are available.
- Treat duplicated contract symbols as coordination diagnostics, not as artifact hygiene violations.
- Keep raw run directories or shared-storage copies for reproducibility; this report only indexes them.

