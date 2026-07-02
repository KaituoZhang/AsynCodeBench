# gpt-5.4-mini requests Experiment Report

Task: `commit0:requests`

Model: `openai/gpt-5.4-mini`

Runner adapter: `native-strict-checkpoints`

This report is an automatically generated AsyncCodeBench evaluation record.
No protocol reaches final success; interpret this as a failure-structure record.

## Canonical Metrics Table

ADPR convention: `final_integrated_ADPR` is the canonical run-level dependency score for paper tables. `mean_per_agent_view_ADPR` is diagnostic only.

| Mode | Final tests | Final success | Final-integrated ADPR | Mean per-agent ADPR | Async overlap | Runtime | Tokens | Cost | Artifact failures | Non-merged attempts | Merge failures | Scope violations | Duplicated contracts | Hygiene violations |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| single | 589/606 | False | 1 | unavailable | 0s | 449.3s | 1707575 | $0.252 | 0 | unavailable | 0 | 0 | 0 | 0 |
| serial_specialists | 391/606 | False | 1 | unavailable | 0s | 509.3s | 3444984 | $0.5498 | 0 | 0 | 0 | 0 | 3 | 0 |
| async_private | 350/606 | False | 0.3333 | unavailable | 204.3s | 540.4s | 5140856 | $1.099 | 3 | 0 | 0 | 0 | 3 | 0 |
| CAID_multi | 357/606 | False | 1 | unavailable | 157.1s | 1189s | 9955747 | $1.71 | 1 | 0 | 0 | 0 | 3 | 0 |

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
| async_private | 1 | 4 | 4 | 1 | 2 | 0 | 0 | 0 | 0 |
| CAID_multi | 3 | 4 | 4 | 3 | 0 | 2 | 1 | 0 | 0 |

## Strict Dependency Diagnostics

This table is based on `dependency_probe_checkpoints.jsonl` and shows whether each protocol resolves producer-side, consumer-side, and integrated dependency probes.

| Mode | Dependencies | Upstream resolved | Downstream resolved | Integrated resolved | Unresolved dependencies | Upstream-only dependencies |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| single | 3 | 3 | 3 | 3 |  |  |
| serial_specialists | 3 | 3 | 3 | 3 |  |  |
| async_private | 3 | 3 | 1 | 1 | requests.prep_to_transport.prepared_request_contract; requests.utils_to_adapters.proxy_tls_url_contract | requests.prep_to_transport.prepared_request_contract; requests.utils_to_adapters.proxy_tls_url_contract |
| CAID_multi | 3 | 3 | 3 | 3 |  |  |

## Strict Per-Dependency Trace

| Mode | Trace |
| --- | --- |
| single | requests.prep_to_transport.prepared_request_contract:up=1,down=1,DRS=1,CAIL=0<br>requests.utils_to_adapters.proxy_tls_url_contract:up=1,down=1,DRS=1,CAIL=0<br>requests.foundation_to_public_api.package_contract:up=1,down=1,DRS=1,CAIL=0 |
| serial_specialists | requests.prep_to_transport.prepared_request_contract:up=3,down=3,DRS=4,CAIL=0<br>requests.utils_to_adapters.proxy_tls_url_contract:up=3,down=3,DRS=4,CAIL=0<br>requests.foundation_to_public_api.package_contract:up=3,down=3,DRS=4,CAIL=0 |
| async_private | requests.prep_to_transport.prepared_request_contract:up=4,down=unavailable,DRS=unavailable,CAIL=unavailable<br>requests.utils_to_adapters.proxy_tls_url_contract:up=4,down=unavailable,DRS=unavailable,CAIL=unavailable<br>requests.foundation_to_public_api.package_contract:up=4,down=4,DRS=4,CAIL=0 |
| CAID_multi | requests.prep_to_transport.prepared_request_contract:up=3,down=4,DRS=4,CAIL=1<br>requests.utils_to_adapters.proxy_tls_url_contract:up=3,down=4,DRS=4,CAIL=1<br>requests.foundation_to_public_api.package_contract:up=3,down=3,DRS=4,CAIL=0 |

## Interpretation Notes

This run is suitable for failure-structure analysis: final scores alone do not describe dependency progress, local-vs-integrated gaps, or integration burden.

Requests is suitable for AsyncCodeBench as a failure-structure instance. No protocol reaches strict final success, but the dependency-labeled metrics separate several qualitatively different outcomes that a final pass/fail table would collapse.

- `single` nearly solves the full evaluator (`589/606`) and resolves all three labeled dependencies immediately (`ADPR=1.0`, `DRS=1`, `CAIL=0`). Its strict failure is concentrated in one remaining TLS/mTLS connection-pool test, so it should be interpreted as task-level residual failure rather than unresolved async dependency structure.
- `serial_specialists` also resolves all three dependency labels (`ADPR=1.0`) but later (`DRS=4`) and with much weaker final coverage (`391/606`, plus many request-layer errors). This shows that resolving the selected public dependency probes is not identical to solving the whole repository, which is expected for a large library like Requests.
- `async_private` is the clearest async failure mode. It has substantial overlap (`204.3s`) but resolves only one of three dependencies (`ADPR=0.3333`), leaving the two primary async dependencies unresolved: `prepared_request_contract` and `proxy_tls_url_contract`. It also has `FSAR=1.0`, meaning all recorded agent artifacts failed, so parallel private work did not integrate the producer contracts into the transport consumer.
- `CAID_multi` recovers all three labeled dependencies (`ADPR=1.0`) but with visible coordination lag: two primary dependencies have `CAIL=1`, and all dependencies resolve at `DRS=4`. It still fails strict final success (`357/606`) and costs the most tokens, so CAID improves dependency integration relative to naive async but does not guarantee broad task completion on this large task.

These conclusions rely directly on AsyncCodeBench's dependency labels in `commit0_requests_async_metrics.json`. The manifest labels producer/consumer contracts from request preparation utilities into session/adapter transport behavior, plus a public package compatibility contract. Strict `ADPR`, `DRS`, and `CAIL` are computed from the manifest's upstream, downstream, and integrated probe tests. Without those labels, the result would only say that every protocol failed; with them, we can distinguish immediate dependency resolution, delayed handoff resolution, unresolved private-async consumer contracts, and CAID's one-checkpoint cross-agent integration lag.

Important conventions:

- Use `final_integrated_ADPR` in main paper tables.
- Use `mean_per_agent_view_ADPR` to discuss local or partial dependency progress.
- Treat `SAD-proxy` as candidate evidence until dependency-version visibility logs are available.
- Treat duplicated contract symbols as coordination diagnostics, not as artifact hygiene violations.
- Keep raw run directories or shared-storage copies for reproducibility; this report only indexes them.
