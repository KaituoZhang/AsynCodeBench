# AsynCodeBench Evaluation Metrics

This document explains the evaluation metrics used in the current
AsynCodeBench experiments, what each metric means, which artifacts it uses,
and how collaborators can compute the metrics from agent-run outputs.

The current main metrics are the first-round AsynCodeBench v0.3 metrics. They
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

These are the main AsynCodeBench metrics. They use the dependency labels in:

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

#### Strict Checkpoint Policy

For new runs, AsynCodeBench runners now write:

```text
dependency_probe_checkpoints.jsonl
```

This file is produced by the test side, not by the task annotations. The runner
executes the labeled probe tests at these points:

- after each subagent artifact is produced;
- after each artifact is merged into the integrated workspace;
- after the final integrated evaluator run.

Each checkpoint stores `logical_step`, `checkpoint_type`, `agent_id`,
`workspace_kind`, artifact versions, raw probe selector outcomes, and
per-dependency upstream/downstream/integrated pass states.

Strict metrics are then computed from those checkpoints:

```text
strict_DRS_d =
  first integrated-workspace checkpoint where integrated_probe_tests(d) pass

strict_CAIL_d =
  first downstream_probe_tests(d) pass step
  - first upstream_probe_tests(d) pass step
```

If either side is never observed, strict CAIL is unresolved rather than filled
with zero. Older runs without `dependency_probe_checkpoints.jsonl` can still
report final ADPR and proxy diagnostics, but they cannot support strict DRS or
strict CAIL retroactively.

#### Handling Unresolved Dependencies In Aggregates

`unresolved` is a valid failure outcome, not missing data. Do not drop
unresolved dependencies when computing aggregate statistics. Otherwise, systems
that solve only one easy dependency and fail the rest can look artificially
strong when DRS or CAIL is averaged only over resolved cases.

AsynCodeBench reports both raw/status metrics and penalized aggregate metrics.

Let:

```text
T = number of dependency-probe checkpoints observed in the run
```

For strict DRS, keep the raw value for interpretability:

```text
DRS_raw(d) =
  first integrated-resolution step for dependency d, if observed
  unresolved, otherwise
```

For aggregate statistics, use a penalized value:

```text
DRS_penalized(d) =
  DRS_raw(d), if dependency d is integrated-resolved
  T + 1, otherwise
```

This makes every unresolved dependency worse than any resolved dependency while
preserving the interpretation that smaller DRS is better.

When comparing across tasks with different checkpoint counts, optionally report
a normalized dependency-resolution efficiency:

```text
DRE(d) =
  1 - (DRS_penalized(d) - 1) / T, if dependency d is resolved
  0, otherwise
```

Thus:

```text
resolved at step 1      -> DRE = 1
resolved at final step T -> DRE = 1 / T
unresolved              -> DRE = 0
```

For strict CAIL, keep the raw value when both upstream and downstream steps are
observed:

```text
CAIL_raw(d) = downstream_resolution_step_d - upstream_resolution_step_d
```

For aggregate lag statistics, use a penalized value:

```text
CAIL_penalized(d) =
  max(0, downstream_resolution_step_d - upstream_resolution_step_d),
    if both upstream and downstream steps are observed

  T + 1 - upstream_resolution_step_d,
    if upstream is observed but downstream is unresolved

  T + 1,
    if upstream is unresolved
```

The first case measures observed consumer lag. The second case penalizes a
consumer that never catches up after the producer contract becomes available.
The third case handles cases where the producer side itself never becomes
available.

Main aggregate tables should therefore report:

```text
ADPR
unresolved dependency count
mean DRS_penalized
mean CAIL_penalized
```

Case-study tables should additionally report the raw/status view:

```text
dependency outcome
upstream step
downstream step
DRS_raw
CAIL_raw
```

For example, suppose a run has `T = 13` checkpoints and two dependencies.
If CAID resolves producer-side probes at steps 3 and 11 but never resolves the
consumer-side integrated behavior, then:

```text
ADPR = 0 / 2 = 0
DRS_penalized = [14, 14]
mean DRS_penalized = 14
CAIL_penalized = [14 - 3, 14 - 11] = [11, 3]
mean CAIL_penalized = 7
unresolved dependency count = 2
```

This is preferable to reporting DRS/CAIL as `N/A`: the raw status remains
`unresolved`, while the aggregate table still penalizes the failed dependency
resolution.

