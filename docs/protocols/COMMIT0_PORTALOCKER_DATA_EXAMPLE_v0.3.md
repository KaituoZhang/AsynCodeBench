# Commit0 Portalocker curated data example — v0.3

Specification: `SPECIFICATION_v0.3.md`  
Status: curated task; `qualification_ready`  
Task: `commit0:portalocker`

This document records how Portalocker is converted into a reproducible POSIX
core task that satisfies the AsyncCodeBench data-quality requirements without
copying substantive locking behavior from a completed implementation.

## 1. Task identity

```text
repository: data/repos/commit0/portalocker
origin: https://github.com/commit-0/portalocker.git
commit0 SHA: 300136afca11ea23c79ecfd110ed0d2819322f11
completed evaluator-sanity tag: v2.10.1

curated overlay:
  data/overlays/commit0/portalocker/0001-import-bootstrap.patch
overlay SHA-256:
  954c4855872d8c4695e981cc257f72a22a4d6e5302f09f0965c2062cee8d6c54
```

The decomposition uses only public Commit0 source, docstrings, tests, and
static dependencies. The completed tag is used only for evaluator sanity.

## 2. Corrected implementation surface

Automatic incomplete-marker extraction included false positives:

- exception subclasses are intentionally empty;
- `HasFileno` is a Protocol declaration.

The POSIX core task has two substantive layers:

```text
platform_lock_backend:
  portalocker/portalocker.py
  lock(), unlock(), flags, OS-error translation

file_lock_utilities:
  portalocker/utils.py
  coalesce, open_atomic, Lock, RLock, TemporaryFileLock,
  BoundedSemaphore and NamedBoundedSemaphore
```

`portalocker/redis.py` is not part of this task.

## 3. Curated bootstrap

Raw Commit0 cannot import because `portalocker/__init__.py` exports:

```text
portalocker.portalocker.lock
portalocker.portalocker.unlock
```

but those symbols are absent. The versioned overlay adds:

```python
def lock(file, flags):
    pass


def unlock(file):
    pass
```

These stubs only satisfy package-level symbol lookup. They do not implement
POSIX locking, conflict detection, exception translation, unlocking, timeout
behavior, or file lifecycle. In fact, the majority of tests continue to fail.

The workspace is reconstructed with:

```bash
cd /path/to/AsyncCodeBench
PYTHONPATH=src python scripts/materialize_curated_commit0_task.py \
  commit0:portalocker
```

Output:

```text
data/processed/commit0_curated/v0.3/portalocker
```

The raw repository remains unchanged.

## 4. Why Redis is excluded

The upstream Redis tests require:

```text
the redis Python package
a running Redis service
network/service lifecycle management
```

This creates an external-service condition unrelated to the first-paper
freshness question. The default evaluator therefore excludes:

```text
portalocker_tests/test_redis.py
```

RedisLock may become a future optional extension with its own frozen service
profile. It is not silently skipped or counted in the core task.

## 5. Coordination structure

Portalocker has a natural Interface Dependency:

```text
platform lock/unlock + flags + exception semantics
                         ↓
Lock/RLock timeout and retry behavior
                         ↓
temporary-file and semaphore lifecycle
```

The utilities specialist can implement local helpers and public doctests while
the backend is still in flight. However, it must make assumptions about:

- which OS errors become `AlreadyLocked` versus `LockException`;
- whether file objects or integer descriptors are accepted;
- how non-blocking flags are validated;
- how unlock is performed;
- whether retries should continue after a backend exception.

Stale or inconsistent assumptions can therefore merge without textual Git
conflicts and still break integrated locking behavior.

## 6. Natural specialist split

```text
backend_agent:
  writable: portalocker/portalocker.py
  owns direct POSIX backend tests

utilities_agent:
  writable: portalocker/utils.py
  owns public helper/semaphore doctests
```

The earlier three-agent design was rejected. Redis is an optional service
extension, not a reliable core specialist for this task.

## 7. Evaluator evidence

Raw Commit0:

```text
collected: 0
return code: 4
reason: package-level lock symbol is absent
```

Curated POSIX core initial state:

```text
collected: 40
passed: 8
failed: 32
errors: 0
return code: 1
```

Specialist-local groups:

```text
platform_backend_local:
  10 selected
  5 passed
  5 failed

utilities_local_doctest:
  4 selected
  0 passed
  4 failed
```

Cross-subproblem group:

```text
backend_utilities_cross_contract:
  31 selected
  4 passed
  27 failed
```

Completed public v2.10.1 sanity:

```text
40 passed
0 failed
0 errors
```

The initial passing tests include false-positive controls enabled by no-op
stubs. They must not be counted as implementation progress.

## 8. Current decision

```text
quality_status: qualification_ready
coordination_structure: interface_dependency
proposed label: partially_parallelizable
qualification status: pending independent annotation
official result eligibility: false
```

The task now satisfies:

- reproducible source materialization;
- checksum-pinned answer-free bootstrap;
- successful initial collection;
- specialist-local evaluators for both workers;
- cross-subproblem and full evaluators;
- completed-version evaluator sanity;
- explicit environment and scope limitations.

## 9. Remaining release tasks and pending evaluations

1. two independent human annotations and adjudication if needed;
2. recorded Linux/POSIX environment requirements and evaluator command;
3. single-agent baseline result;
4. specialist-local, serial-specialist, and async results;
5. equal model, scaffold, tools, and budgets across all four scenarios.

Portalocker can enter the annotated benchmark set after annotation. Model
performance and async degradation are reported later as evaluation results.

## 10. Generated assets

```text
configs/tasks/commit0_curated_tasks.v0.3.json
data/overlays/commit0/portalocker/0001-import-bootstrap.patch
manifests/pilot/v0.3/tasks/commit0_portalocker.json
manifests/pilot/v0.3/scenarios/commit0_portalocker.json
manifests/pilot/v0.3/quality/commit0_portalocker.json
manifests/annotations/commit0_v0.3/portalocker/
scripts/build_portalocker_v03_data.py
scripts/materialize_curated_commit0_task.py
```
