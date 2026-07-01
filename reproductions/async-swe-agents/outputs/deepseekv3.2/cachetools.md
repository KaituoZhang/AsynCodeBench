# DeepSeek-V3.2 Cachetools Experiment Report

Task: `commit0:cachetools`

Model: `deepinfra/deepseek-ai/DeepSeek-V3.2`

Date: 2026-07-01

Run directories:

- `outputs/repro_commit0/cachetools/deepseek_v32_single_i30`
- `outputs/repro_commit0/cachetools/deepseek_v32_serial_2agents_s30`
- `outputs/repro_commit0/cachetools/deepseek_v32_async_private_2agents_s30`
- `outputs/repro_commit0/cachetools/deepseek_v32_caid_multi_2agents_m30_s30`

Metric source files:

- `report.json`
- `cost.json`
- `runtime.txt`
- `patch.diff`
- `async_dependency_resolution_*.json`
- `process_metrics_summary.json`

## Summary

These DeepSeek-V3.2 runs do not constitute successful solve runs: all four protocols fail final evaluation. However, they are useful asynchronous-coordination stress cases. The key finding is that final test counts alone hide important asynchronous behavior. AsyncCodeBench dependency-level and coordination-level metrics expose cross-agent lag, failed subagent attempts, integration burden, and artifact hygiene issues.

The strongest asynchronous evidence is:

- `async_private` and `CAID_multi` have real asynchronous overlap: 729.3s and 826.4s.
- `async_private` and `CAID_multi` improve ADPR over `serial_specialists`, but do not produce final success.
- `CAID_multi` shows repeated `CAIL=26` in the engineer1 view, indicating delayed downstream dependency resolution after upstream progress.
- Multi-agent modes have `FSAR=1.0` and `IFR=1.0`, showing non-clean subagent attempts and integration failure.
- `CAID_multi` pollutes the patch with temporary files, including `func.py.backup`, `test_decorator.py`, `test_keys_impl.py`, and `test_prototype.py`.

## Overall Metrics

| Mode | Final tests | Final success | ADPR | DRS score | FSR | FSAR | IFR | SVR | Runtime | Tokens |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| single | 166/215 | false | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | N/A | 410.7s | 718,102 |
| serial_specialists | 198/215 | false | 0.2 | 0.2 | 0.0 | 1.0 | 1.0 | 0.0 | 1699.9s | 1,441,639 |
| async_private | 179/215 | false | 0.6 | 0.6 | 0.0 | 1.0 | 1.0 | 0.0 | 806.5s | 1,389,591 |
| CAID_multi | 198/215 | false | 0.6 | 0.6 | 0.0 | 1.0 | 1.0 | 0.0 | 5211.9s | 19,148 |

Note: CAID token accounting appears incomplete because the DeepSeek JSON delegation adapter and LiteLLM accounting did not fully populate `cost.json`. Use the DeepInfra dashboard as the source of truth for billing.

## Asynchronous Overlap

| Mode | Async overlap |
| --- | ---: |
| single | 0.0s |
| serial_specialists | 0.0s |
| async_private | 729.3s |
| CAID_multi | 826.4s |

Interpretation: `async_private` and `CAID_multi` performed actual concurrent work. This lets us compare asynchronous coordination behavior against serial execution.

## Dependency-Level Metrics

Dependency abbreviations:

- `untyped`: `cachetools.keys_to_func.untyped_key_contract`
- `typed`: `cachetools.keys_to_func.typed_key_contract`
- `typedmethod`: `cachetools.keys_to_cachedmethod.typed_method_key_contract`
- `metadata`: `cachetools.core_to_func.wrapper_metadata_contract`
- `maxsize_lock`: `cachetools.core_to_func.maxsize_and_lock_contract`

`None` means the run did not observe a complete upstream/downstream/integrated resolution for that dependency point, so `CAIL` cannot be computed.

### single

Report: `async_dependency_resolution_single_agent_events.json`

ADPR: `0/5 = 0.0`

