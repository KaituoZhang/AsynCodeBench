# Commit0 Dulwich final quality check — v0.3

> Archived record: Dulwich is not part of the official AsynCodeBench v0.3
> 16-task release. Referenced construction artifacts now live under
> `archive/non_official/commit0_v0.3/`.

Task: `commit0:dulwich`
Status: final AsynCodeBench construction, pending independent annotation
Date: 2026-06-26

## Decision

`commit0:dulwich` is suitable for AsynCodeBench v0.3 qualification and agent
evaluation after independent annotation. All non-annotation dataset artifacts
are in place:

```text
manifests/pilot/v0.3/tasks/commit0_dulwich.json
manifests/pilot/v0.3/scenarios/commit0_dulwich.json
manifests/pilot/v0.3/quality/commit0_dulwich.json
manifests/pilot/v0.3/metrics/commit0_dulwich_async_metrics.json
manifests/annotations/commit0_v0.3/dulwich/
```

The task should remain `qualification_ready`, not `release_ready`, until the
two independent human annotations are completed and reconciled.

## Why this fits AsynCodeBench

The task contains natural cross-agent dependencies rather than arbitrary file
splits:

1. `config_defaults -> repo_refs_integration`
   - Producer: `dulwich/config.py`
   - Consumer: `dulwich/repo.py`, `dulwich/refs.py`
   - Contract: unavailable default config files should be treated as absent
     sources so repository initialization and symbolic ref updates can proceed.
   - Primary probes:
     - `tests/test_config.py::StackedConfigTests::test_default_backends`
     - `tests/test_refs.py::DiskRefsContainerTests::test_add_if_new_symbolic`

2. `pack_format_layer -> object_store_layer`
   - Producer: `dulwich/pack.py`, `dulwich/objects.py`
   - Consumer: `dulwich/object_store.py`
   - Contract: object-store `add_pack` behavior depends on pack lookup,
     iteration, checksum, and raw-object semantics.
   - Primary probes:
     - `tests/test_pack.py::TestPack::test_get`
     - `tests/test_object_store.py::DiskObjectStoreTests::test_add_pack`

These dependencies are appropriate for dependency-level metrics such as ADPR,
DRS, CAIL, and SAD. The config/ref dependency is the primary paper probe.

## Evaluator subset

The final v0.3 evaluator subset is:

```bash
PYTHONNOUSERSITE=1 \
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
PYTHONPATH=. \
python -m pytest -q \
  tests/test_object_store.py \
  tests/test_pack.py \
  tests/test_refs.py \
  tests/test_config.py \
  tests/test_objectspec.py \
  tests/test_objects.py \
  tests/test_diff_tree.py \
  tests/test_walk.py
```

Observed initial-state result in the AsynCodeBench conda environment:

```text
2 failed
526 passed
11 skipped
1 xfailed
2 warnings
```

The two failures are the intended public task signal:

```text
tests/test_config.py::StackedConfigTests::test_default_backends
tests/test_refs.py::DiskRefsContainerTests::test_add_if_new_symbolic
```

They fail because `StackedConfig.default_backends()` tries to read
`/nonexistent/.gitconfig` and raises `PermissionError` under the public test
environment. This is a code-level config/repo/refs contract failure, not an
agent-runner, Docker, network, or API-key failure.

## Exclusions

The evaluator excludes full-suite areas that are not necessary for the core
AsynCodeBench task:

- `fuzzing/fuzz-targets/*`, which requires optional `atheris`;
- `tests/contrib/test_swift_smoke.py`, which requires optional `gevent`;
- broader compatibility/contrib smoke coverage not part of the selected
  config/refs/object-store task.

The exclusions are answer-free because they remove optional environment-heavy
tests rather than adding implementation behavior.

## Completed-version sanity

Completed-version evaluator sanity is unavailable in the local Commit0
materialization:

- `origin/master` points to the same SHA as `commit0`;
- `origin/commit0_combined` exists but collection fails for this evaluator;
- `origin/upstream` uses an incompatible test layout.

This is recorded as a limitation, not as a remaining qualification gate.

## Remaining gate

The only remaining dataset gate is:

```text
two independent human inclusion/exclusion annotations
```

Single-agent, serial-specialist, and asynchronous-agent runs are benchmark
evaluation outputs. They should be reported in the paper, but they are not
dataset qualification gates.
