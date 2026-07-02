# gpt-5.4-mini portalocker Experiment Report

Task: `commit0:portalocker`

Model: `openai/gpt-5.4-mini`

Runner adapter: `native-strict-checkpoints`

This report is an automatically generated AsyncCodeBench evaluation record.
No protocol reaches final success; interpret this as a failure-structure record.

## Canonical Metrics Table

ADPR convention: `final_integrated_ADPR` is the canonical run-level dependency score for paper tables. `mean_per_agent_view_ADPR` is diagnostic only.

| Mode | Final tests | Final success | Final-integrated ADPR | Mean per-agent ADPR | Async overlap | Runtime | Tokens | Cost | Artifact failures | Non-merged attempts | Merge failures | Scope violations | Duplicated contracts | Hygiene violations |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| single | 41/41 | False | 1 | unavailable | 0s | 227.3s | 1355763 | $0.222 | 0 | unavailable | 0 | 0 | 0 | 0 |
| serial_specialists | 13/40 | False | 0 | unavailable | 0s | 329.2s | 1673017 | $0.3475 | 1 | 1 | 0 | 0 | 0 | 0 |
| async_private | unavailable/unavailable | False | 0 | unavailable | 154.3s | 261.1s | 1773795 | $0.348 | 2 | 2 | 0 | 0 | 0 | 0 |
| CAID_multi | 39/40 | False | 0.6667 | unavailable | 269s | 511.9s | 3461013 | $0.8357 | 1 | 1 | 0 | 3 | 11 | 0 |

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
| serial_specialists | 0 | unavailable | unavailable | 0 | 3 | 0 | unavailable | 0 | 0 |
| async_private | 0 | unavailable | unavailable | 0 | 3 | 0 | unavailable | 0 | 0 |
| CAID_multi | 2 | 2 | 2 | 2 | 1 | 0 | 0 | 0 | 0 |

## Strict Dependency Diagnostics

This table is based on `dependency_probe_checkpoints.jsonl` and shows whether each protocol resolves producer-side, consumer-side, and integrated dependency probes.

| Mode | Dependencies | Upstream resolved | Downstream resolved | Integrated resolved | Unresolved dependencies | Upstream-only dependencies |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| single | 3 | 3 | 3 | 3 |  |  |
| serial_specialists | 3 | 2 | 0 | 0 | portalocker.backend_to_utilities.exception_timeout_contract; portalocker.backend_to_utilities.flags_fileno_contract; portalocker.utilities_to_integration.lifecycle_contract | portalocker.backend_to_utilities.exception_timeout_contract; portalocker.backend_to_utilities.flags_fileno_contract |
| async_private | 3 | 2 | 0 | 0 | portalocker.backend_to_utilities.exception_timeout_contract; portalocker.backend_to_utilities.flags_fileno_contract; portalocker.utilities_to_integration.lifecycle_contract | portalocker.backend_to_utilities.exception_timeout_contract; portalocker.backend_to_utilities.flags_fileno_contract |
| CAID_multi | 3 | 3 | 2 | 2 | portalocker.utilities_to_integration.lifecycle_contract | portalocker.utilities_to_integration.lifecycle_contract |

## Strict Per-Dependency Trace

| Mode | Trace |
| --- | --- |
| single | portalocker.backend_to_utilities.exception_timeout_contract:up=1,down=1,DRS=1,CAIL=0<br>portalocker.backend_to_utilities.flags_fileno_contract:up=1,down=1,DRS=1,CAIL=0<br>portalocker.utilities_to_integration.lifecycle_contract:up=1,down=1,DRS=1,CAIL=0 |
| serial_specialists | portalocker.backend_to_utilities.exception_timeout_contract:up=1,down=unavailable,DRS=unavailable,CAIL=unavailable<br>portalocker.backend_to_utilities.flags_fileno_contract:up=1,down=unavailable,DRS=unavailable,CAIL=unavailable<br>portalocker.utilities_to_integration.lifecycle_contract:up=unavailable,down=unavailable,DRS=unavailable,CAIL=unavailable |
| async_private | portalocker.backend_to_utilities.exception_timeout_contract:up=1,down=unavailable,DRS=unavailable,CAIL=unavailable<br>portalocker.backend_to_utilities.flags_fileno_contract:up=1,down=unavailable,DRS=unavailable,CAIL=unavailable<br>portalocker.utilities_to_integration.lifecycle_contract:up=unavailable,down=unavailable,DRS=unavailable,CAIL=unavailable |
| CAID_multi | portalocker.backend_to_utilities.exception_timeout_contract:up=1,down=1,DRS=2,CAIL=0<br>portalocker.backend_to_utilities.flags_fileno_contract:up=1,down=1,DRS=2,CAIL=0<br>portalocker.utilities_to_integration.lifecycle_contract:up=1,down=unavailable,DRS=unavailable,CAIL=unavailable |

## Interpretation Notes

This run is suitable for failure-structure analysis: final scores alone do not describe dependency progress, local-vs-integrated gaps, or integration burden.

Portalocker is a useful example of why AsyncCodeBench should not be reported only with a final success column. Under the strict evaluator, all four protocols have `Final success=False`, but the dependency-aware metrics separate very different failure modes:

- `single` resolves all three labeled dependencies (`ADPR=1.0`, `DRS=1`, `CAIL=0`) and passes `41/41` functional tests, but still fails strict final success because the evaluator exits nonzero under the full project gate. This is a task-level gate failure, not a dependency-resolution failure.
- `serial_specialists` reaches only `13/40` final tests and has `ADPR=0.0`. Its backend-side probes resolve for two dependencies, but downstream and integrated probes never resolve, so all three labeled dependency points remain unresolved.
- `async_private` has real concurrent execution (`154.3s` overlap) but still has `ADPR=0.0`, `FSAR=1.0`, and no successful merged artifact. This is the clearest negative control: parallelism alone does not resolve cross-agent contracts.
- `CAID_multi` improves the async picture: it resolves two of the three labeled dependency points (`ADPR=0.6667`), with both backend-to-utilities contracts reaching `DRS=2` and `CAIL=0`. It still fails the lifecycle integration dependency, and its high `SVR=0.75` plus `11` duplicated contract symbols show coordination and ownership noise that final tests alone would hide.

These conclusions depend on the dependency labels created during AsyncCodeBench construction. The portalocker metrics manifest defines producer/consumer agents, dependency IDs, and upstream/downstream/integrated probe tests for `exception_timeout_contract`, `flags_fileno_contract`, and `lifecycle_contract`. Without those labels, the table would only say that every protocol failed strictly; with them, we can show that CAID resolves 2/3 cross-agent contracts while serial and naive async resolve 0/3.

Important conventions:

- Use `final_integrated_ADPR` in main paper tables.
- Use `mean_per_agent_view_ADPR` to discuss local or partial dependency progress.
- Treat `SAD-proxy` as candidate evidence until dependency-version visibility logs are available.
- Treat duplicated contract symbols as coordination diagnostics, not as artifact hygiene violations.
- Keep raw run directories or shared-storage copies for reproducibility; this report only indexes them.
