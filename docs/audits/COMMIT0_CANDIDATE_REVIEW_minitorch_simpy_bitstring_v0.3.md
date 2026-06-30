# Commit0 Candidate Review: minitorch, simpy, bitstring

Date: 2026-06-24

Scope: sequential candidate review after the existing v0.3 curated/reviewed set. This review inspects whether each repository can become an AsyncCodeBench task under the v0.3 benchmark direction: strong single-agent coding task, natural multi-agent decomposition, and measurable async coordination risk.

Reviewed repositories:

- `commit0:minitorch`
- `commit0:simpy`
- `commit0:bitstring`

Important branch/ref note:

- The local default branches for these repositories are mostly complete upstream code.
- The Commit0-style stripped task state is visible at `origin/commit0_combined`.
- Therefore candidate construction should treat `origin/commit0_combined` as the stripped input state and the complete upstream/default branch as validation/reference evidence only.

## Summary decision

| Repository | Decision | Priority | Reason |
| --- | --- | --- | --- |
| `simpy` | Promote to formal construction queue | High | Clean no-runtime-dependency package, strong event/resource interface dependencies, stable tests when evaluator is scoped to `tests/` and excludes metadata/docs controls. |
| `bitstring` | Keep in candidate backlog | Medium | Strong abstraction chain, but the full stripped task is very large and dependency-heavy; needs a curated subset before becoming a release task. |
| `minitorch` | Defer for v0.3 | Low/medium | Has many natural dependencies, but it is course-assignment shaped, broad, dependency-heavy, and includes test TODOs; likely noisy for the first AsyncCodeBench release. |

## `commit0:simpy`

### Evidence inspected

- Config entry: `configs/tasks/commit0_repositories_full.v0.3.json`
  - `commit0_sha`: `22cb5d8676f6ecccf0790d609103e975ed4cd120`
- Stripped task ref: `origin/commit0_combined`
  - commit: `2549671`
  - changed source files: `src/simpy/core.py`, `src/simpy/events.py`, `src/simpy/exceptions.py`, `src/simpy/resources/base.py`, `src/simpy/resources/container.py`, `src/simpy/resources/resource.py`, `src/simpy/resources/store.py`, `src/simpy/rt.py`, `src/simpy/util.py`
- Test collection with correct src layout:
  - command: `PYTHONNOUSERSITE=1 PYTHONPATH=src python -m pytest --collect-only -q`
  - result: 141/151 tests collected, 10 benchmark tests deselected by project config, one docs collection blocker due to `py._code`.
- Scoped test run:
  - command: `PYTHONNOUSERSITE=1 PYTHONPATH=src python -m pytest tests -q -m 'not benchmark'`
  - result: 139 passed, 1 failed (`tests/test_version.py::test_simpy_version`), 10 deselected.

### Quality assessment

`simpy` is a strong AsyncCodeBench candidate.

The repo has a natural interface dependency:

- `src/simpy/core.py` defines environment scheduling, event queues, stepping, and run semantics.
- `src/simpy/events.py` defines event lifecycle, process resume behavior, conditions, timeouts, and interrupts.
- `src/simpy/resources/base.py` defines the shared queue/request abstraction used by concrete resources.
- `src/simpy/resources/resource.py`, `container.py`, and `store.py` implement higher-level resource semantics on top of the base event/resource contract.
- `src/simpy/util.py` exposes convenience utilities that depend on correct process/event behavior.

This gives a clear async failure mode: one agent implementing resources may assume stale or incorrect event callback/trigger behavior from another agent implementing core/events. The merged code may type-check and partially pass local tests, but fail interaction tests around resource scheduling, condition resolution, interrupt handling, or queue invariants.

### Recommended task shape

Proposed task id:

- `commit0:simpy_event_resource`

Recommended decomposition:

- Subproblem A: event loop and event lifecycle
  - `src/simpy/core.py`
  - `src/simpy/events.py`
  - `src/simpy/exceptions.py`
- Subproblem B: shared resources and utilities
  - `src/simpy/resources/base.py`
  - `src/simpy/resources/resource.py`
  - `src/simpy/resources/container.py`
  - `src/simpy/resources/store.py`
  - `src/simpy/util.py`

Recommended evaluator:

- Use `PYTHONPATH=src`.
- Run `pytest tests -q -m 'not benchmark'`.
- Exclude or separately classify `tests/test_version.py::test_simpy_version` as package metadata/control unless the task explicitly asks for package metadata.
- Do not include docs doctests in the primary evaluator unless the `py` dependency is frozen and documented.

Admission status:

- Promote to formal construction queue.
- Needs TaskQualityRecord, task/scenario manifests, and two annotator records before release.

## `commit0:bitstring`

### Evidence inspected

