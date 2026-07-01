# AsyncCodeBench Evaluation Metrics

This document explains the evaluation metrics used in the current
AsyncCodeBench experiments, what each metric means, which artifacts it uses,
and how collaborators can compute the metrics from agent-run outputs.

The current main metrics are the first-round AsyncCodeBench v0.3 metrics. They
are dependency-centered: the goal is not only to know whether the final
repository passes tests, but also when the labeled cross-agent software
dependencies are resolved and what coordination burden was required.

## Metric Groups

### 1. Traditional Coding Metrics

These are standard coding benchmark metrics. They are necessary, but they do
not explain asynchronous coordination behavior.

| Metric | Meaning | Required artifacts |
| --- | --- | --- |
| Final Pass / Final Tests | Number of final evaluator tests passed out of tests collected | `report.json` |
| FSR | Successful runs divided by total repeated runs | repeated `report.json` files |
| Cost | API cost in dollars | `cost.json` |
| Tokens | Input plus output tokens | `cost.json` |
| Runtime | Agent runtime and wall-clock duration | `runtime.txt`, `cost.json` |

Example:

```text
Final Pass = 215/215
```

This means the final integrated repository passes all evaluator tests. It does
not show whether the run had stale assumptions, delayed dependency resolution,
merge conflicts, or failed subagent attempts.

### 2. Dependency-Level Metrics

These are the main AsyncCodeBench metrics. They use the dependency labels in:

```text
manifests/pilot/v0.3/metrics/commit0_<repo>_async_metrics.json
```

Each dependency point provides:

- `dependency_id`
- `producer_agent` and `consumer_agent`
- `producer_files` and `consumer_files`
- `upstream_probe_tests`
- `downstream_probe_tests`
- `integrated_probe_tests`
- `resolution_criteria`
- `stale_failure_mode`

#### ADPR: Async Dependency Pass Rate

```text
ADPR = resolved_dependency_points / total_dependency_points
```

A dependency point is resolved when its required integrated probe tests pass in
the final integrated workspace.

For paper tables, state whether the denominator is all dependency points or the
task's `primary_async_dependency_ids`.

#### DRS: Dependency Resolution Step

```text
DRS_d = first checkpoint or logical iteration where integrated_probe_tests(d) pass
```

`DRS` answers when dependency `d` was first observed to be resolved.

Use two variants when available:

```text
strict DRS_d =
  first integrated checkpoint where upstream and downstream probes for d pass
  in the same integrated workspace
```

```text
composed DRS_d =
  max(upstream_resolution_step_d, downstream_resolution_step_d)
```

Use strict DRS in main tables. Use composed DRS as a diagnostic when upstream
and downstream probes are observed at different checkpoints.

#### Upstream And Downstream Resolution

```text
upstream_resolution_step_d =
  first checkpoint where upstream_probe_tests(d) pass

downstream_resolution_step_d =
  first checkpoint where downstream_probe_tests(d) pass
```

These metrics separate producer-side correctness from consumer-side adaptation.
They show whether a run was blocked by the upstream implementation, downstream
adaptation, or late integration.

#### CAIL: Cross-Agent Integration Lag

```text
CAIL_d = downstream_resolution_step_d - upstream_resolution_step_d
```

Positive `CAIL` means the downstream consumer lagged behind the producer
contract. A zero value can mean clean synchronization, or it can mean the
runner only observed both sides at the same final checkpoint. Always report
the checkpoint policy.

#### SAD: Stale Assumption Duration

```text
SAD_d =
  duration or iteration interval where the consumer continues acting on a
  producer-contract assumption that has become stale
```

Strict automatic `SAD` requires dependency-version visibility logs. Current
runs may report `SAD-proxy`, based on evidence such as:

- downstream probes passing before upstream probes in the event-log view;
- consumer edits to `consumer_files` without producer artifact visibility;
- duplicated implementation of a producer-side contract in a consumer file;
- consumer work after a relevant producer artifact finished but could not be
  delivered under the protocol.

`SAR` can be added later as a rate version of `SAD`:

```text
SAR_d = stale dependency-sensitive consumer attempts for d
        / dependency-sensitive consumer attempts for d
```

In the current paper draft, `SAD` is the main metric and `SAR` is an optional
extension.

### 3. Coordination-Level Diagnostics

These metrics explain how a protocol reached the final result.

| Metric | Definition | Required artifacts |
| --- | --- | --- |
| Failed Subagent Rate | Subagent attempts without a usable committed or merged artifact divided by total subagent attempts | `outputs.jsonl`, `cost.json`, `agent_events/` |
| Merge Conflict Count | Number of textual merge conflicts during integration | `outputs.jsonl`, manager review events |
| Scope Violation Count | Number of agents modifying files outside assigned writable paths | `protocol.json`, `delegations.json`, `patch.diff`, `outputs.jsonl` |
| Manager Recovery Required | True if final success depends on manager review, merge repair, reassignment, or final recovery after failed subagent artifacts | manager events and review events |

