# Commit0 data + async-metric label guide — v0.3

Specification: `SPECIFICATION_v0.3.md`  
Base protocol: `docs/protocols/COMMIT0_DATA_EXAMPLE_GUIDE_v0.3.md`  
Status: operating guide for AsynCodeBench task construction
Primary example: `commit0:cachetools`

This document extends the Commit0 data-example guide with the dependency
labels needed by AsynCodeBench's async-specific metrics. All non-metric
requirements remain unchanged: use only public Commit0 evidence, preserve the
upstream task, do not inspect gold patches, and do not manufacture coordination
difficulty.

## 1. What changes relative to the base guide

The base guide already requires each task to identify natural subproblems and
publicly justified `dependency_annotations`. This guide adds one extra artifact:

```text
manifests/pilot/v0.3/metrics/commit0_<repo>_async_metrics.json
```

That metrics file records which cross-subproblem contracts should be tracked
during single-agent, synchronous multi-agent, and asynchronous multi-agent
runs.

The metrics labels do not replace task qualification. They answer a narrower
question:

```text
When did this run actually resolve the dependency that makes asynchronous
coordination hard?
```

## 2. Required metric concepts

Each task should define one or more `dependency_points`. A dependency point is
a public, test-observable contract between a producer subproblem and a consumer
subproblem.

The current metric set is:

- ADPR — Async Dependency Pass Rate. Fraction of labeled dependency points
  whose required integrated probe tests pass in the final integrated workspace.
- DRS — Dependency Resolution Step. First checkpoint or logical iteration where
  a dependency point's integrated probe tests pass.
- CAIL — Cross-Agent Integration Lag. Difference between downstream dependency
  resolution and upstream dependency resolution, when both can be observed.
- SAD — Stale Assumption Duration. Interval where a downstream agent continues
  acting on an upstream contract assumption that has become stale.

Use normal pass/fail metrics as before. These metrics add resolution timing and
dependency-level observability.

## 3. Required fields for one dependency point

Each dependency point should contain:

```text
dependency_id
dependency_type
producer_subproblem
consumer_subproblem
producer_agent
consumer_agent
producer_files
consumer_files
contract_summary
stale_failure_mode
upstream_probe_tests
downstream_probe_tests
integrated_probe_tests
resolution_criteria
metrics_enabled
```

Recommended optional fields:

```text
primary_paper_probe
notes
```

Allowed `dependency_type` values in the metrics manifest:

```text
interface_dependency
shared_api_contract
shared_state_contract
integration_contract
```

The `producer_subproblem` and `consumer_subproblem` names must match or clearly
map to the `natural_subproblems` and `dependency_annotations` in the task
record. The metrics file may use more specific IDs, but it must not introduce
a dependency that is absent from the task/scenario rationale.

## 4. Probe-test rules

Probe tests must be answer-free and public:

- use tests visible at `commit0`;
- prefer exact pytest node IDs: `tests/file.py::ClassName::test_name`;
- avoid tests that require network, private credentials, optional cloud
  services, or unfrozen system state;
- if an evaluator subset excludes an environment-only test, document that
  exclusion in the TaskQualityRecord;
- do not select probes by looking at reference patches or model outputs.

Each dependency point should have:

- at least one upstream probe that validates the producer-side contract;
- at least one downstream probe that validates consumer behavior;
- at least one integrated probe set that must pass after both artifacts are
  integrated.

For small tasks, upstream and integrated probes may overlap. That is acceptable
if the rationale explains why the same public test observes both the producer
contract and downstream integration.

## 5. Good dependency labels

Good labels identify the semantic contract that can become stale:

```text
keys.py typedkey contract -> func.py typed decorators
config.py default backend fallback -> repo.py init -> refs.py symbolic HEAD update
storage schema field type -> query/index consumer behavior
unicode version catalog ordering -> width matching algorithm
```

Weak labels merely restate file ownership:

```text
agent A edits file_a.py and agent B edits file_b.py
```

If the failure mode is only a textual merge conflict, the task may still be
useful, but it is not a strong async-dependency example. Prefer semantic
integration failures that can happen even when patches merge cleanly.

## 6. Cachetools reference pattern

`commit0:cachetools` uses:

```text
producer_subproblem: key_construction
consumer_subproblem: decorator_factories
primary dependency: keys.py typedkey semantics -> func.py typed decorators
primary probe: tests/test_keys.py::CacheKeysTest::test_typedkey
downstream probes: tests/test_func.py::*::test_decorator_typed
metric focus: DRS and SAD for stale typed/untyped key assumptions
```

This is the preferred pattern for future tasks:

1. identify the public producer contract;
2. identify consumer behavior that can be written incorrectly under stale
   assumptions;
3. attach exact public tests to upstream, downstream, and integrated checks;
4. record why this dependency is the async signal rather than generic task
   difficulty.

## 7. Output checklist for a transformed Commit0 task

For every newly transformed task, produce:

```text
src/asyncodebench/dataset/<repo>_v03.py
scripts/build_<repo>_v03_data.py
manifests/pilot/v0.3/tasks/commit0_<repo>.json
manifests/pilot/v0.3/scenarios/commit0_<repo>.json
manifests/pilot/v0.3/quality/commit0_<repo>.json
manifests/pilot/v0.3/metrics/commit0_<repo>_async_metrics.json
manifests/annotations/asyncodebench_v0.3/<repo>/annotator_a.json
manifests/annotations/asyncodebench_v0.3/<repo>/annotator_b.json
manifests/annotations/asyncodebench_v0.3/<repo>/adjudication.template.json
```

Recommended validation:

```bash
PYTHONNOUSERSITE=1 PYTHONPATH=src python scripts/build_<repo>_v03_data.py
PYTHONNOUSERSITE=1 PYTHONPATH=src python -m pytest -q tests/contracts/test_<repo>_dataset_v03.py
```

If a metric manifest is added, also add a lightweight contract test that checks:

- the metrics file has `schema_version == "0.3-async-metrics"`;
- every exact probe selector points to a public test function in the local
  Commit0 repository;
- the primary dependency has both upstream and downstream probes.

## 8. Release discipline

Do not mark a task `release_ready` just because the metric labels exist.
Metric labels are part of qualification, not a substitute for annotation.

Use `qualification_ready` when:

- the task/scenario/quality records are internally consistent;
- the evaluator subset is answer-free and documented;
- dependency points have public evidence and exact probes;
- independent annotation is still pending.

Use `release_ready` only after the dataset's release rules are satisfied.