| Dependency | DRS | Upstream | Downstream | CAIL | Composed DRS |
| --- | ---: | ---: | ---: | ---: | ---: |
| untyped | None | None | None | None | None |
| typed | None | None | None | None | None |
| typedmethod | None | None | None | None | None |
| metadata | None | None | None | None | None |
| maxsize_lock | None | None | None | None | None |

### serial_specialists

Reports:

- `async_dependency_resolution_decorator_agent_events.json`
- `async_dependency_resolution_key_agent_events.json`

Both reports have the same observed dependency result.

ADPR: `1/5 = 0.2`

| Dependency | DRS | Upstream | Downstream | CAIL | Composed DRS |
| --- | ---: | ---: | ---: | ---: | ---: |
| untyped | None | 31 | None | None | None |
| typed | None | 31 | None | None | None |
| typedmethod | 31 | 31 | 31 | 0 | 31 |
| metadata | None | 31 | None | None | None |
| maxsize_lock | None | 31 | None | None | None |

Interpretation: serial execution avoids overlap but resolves only one labeled dependency point. Most downstream dependency points remain unresolved.

### async_private

Report: `async_dependency_resolution_decorator_agent_events.json`

ADPR: `5/5 = 1.0`

| Dependency | DRS | Upstream | Downstream | CAIL | Composed DRS |
| --- | ---: | ---: | ---: | ---: | ---: |
| untyped | 9 | 9 | 9 | 0 | 9 |
| typed | 9 | 9 | 9 | 0 | 9 |
| typedmethod | 9 | 9 | 9 | 0 | 9 |
| metadata | 9 | 9 | 9 | 0 | 9 |
| maxsize_lock | 9 | 9 | 9 | 0 | 9 |

Report: `async_dependency_resolution_key_agent_events.json`

ADPR: `1/5 = 0.2`

| Dependency | DRS | Upstream | Downstream | CAIL | Composed DRS |
| --- | ---: | ---: | ---: | ---: | ---: |
| untyped | None | 5 | None | None | None |
| typed | None | 5 | None | None | None |
| typedmethod | 31 | 5 | 31 | 26 | 31 |
| metadata | None | 31 | None | None | None |
| maxsize_lock | None | 31 | None | None | None |

Mean ADPR: `0.6`

Interpretation: async-private shows mixed dependency behavior. One view resolves all dependency points with `CAIL=0`, while another shows delayed downstream resolution for `typedmethod` with `CAIL=26`. Final tests are worse than serial despite the higher mean ADPR.

### CAID_multi

Report: `async_dependency_resolution_engineer1_events.json`

ADPR: `3/5 = 0.6`

| Dependency | DRS | Upstream | Downstream | CAIL | Composed DRS |
| --- | ---: | ---: | ---: | ---: | ---: |
| untyped | None | 4 | 30 | 26 | 30 |
| typed | None | 4 | 30 | 26 | 30 |
| typedmethod | 4 | 4 | 4 | 0 | 4 |
| metadata | 30 | 4 | 30 | 26 | 30 |
| maxsize_lock | 30 | 4 | 30 | 26 | 30 |

Report: `async_dependency_resolution_engineer2_events.json`

ADPR: `5/5 = 1.0`

| Dependency | DRS | Upstream | Downstream | CAIL | Composed DRS |
| --- | ---: | ---: | ---: | ---: | ---: |
| untyped | 16 | 16 | 16 | 0 | 16 |
| typed | 16 | 16 | 16 | 0 | 16 |
| typedmethod | 16 | 16 | 16 | 0 | 16 |
| metadata | 16 | 16 | 16 | 0 | 16 |
| maxsize_lock | 16 | 16 | 16 | 0 | 16 |

Report: `async_dependency_resolution_manager_events.json`

ADPR: `1/5 = 0.2`

| Dependency | DRS | Upstream | Downstream | CAIL | Composed DRS |
| --- | ---: | ---: | ---: | ---: | ---: |
| untyped | None | 99 | None | None | None |
| typed | None | 99 | None | None | None |
| typedmethod | 99 | 99 | 99 | 0 | 99 |
| metadata | None | 99 | None | None | None |
| maxsize_lock | None | 99 | None | None | None |

Mean ADPR: `0.6`