- Config entry:
  - `commit0_sha`: `38fc95283d67397cfd38857e52aa26d2855b7163`
- Stripped task ref: `origin/commit0_combined`
  - commit: `0b71015`
  - changed files include `bitstring/bits.py`, `bitstring/bitstore.py`, `bitstring/bitstore_helpers.py`, `bitstring/bitarray_.py`, `bitstring/bitstream.py`, `bitstring/array_.py`, `bitstring/dtypes.py`, `bitstring/fp8.py`, `bitstring/mxfp.py`, `bitstring/utils.py`, and others.
- Current environment collection blocker:
  - missing `bitarray`
  - declared dependency: `bitarray >= 2.9.0, < 3.0.0`
  - test dependencies include `pytest`, `hypothesis`, `gfloat`, `pytest-benchmark`

### Quality assessment

`bitstring` has a strong abstraction structure but is too broad as a full v0.3 release task.

The promising dependency chain is:

- `bitstring/bitstore.py` and `bitstore_helpers.py`: low-level bit storage, indexing, slicing, conversion.
- `bitstring/bits.py`: immutable high-level public API built over `BitStore`.
- `bitstring/bitarray_.py` and `bitstream.py`: mutable/streaming APIs relying on the same storage and slicing semantics.
- `bitstring/dtypes.py`, `fp8.py`, `mxfp.py`, `array_.py`: interpretation and typed-array layer on top of the core bit representation.

The async risk is real: stale assumptions about LSB0/MSB0 indexing, slice conversion, mutability, or dtype conversion can silently break upper layers. However, the stripped state touches too many files and too many methods. As a full task it may measure repository size and dependency management more than async coordination.

### Recommended task shape

Do not admit the full stripped task directly.

Potential curated subset:

- `commit0:bitstring_bitstore_bits`
- Subproblem A: `bitstore.py` + `bitstore_helpers.py` low-level indexing/slicing/conversion.
- Subproblem B: `bits.py` creation, slicing, conversion, representation, and search behavior.
- Optional Subproblem C only if needed: `bitstream.py` stream position/read behavior.

Recommended evaluator:

- Freeze external dependency `bitarray`.
- Start with targeted tests:
  - `tests/test_bitstore.py`
  - selected creation/slicing/search sections from `tests/test_bits.py`
  - optionally selected `tests/test_bitstream.py`
- Avoid full `array_`, `dtypes`, `fp8`, and `mxfp` scope for v0.3 unless we intentionally want a large task tier.

Admission status:

- Keep in candidate backlog.
- Can become a benchmark task after curated subset definition and environment freeze.

## `commit0:minitorch`

### Evidence inspected

- Config entry:
  - `commit0_sha`: `7d35d597ad226e73289e6920fbc1e83ea6148c8b`
- Stripped task ref: `origin/commit0_combined`
  - commit: `1fc342c`
  - changed files include most of `minitorch/*.py`.
- Environment collection blockers:
  - missing `hypothesis`
  - missing `numba`
- Declared dependency files include heavy educational/deep-learning dependencies:
  - `hypothesis`
  - `numba`
  - `numpy`
  - `torch`
  - `datasets`
  - `streamlit`
  - others.
- Tests contain task TODOs requiring test implementation:
  - `tests/test_operators.py` includes `raise NotImplementedError('Need to implement for Task 0.2')`
  - `tests/test_nn.py` includes `raise NotImplementedError('Need to implement for Task 4.4')`

### Quality assessment

`minitorch` is structurally rich but not a good first-release AsyncCodeBench task.

It has many natural dependency layers:

- mathematical operators
- module/parameter tree
- scalar autodiff
- tensor data
- tensor functions
- fast/cuda ops
- neural-network helpers

However, this is closer to a course assignment than a normal library repair/implementation benchmark. The repo includes staged tasks and TODOs in tests, and the full stripped state is very broad. If used directly, it will likely test whether an agent can solve a long educational assignment rather than whether async multi-agent coding introduces stale-work conflicts.

### Possible future use

If we later add a separate educational/algorithmic tier, a small subset could be useful:

- `minitorch_operators_module`
  - `minitorch/operators.py`
  - `minitorch/module.py`
  - selected task0 tests

But this should not enter the main v0.3 release queue.

Admission status:

- Defer for v0.3.
- Do not count toward the target 20 main AsyncCodeBench tasks unless a very small curated subset is explicitly designed and reviewed.

## Updated candidate queue implication

After this three-repo review:

- Promote next: `simpy`
- Backlog: `bitstring`
- Defer: `minitorch`

Recommended next formal construction target after `requests`:

1. `commit0:requests`
2. `commit0:simpy`
3. `commit0:dulwich`
4. `commit0:filesystem_spec`