`not_collected` should be handled carefully. If probes cannot collect because
the model introduced a syntax error, import error, or broken package state,
count the dependency as unresolved and also report the artifact or integration
failure. If probes cannot collect because of runner instrumentation or missing
environment setup, fix the run before using it in aggregate statistics.

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

New native runs compute strict dependency and process metrics automatically and
freeze them in a validated result bundle. Each formal run directory contains:

```text
report.json
cost.json
runtime.txt
outputs.jsonl
agent_events/*.jsonl
patch.diff
protocol.json
delegations.json
run_metadata.json
task_snapshot.json
scenario_snapshot.json
scenario_manifest_snapshot.json
metrics_snapshot.json
quality_snapshot.json
execution_profile_snapshot.json
dependency_probe_checkpoints.jsonl
process_metrics_summary.json
run_bundle.json
<repo>_test_output.txt
```

Run `asyncodebench validate-run <run-dir>` before aggregation. The eligibility
flags in `run_bundle.json` determine which metric families may be used. See
`docs/RESULT_VALIDITY.md`.

The per-task summarizer copies those flags into both the metrics CSV and the
artifact index. `scripts/aggregate_model_task_results.py` rejects every row
without `official_aggregate_eligible=true` by default. The
`--allow-ineligible` override is reserved for clearly labeled exploratory or
legacy analyses.

Final success additionally requires a positive collected-test count. A zero
exit code with `0 collected` is evaluator evidence failure, not a successful
coding result.

For model-level results, the aggregator emits a campaign manifest linking each
metric row to the corresponding run-bundle checksum. It also verifies one model
ID, one bundle-recorded agent-adapter identity, one execution-profile ID and
SHA256, and one per-task generation configuration across compared protocols.
This lineage is part of result validity, not a performance metric.

### Native Metric Generation

The native runner invokes the strict dependency and process analysis before it
freezes `run_bundle.json`. No manual metric command is required for a successful
run. The generated `process_metrics_summary.json` contains:

- `primary_outcome`: final pass/fail summary;
- `cost_metrics`: cost, tokens, runtime, model calls, test invocations;
- `dependency_metrics`: ADPR, DRS, upstream/downstream, CAIL, SAD-proxy;
- `process_metrics`: failed attempts, merge conflicts, scope violations,
  duplicated contract candidates, and recovery diagnostics;
- `formal_metrics`: compatibility summary for downstream scripts.

Do not regenerate or replace this file inside a bundled run directory. Any
post-run audit must write to a separate derived-output path, as shown in
[`ASYNCODEBENCH_HARNESS_V2.md`](ASYNCODEBENCH_HARNESS_V2.md).

### Derived Reports

After all four task protocols validate, use
`scripts/summarize_model_task_runs.py` to create the task Markdown, metrics CSV,
and artifact index outside the immutable run directories. After all 16 task
reports exist, use `scripts/aggregate_model_task_results.py` to create the
model-level tables and campaign manifest. Copy-ready commands are in
[`MODEL_EXPERIMENT_RUNBOOK.md`](MODEL_EXPERIMENT_RUNBOOK.md).

Historical v1 directories without formal bundles may still be analyzed for a
clearly labeled migration appendix. They cannot support a current official
aggregate and must not be mixed with native bundled runs.

## Historical Cachetools Pilot Interpretation

The following pre-bundle pilot motivated the benchmark metrics. It is not a
current official native-harness result table.

For `cachetools + gpt-5.4-mini`, the four current modes all pass final tests:

| Mode | Final tests | Cost | Tokens | ADPR |
| --- | ---: | ---: | ---: | ---: |
| single | 215/215 | $0.2723 | 1.38M | 1.0 |
| serial_specialists | 215/215 | $0.2720 | 1.24M | 1.0 |
| async_private | 215/215 | $0.2369 | 0.97M | 1.0 |
| caid_manager | 215/215 | $1.0728 | 4.66M | 1.0 |

The dependency and coordination metrics distinguish the protocols:

- `serial_specialists` is clean: no failed attempts, no merge conflicts, no
  scope violations, and no SAD proxy.
- `async_private` passes final tests but shows stale-dependency evidence:
  `SAD-proxy = 8` for the typed key dependency view, duplicated producer
  contract symbols in `func.py`, and undelivered producer-update work.
- `caid_manager` passes final tests but requires much more recovery:
  8 subagent attempts, 5 non-merged attempts under the current accounting,
  2 merge conflicts, 1 scope violation, and manager recovery.

The key claim is:

```text
Final pass/fail hides async coordination quality. AsynCodeBench exposes when
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