Interpretation: CAID_multi has real asynchronous overlap and improves dependency progress over serial, but it exposes a strong coordination-lag pattern. In the engineer1 view, four dependencies show `CAIL=26`, meaning upstream progress is observed at step 4 while downstream or integrated resolution appears at step 30.

## Coordination-Level Diagnostics

| Mode | Agent attempts | Failed attempts | Manager reviews | Merged reviews | Textual conflict | Semantic integration failure |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| single | 1 | 0 | 0 | 0 | false | false |
| serial_specialists | 2 | 2 | 2 | 2 | false | true |
| async_private | 2 | 2 | 2 | 2 | false | true |
| CAID_multi | 4 | 4 | 4 | 3 | true | false |

CAID_multi modified files:

- `src/cachetools/func.py`
- `src/cachetools/func.py.backup`
- `src/cachetools/keys.py`
- `test_decorator.py`
- `test_keys_impl.py`
- `test_prototype.py`

Interpretation: CAID_multi shows the strongest evidence of coordination and artifact hygiene problems. It reaches the same final test count as serial, but requires much more wall-clock time, has real overlap, has failed subagent attempts, and produces extra temporary files.

## Main Claim Supported by This Experiment

This DeepSeek-V3.2 experiment should not be presented as a successful solve result. It should be presented as evidence that AsyncCodeBench metrics reveal asynchronous coordination failures that final tests alone hide.

Final test counts alone say:

| Mode | Final tests |
| --- | ---: |
| serial_specialists | 198/215 |
| CAID_multi | 198/215 |

AsyncCodeBench metrics show that these are not equivalent:

- `serial_specialists`: no overlap, ADPR 0.2, runtime 1699.9s.
- `CAID_multi`: 826.4s overlap, mean ADPR 0.6, repeated `CAIL=26`, runtime 5211.9s, failed subagent attempts, textual/integration burden, and extra artifacts.

Suggested wording:

> Although serial and CAID_multi reach the same final pass count, AsyncCodeBench metrics reveal that they are not equivalent. CAID_multi obtains this result under substantial asynchronous coordination burden: nonzero overlap, delayed downstream dependency resolution, failed subagent attempts, and integration/hygiene issues. This validates the benchmark design: dependency-level metrics expose asynchronous failure modes hidden by final test counts.

## Limitations

- All four DeepSeek-V3.2 runs fail final evaluation, so `FSR=0` for this model/task setting.
- `SAD` and `SAR` remain proxy-only in the current logs. Strict automatic stale-assumption duration requires structured artifact-visibility or dependency-version logs.
- CAID token accounting appears incomplete in `cost.json`; billing should be checked against DeepInfra.
- The DeepSeek runs used the JSON delegation adapter, so they should be labeled separately from native GPT-style manager delegation runs.

## Recompute Metrics

From WSL:

```bash
cd ~/AsynccodeBench/Asynccodebench

METRICS=manifests/pilot/v0.3/metrics/commit0_cachetools_async_metrics.json

for RUN in \
  reproductions/async-swe-agents/outputs/repro_commit0/cachetools/deepseek_v32_single_i30 \
  reproductions/async-swe-agents/outputs/repro_commit0/cachetools/deepseek_v32_serial_2agents_s30 \
  reproductions/async-swe-agents/outputs/repro_commit0/cachetools/deepseek_v32_async_private_2agents_s30 \
  reproductions/async-swe-agents/outputs/repro_commit0/cachetools/deepseek_v32_caid_multi_2agents_m30_s30
do
  for EVENTS in "$RUN"/agent_events/*.jsonl
  do
    [ -e "$EVENTS" ] || continue
    NAME=$(basename "$EVENTS" .jsonl)

    PYTHONPATH=src python3 scripts/analyze_async_dependency_resolution.py \
      --metrics "$METRICS" \
      --events "$EVENTS" \
      --final-test-output "$RUN/cachetools_test_output.txt" \
      --output "$RUN/async_dependency_resolution_${NAME}.json"
  done

  PYTHONPATH=src python3 scripts/analyze_run_process_metrics.py \
    --run-dir "$RUN" \
    --metrics "$METRICS" \
    --output "$RUN/process_metrics_summary.json" \
    --print-summary
done
```
