# gpt-5.4-mini deprecated Experiment Report

Task: `commit0:deprecated`

Model: `openai/gpt-5.4-mini`

Runner adapter: `native-strict-checkpoints`

This report is an automatically generated AsyncCodeBench evaluation record.
At least one protocol reaches final success.

## Canonical Metrics Table

ADPR convention: `final_integrated_ADPR` is the canonical run-level dependency score for paper tables. `mean_per_agent_view_ADPR` is diagnostic only.

| Mode | Final tests | Final success | Final-integrated ADPR | Mean per-agent ADPR | Async overlap | Runtime | Tokens | Cost | Artifact failures | Non-merged attempts | Merge failures | Scope violations | Duplicated contracts | Hygiene violations |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| single | 171/171 | True | 1 | unavailable | 0s | 160.2s | 798053 | $0.153 | 0 | unavailable | 0 | 0 | 0 | 0 |
| serial_specialists | 160/171 | False | 1 | unavailable | 0s | 451.3s | 1469831 | $0.3622 | 1 | 0 | 0 | 0 | 0 | 0 |
| async_private | 171/171 | True | 1 | unavailable | 207.2s | 341.7s | 2271582 | $0.4962 | 1 | 0 | 0 | 0 | 1 | 0 |
| CAID_multi | 171/171 | True | 1 | unavailable | 183.1s | 656.1s | 5897348 | $0.9662 | 4 | 4 | 0 | 0 | 2 | 0 |

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
| serial_specialists | 3 | 4 | 4 | 3 | 0 | 2 | 2 | 0 | 0 |
| async_private | 3 | 4 | 4 | 3 | 0 | 2 | 1 | 0 | 0 |
| CAID_multi | 3 | 6 | 8 | 3 | 0 | 3 | 6 | 0 | 0 |

## Strict Dependency Diagnostics

This table is based on `dependency_probe_checkpoints.jsonl` and shows whether each protocol resolves producer-side, consumer-side, and integrated dependency probes.

| Mode | Dependencies | Upstream resolved | Downstream resolved | Integrated resolved | Unresolved dependencies | Upstream-only dependencies |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| single | 3 | 3 | 3 | 3 |  |  |
| serial_specialists | 3 | 3 | 3 | 3 |  |  |
| async_private | 3 | 3 | 3 | 3 |  |  |
| CAID_multi | 3 | 3 | 3 | 3 |  |  |

## Strict Per-Dependency Trace

| Mode | Trace |
| --- | --- |
| single | deprecated.classic_to_sphinx.warning_message_contract:up=1,down=1,DRS=1,CAIL=0<br>deprecated.classic_to_sphinx.class_identity_contract:up=1,down=1,DRS=1,CAIL=0<br>deprecated.sphinx_to_integration.docstring_reference_contract:up=1,down=1,DRS=1,CAIL=0 |
| serial_specialists | deprecated.classic_to_sphinx.warning_message_contract:up=1,down=3,DRS=4,CAIL=2<br>deprecated.classic_to_sphinx.class_identity_contract:up=1,down=3,DRS=4,CAIL=2<br>deprecated.sphinx_to_integration.docstring_reference_contract:up=3,down=3,DRS=4,CAIL=0 |
| async_private | deprecated.classic_to_sphinx.warning_message_contract:up=1,down=2,DRS=4,CAIL=1<br>deprecated.classic_to_sphinx.class_identity_contract:up=1,down=2,DRS=4,CAIL=1<br>deprecated.sphinx_to_integration.docstring_reference_contract:up=2,down=2,DRS=4,CAIL=0 |
| CAID_multi | deprecated.classic_to_sphinx.warning_message_contract:up=2,down=8,DRS=8,CAIL=6<br>deprecated.classic_to_sphinx.class_identity_contract:up=2,down=6,DRS=6,CAIL=4<br>deprecated.sphinx_to_integration.docstring_reference_contract:up=6,down=8,DRS=8,CAIL=2 |

## Interpretation Notes

This run is suitable for success-case analysis: final pass is achieved, and dependency/coordination metrics explain the process differences between protocols.

Deprecated-specific reading:

- `CAID_multi` reaches `171/171`, but all four subagent attempts fail to produce a merged artifact. Treat this as a late manager-recovery success, not as clean asynchronous collaboration.
- `async_private` also reaches `171/171` with one failed artifact attempt, showing that final tests alone hide recovery-dependent execution.
- `serial_specialists` has `final_integrated_ADPR=1.0` but fails full tests at `160/171`; the failure is a semantic integration gap outside the final dependency aggregate, so report final tests alongside ADPR.
- The strongest process signal is the lag gap: `CAID_multi` has `DRS max=8` and `CAIL max=6`, while `async_private` resolves by `DRS=4` with smaller CAIL.

Important conventions:

- Use `final_integrated_ADPR` in main paper tables.
- Use `mean_per_agent_view_ADPR` to discuss local or partial dependency progress.
- Treat `SAD-proxy` as candidate evidence until dependency-version visibility logs are available.
- Treat duplicated contract symbols as coordination diagnostics, not as artifact hygiene violations.
- Keep raw run directories or shared-storage copies for reproducibility; this report only indexes them.
