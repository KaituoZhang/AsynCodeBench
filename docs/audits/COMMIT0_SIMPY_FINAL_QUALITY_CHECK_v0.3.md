# Commit0 SimPy final quality check — v0.3

Task: `commit0:simpy`  
Status: final AsynCodeBench construction, pending independent annotation
Date: 2026-06-26

## Decision

`commit0:simpy` is suitable for AsynCodeBench v0.3 qualification and agent
evaluation after independent annotation. All non-annotation dataset artifacts
are in place:

```text
manifests/pilot/v0.3/tasks/commit0_simpy.json
manifests/pilot/v0.3/scenarios/commit0_simpy.json
manifests/pilot/v0.3/quality/commit0_simpy.json
manifests/pilot/v0.3/metrics/commit0_simpy_async_metrics.json
manifests/annotations/asyncodebench_v0.3/simpy/
```

The task should remain `qualification_ready`, not `release_ready`, until the
two independent human annotations are completed and reconciled.

## Source-ref discipline

The local default/`commit0` branch for this repository is a complete
implementation. The actual stripped Commit0-style benchmark initial state is:

```text
origin/commit0_combined:25496719af798e5a276289279651873ea5b6e7d1
```

Any benchmark workspace for this task must be materialized from that stripped
ref, not from the local complete/default `commit0` branch.

## Why this fits AsynCodeBench

The task contains natural cross-agent dependencies:

1. `environment_core -> event_lifecycle`
   - Producer: `src/simpy/core.py`
   - Consumer: `src/simpy/events.py`, `src/simpy/exceptions.py`
   - Contract: scheduler/run/step/peek/timeout/process behavior must support
     event lifecycle, process resumption, callbacks, interrupts, and conditions.

2. `event_lifecycle -> resource_layer`
   - Producer: `src/simpy/events.py`
   - Consumer: `src/simpy/resources/*.py`
   - Contract: resources, containers, stores, queues, and immediate requests
     must consume event triggering/callback/process semantics consistently.

3. `environment_core -> realtime_and_utilities`
   - Producer: `src/simpy/core.py`
   - Consumer: `src/simpy/rt.py`, `src/simpy/util.py`
   - Contract: realtime pacing and delayed-start utilities depend on
     Environment.run(), timeout, process, and negative-delay semantics.

These dependencies are suitable for ADPR, DRS, CAIL, and SAD because downstream
workers can continue implementing resources or utilities against stale
scheduler/event assumptions and fail only after integration.

## Evaluator subset

The final v0.3 evaluator subset is:

```bash
PYTHONNOUSERSITE=1 \
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
PYTHONPATH=src \
python -m pytest tests -q -m 'not benchmark' -k 'not test_simpy_version'
```

Observed initial-state result on `origin/commit0_combined`:

```text
57 failed
82 passed
11 deselected
10 warnings
```

Observed complete/default sanity result on local `commit0`:

```text
139 passed
11 deselected
10 warnings
```

The initial failures are implementation failures in the event scheduler,
event lifecycle, resources, realtime, and utility layers. They are not import
errors, Docker errors, network failures, API-key failures, or package metadata
failures.

## Exclusions

The evaluator excludes:

- benchmark-marked tests;
- `tests/test_version.py::test_simpy_version`.

These exclusions are answer-free because they remove benchmarking infrastructure
and package metadata checks rather than implementation behavior.

## Remaining gate

The only remaining dataset gate is:

```text
two independent human inclusion/exclusion annotations
```

Single-agent, serial-specialist, and asynchronous-agent runs are benchmark
evaluation outputs. They should be reported in the paper, but they are not
dataset qualification gates.
