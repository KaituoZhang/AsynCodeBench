# gpt-5.4-mini tinydb Experiment Report

Task: `commit0:tinydb`

Model: `openai/gpt-5.4-mini`

Runner adapter: `native`

This report is an automatically generated AsyncCodeBench evaluation record.
At least one protocol reaches final success.

## Canonical Metrics Table

ADPR convention: `final_integrated_ADPR` is the canonical run-level dependency score for paper tables. `mean_per_agent_view_ADPR` is diagnostic only.

| Mode | Final tests | Final success | Final-integrated ADPR | Mean per-agent ADPR | Async overlap | Runtime | Tokens | Cost | Artifact failures | Non-merged attempts | Merge failures | Scope violations | Duplicated contracts | Hygiene violations |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| single | 200/201 | True | 1 | 0.5 | 0s | 753s | 5095968 | $0.858 | 0 | unavailable | 0 | 0 | 0 | 0 |
| serial_specialists | 195/201 | False | 1 | 0.3333 | 0s | 1087s | 6905576 | $1.192 | 1 | 0 | 0 | 0 | 6 | 0 |
| async_private | 60/201 | False | 0 | 0 | 352.8s | 550.5s | 7241295 | $1.223 | 0 | 0 | 0 | 0 | 5 | 0 |
| CAID_multi | 57/201 | False | 0 | 0 | 167.5s | 645s | 5615562 | $1.046 | 0 | 0 | 0 | 1 | 0 | 0 |

## Per-Agent Dependency Views

| Mode | Final-integrated ADPR source | Mean per-agent ADPR | Per-agent-view ADPR |
| --- | --- | ---: | --- |
| single | async_dependency_resolution_final_integrated.json | 0.5 | async_dependency_resolution_final_integrated.json=3/3=1.0; async_dependency_resolution_single_agent.json=0/3=0.0 |
| serial_specialists | async_dependency_resolution_final_integrated.json | 0.3333 | async_dependency_resolution_final_integrated.json=3/3=1.0; async_dependency_resolution_query_agent.json=0/3=0.0; async_dependency_resolution_state_agent.json=0/3=0.0 |
| async_private | async_dependency_resolution_final_integrated.json | 0 | async_dependency_resolution_final_integrated.json=0/3=0.0; async_dependency_resolution_query_agent.json=0/3=0.0; async_dependency_resolution_state_agent.json=0/3=0.0 |
| CAID_multi | async_dependency_resolution_final_integrated.json | 0 | async_dependency_resolution_engineer_1.json=0/3=0.0; async_dependency_resolution_engineer_2.json=0/3=0.0; async_dependency_resolution_final_integrated.json=0/3=0.0; async_dependency_resolution_manager.json=0/3=0.0 |

## DRS / CAIL / SAD Summary

| Mode | DRS observed | DRS min | DRS max | CAIL observed | CAIL unresolved | Nonzero CAIL | CAIL max | SAD-proxy | Missing-comm proxy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| single | 0 | unavailable | unavailable | 0 | 6 | 0 | unavailable | 0 | 0 |
| serial_specialists | 0 | unavailable | unavailable | 0 | 9 | 0 | unavailable | 0 | 0 |
| async_private | 0 | unavailable | unavailable | 0 | 9 | 0 | unavailable | 0 | 0 |
| CAID_multi | 0 | unavailable | unavailable | 0 | 12 | 0 | unavailable | 0 | 0 |

## Interpretation Notes

This run is suitable for success-case analysis: final pass is achieved, and dependency/coordination metrics explain the process differences between protocols.

Important conventions:

- Use `final_integrated_ADPR` in main paper tables.
- Use `mean_per_agent_view_ADPR` to discuss local or partial dependency progress.
- Treat `SAD-proxy` as candidate evidence until dependency-version visibility logs are available.
- Treat duplicated contract symbols as coordination diagnostics, not as artifact hygiene violations.
- Keep raw run directories or shared-storage copies for reproducibility; this report only indexes them.