These are not replacements for dependency metrics. They explain why two runs
with the same final pass result can have different async coordination quality.

## Computation Pipeline

Each run directory should contain artifacts like:

```text
report.json
cost.json
runtime.txt
outputs.jsonl
agent_events/*.jsonl
patch.diff
protocol.json
delegations.json
<repo>_test_output.txt
```

The metrics computation has two steps.

### Step 1: Compute Dependency Resolution Reports

Use:

```text
scripts/analyze_async_dependency_resolution.py
```

Example for a static protocol run:

```bash
python scripts/analyze_async_dependency_resolution.py \
  --metrics manifests/pilot/v0.3/metrics/commit0_cachetools_async_metrics.json \
  --events reproductions/async-swe-agents/outputs/repro_commit0/cachetools/gpt54mini_async_private_iter30_metrics_v03/agent_events/decorator_agent_events.jsonl \
  --final-test-output reproductions/async-swe-agents/outputs/repro_commit0/cachetools/gpt54mini_async_private_iter30_metrics_v03/cachetools_test_output.txt \
  --output reproductions/async-swe-agents/outputs/repro_commit0/cachetools/gpt54mini_async_private_iter30_metrics_v03/async_dependency_resolution_decorator_agent.json
```

Run this once per relevant agent event log. For CAID, run it for each engineer
and manager event log when available.

The output contains:

- `ADPR_strict`
- per-dependency strict DRS;
- composed DRS;
- upstream/downstream resolution steps;
- checkpoint counts.

### Step 2: Aggregate Run-Level Process Metrics

Use:

```text
scripts/analyze_run_process_metrics.py
```

Example:

```bash
python scripts/analyze_run_process_metrics.py \
  --run-dir reproductions/async-swe-agents/outputs/repro_commit0/cachetools/gpt54mini_async_private_iter30_metrics_v03 \
  --baseline-run-dir reproductions/async-swe-agents/outputs/repro_commit0/cachetools/gpt54mini_serial_iter30_metrics_v03 \
  --metrics manifests/pilot/v0.3/metrics/commit0_cachetools_async_metrics.json \
  --output reproductions/async-swe-agents/outputs/repro_commit0/cachetools/gpt54mini_async_private_iter30_metrics_v03/process_metrics_summary.json \
  --print-summary
```

The output file `process_metrics_summary.json` contains:

- `primary_outcome`: final pass/fail summary;
- `cost_metrics`: cost, tokens, runtime, model calls, test invocations;
- `dependency_metrics`: ADPR, DRS, upstream/downstream, CAIL, SAD-proxy;
- `process_metrics`: failed attempts, merge conflicts, scope violations,
  duplicated contract candidates, and recovery diagnostics;
- `formal_metrics`: compatibility summary for downstream scripts.

## Cachetools Pilot Interpretation

For `cachetools + gpt-5.4-mini`, the four current modes all pass final tests:

| Mode | Final tests | Cost | Tokens | ADPR |
| --- | ---: | ---: | ---: | ---: |
| single | 215/215 | $0.2723 | 1.38M | 1.0 |
| serial_specialists | 215/215 | $0.2720 | 1.24M | 1.0 |
| async_private | 215/215 | $0.2369 | 0.97M | 1.0 |
| CAID_multi_agent | 215/215 | $1.0728 | 4.66M | 1.0 |

The dependency and coordination metrics distinguish the protocols:

- `serial_specialists` is clean: no failed attempts, no merge conflicts, no
  scope violations, and no SAD proxy.
- `async_private` passes final tests but shows stale-dependency evidence:
  `SAD-proxy = 8` for the typed key dependency view, duplicated producer
  contract symbols in `func.py`, and undelivered producer-update work.
- `CAID_multi_agent` passes final tests but requires much more recovery:
  8 subagent attempts, 5 non-merged attempts under the current accounting,
  2 merge conflicts, 1 scope violation, and manager recovery.

The key claim is:

```text
Final pass/fail hides async coordination quality. AsyncCodeBench exposes when
cross-agent dependencies are resolved, whether downstream work proceeds under
stale or missing producer information, and how much recovery burden is needed
to reach a passing final repository.
```

## Current Limitations

- Strict `SAD` requires dependency-version visibility logs. Current runs can
  report `SAD-proxy`; strict automatic `SAD` should be enabled by adding
  runner-side dependency-version instrumentation.
- DRS and CAIL quality depends on checkpoint frequency. If probes only run at
  final integration, DRS is an observed resolution step, not necessarily the
  true earliest semantic fix.
- Coordination diagnostics depend on runner event quality. Keep `outputs.jsonl`,
  `agent_events/`, `protocol.json`, and `delegations.json` with every run.

