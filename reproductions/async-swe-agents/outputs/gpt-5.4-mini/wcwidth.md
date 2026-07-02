# gpt-5.4-mini wcwidth Experiment Report

Task: `commit0:wcwidth`

Model: `openai/gpt-5.4-mini`

Runner adapter: `native-strict-checkpoints`

This report is an automatically generated AsyncCodeBench evaluation record.
At least one protocol reaches final success.

## Canonical Metrics Table

ADPR convention: `final_integrated_ADPR` is the canonical run-level dependency score for paper tables. `mean_per_agent_view_ADPR` is diagnostic only.

| Mode | Final tests | Final success | Final-integrated ADPR | Mean per-agent ADPR | Async overlap | Runtime | Tokens | Cost | Artifact failures | Non-merged attempts | Merge failures | Scope violations | Duplicated contracts | Hygiene violations |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| single | 38/39 | True | 1 | unavailable | 0s | 235.9s | 1792099 | $0.2991 | 0 | unavailable | 0 | 0 | 0 | 0 |
| serial_specialists | 2/39 | False | 0 | unavailable | 0s | 288.2s | 1499550 | $0.3023 | 1 | 0 | 0 | 0 | 0 | 0 |
| async_private | 35/39 | False | 0.5 | unavailable | 81.5s | 330.7s | 2371746 | $0.4857 | 1 | 0 | 0 | 0 | 2 | 0 |
| CAID_multi | 38/39 | True | 1 | unavailable | 80.24s | 383.6s | 4081656 | $0.7258 | 3 | 4 | 1 | 1 | 0 | 0 |

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
| single | 2 | 1 | 1 | 2 | 0 | 0 | 0 | 0 | 0 |
| serial_specialists | 0 | unavailable | unavailable | 0 | 2 | 0 | unavailable | 0 | 0 |
| async_private | 1 | 4 | 4 | 1 | 1 | 0 | 0 | 0 | 0 |
| CAID_multi | 2 | 9 | 9 | 2 | 0 | 0 | 0 | 0 | 0 |

## Strict Dependency Diagnostics

This table is based on `dependency_probe_checkpoints.jsonl` and shows whether each protocol resolves producer-side, consumer-side, and integrated dependency probes.

| Mode | Dependencies | Upstream resolved | Downstream resolved | Integrated resolved | Unresolved dependencies | Upstream-only dependencies |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| single | 2 | 2 | 2 | 2 |  |  |
| serial_specialists | 2 | 0 | 0 | 0 | wcwidth.unicode_versions_to_width.version_matching_contract; wcwidth.width_to_integration.public_width_contract |  |
| async_private | 2 | 2 | 1 | 1 | wcwidth.width_to_integration.public_width_contract | wcwidth.width_to_integration.public_width_contract |
| CAID_multi | 2 | 2 | 2 | 2 |  |  |

## Strict Per-Dependency Trace

| Mode | Trace |
| --- | --- |
| single | wcwidth.unicode_versions_to_width.version_matching_contract:up=1,down=1,DRS=1,CAIL=0<br>wcwidth.width_to_integration.public_width_contract:up=1,down=1,DRS=1,CAIL=0 |
| serial_specialists | wcwidth.unicode_versions_to_width.version_matching_contract:up=unavailable,down=unavailable,DRS=unavailable,CAIL=unavailable<br>wcwidth.width_to_integration.public_width_contract:up=unavailable,down=unavailable,DRS=unavailable,CAIL=unavailable |
| async_private | wcwidth.unicode_versions_to_width.version_matching_contract:up=2,down=2,DRS=4,CAIL=0<br>wcwidth.width_to_integration.public_width_contract:up=2,down=unavailable,DRS=unavailable,CAIL=unavailable |
| CAID_multi | wcwidth.unicode_versions_to_width.version_matching_contract:up=7,down=7,DRS=9,CAIL=0<br>wcwidth.width_to_integration.public_width_contract:up=7,down=7,DRS=9,CAIL=0 |

## Interpretation Notes

This run is suitable for success-case analysis: final pass is achieved, and dependency/coordination metrics explain the process differences between protocols.

Wcwidth is a useful positive-control task because final success and dependency success do not collapse to the same story. Both `single` and `CAID_multi` reach strict final success, but they resolve the labeled dependency structure at very different points, while `serial_specialists` and `async_private` expose distinct async failure modes.

- `single` reaches final success with `ADPR=1.0` and resolves both labeled dependencies at `DRS=1`. This is the baseline showing that GPT-5.4-mini can solve the underlying coding task when it has full context.
- `serial_specialists` fails badly (`2/39`, `ADPR=0.0`). Neither the Unicode-version catalog dependency nor the public-width integration dependency resolves. This means the split specialist workflow did not produce a usable producer contract for the downstream width implementation.
- `async_private` is not just "worse final pass"; it gives a more informative partial dependency story. It reaches `35/39` with real overlap (`81.5s`) and resolves the version-matching dependency (`DRS=4`), but it fails the final public-width integration dependency. This is exactly the kind of partial async progress that final tests alone would compress into a binary failure.
- `CAID_multi` reaches final success and `ADPR=1.0`, but dependency resolution is delayed to `DRS=9` for both labels. It also has higher process cost: `3` failed artifact attempts, `1` merge failure, `SVR=0.25`, and about `2.4x` the single-agent token cost. So CAID can recover the dependency contracts, but the benchmark exposes the integration burden and delayed resolution.

These conclusions rely directly on AsyncCodeBench's construction-time dependency labels. The metrics manifest labels `wcwidth.unicode_versions_to_width.version_matching_contract` as a producer-consumer dependency from `wcwidth/unicode_versions.py` to `wcwidth/wcwidth.py`, and labels `wcwidth.width_to_integration.public_width_contract` as the integration dependency over public `wcwidth()` / `wcswidth()` behavior. The strict `ADPR`, `DRS`, and `CAIL` values are computed by running the manifest's upstream, downstream, and integrated probe tests at recorded checkpoints. Without these labels, the result would only say "single and CAID pass, serial and async_private fail"; with them, we can show which cross-agent dependency was resolved, which one was delayed, and which one never integrated.

Important conventions:

- Use `final_integrated_ADPR` in main paper tables.
- Use `mean_per_agent_view_ADPR` to discuss local or partial dependency progress.
- Treat `SAD-proxy` as candidate evidence until dependency-version visibility logs are available.
- Treat duplicated contract symbols as coordination diagnostics, not as artifact hygiene violations.
- Keep raw run directories or shared-storage copies for reproducibility; this report only indexes them.
