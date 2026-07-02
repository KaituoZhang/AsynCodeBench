# gpt-5.4-mini cachetools Experiment Report

Task: `commit0:cachetools`

Model: `openai/gpt-5.4-mini`

Runner adapter: `native`

This report is an automatically generated AsyncCodeBench evaluation record.
At least one protocol reaches final success.

## Canonical Metrics Table

ADPR convention: `final_integrated_ADPR` is the canonical run-level dependency score for paper tables. `mean_per_agent_view_ADPR` is diagnostic only.

| Mode | Final tests | Final success | Final-integrated ADPR | Mean per-agent ADPR | Async overlap | Runtime | Tokens | Cost | Artifact failures | Non-merged attempts | Merge failures | Scope violations | Duplicated contracts | Hygiene violations |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| single | 215/215 | True | 1 | 1 | 0s | 247.4s | 1381916 | $0.2723 | 0 | unavailable | 0 | 0 | 0 | 0 |
| serial_specialists | 215/215 | True | 1 | 1 | 0s | 284.7s | 1235727 | $0.272 | 0 | 0 | 0 | 0 | 0 | 0 |
| async_private | 215/215 | True | 1 | 1 | 58.8s | 194.4s | 965837 | $0.2369 | 0 | 0 | 0 | 0 | 4 | 0 |
| CAID_multi | 215/215 | True | 1 | 1 | 155.2s | 484.6s | 4659935 | $1.073 | 3 | 5 | 2 | 1 | 1 | 0 |

## Per-Agent Dependency Views

| Mode | Final-integrated ADPR source | Mean per-agent ADPR | Per-agent-view ADPR |
| --- | --- | ---: | --- |
| single | process_metrics_summary.formal_metrics.ADPR | 1 | async_dependency_resolution.json=5/5=1.0 |
| serial_specialists | process_metrics_summary.formal_metrics.ADPR | 1 | async_dependency_resolution_decorator_agent.json=5/5=1.0; async_dependency_resolution_key_agent.json=5/5=1.0 |
| async_private | process_metrics_summary.formal_metrics.ADPR | 1 | async_dependency_resolution_decorator_agent.json=5/5=1.0; async_dependency_resolution_key_agent.json=5/5=1.0 |
| CAID_multi | async_dependency_resolution_manager.json | 1 | async_dependency_resolution_engineer_1.json=5/5=1.0; async_dependency_resolution_engineer_2.json=5/5=1.0; async_dependency_resolution_engineer_3.json=5/5=1.0; async_dependency_resolution_engineer_4.json=5/5=1.0; async_dependency_resolution_manager.json=5/5=1.0 |

## DRS / CAIL / SAD Summary

| Mode | DRS observed | DRS min | DRS max | CAIL observed | CAIL unresolved | Nonzero CAIL | CAIL max | SAD-proxy | Missing-comm proxy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| single | 5 | 25 | 25 | 5 | 0 | 0 | 0 | 0 | 0 |
| serial_specialists | 10 | 13 | 25 | 10 | 0 | 4 | 8 | 0 | 0 |
| async_private | 10 | 13 | 21 | 10 | 0 | 7 | 6 | 4 | 4 |
| CAID_multi | 25 | 16 | 30 | 25 | 0 | 4 | 2 | 0 | 0 |

## Interpretation Notes

This run is suitable for success-case analysis: final pass is achieved, and dependency/coordination metrics explain the process differences between protocols.

Important conventions:

- Use `final_integrated_ADPR` in main paper tables.
- Use `mean_per_agent_view_ADPR` to discuss local or partial dependency progress.
- Treat `SAD-proxy` as candidate evidence until dependency-version visibility logs are available.
- Treat duplicated contract symbols as coordination diagnostics, not as artifact hygiene violations.
- Keep raw run directories or shared-storage copies for reproducibility; this report only indexes them.

