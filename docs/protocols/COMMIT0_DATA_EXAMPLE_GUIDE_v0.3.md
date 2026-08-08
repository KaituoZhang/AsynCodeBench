# Commit0 data-example guide — v0.3

Specification: `SPECIFICATION_v0.3.md`  
Status: qualification-ready example and Phase A operating guide  
Example task: `commit0:cachetools`

This document records how a Commit0 candidate is turned into an
AsynCodeBench task example for qualification. It is not a final annotation
decision, not a gold label, and not an official benchmark result. Its purpose
is to keep future task reviews consistent.

## 1. Consistency principles

### 1.1 Preserve the benchmark objective

The first AsynCodeBench paper builds a benchmark/protocol for asynchronous
LLM-based software-engineering agents. Commit0 tasks are used for cheap,
deterministic development and early validation. They must not become synthetic
role-playing examples whose difficulty is created by us.

For each candidate, the central question is:

```text
Does this task naturally expose asynchronous coordination structure under
private workspaces, hidden in-flight work, delayed messages, delayed tool
results, and integration?
```

The central question is not:

```text
Can a single model solve this task in one prompt?
```

### 1.2 Use only public candidate evidence

Primary qualification must use public, agent-independent evidence:

- the public task/specification text available at `commit0`;
- source files visible at `commit0`;
- tests visible at `commit0`;
- static dependency structure;
- measured test/build duration on the exported `commit0` tree;
- natural implementation, test, review, and integration overlap.

Do not use these as primary evidence:

- `reference` branch;
- `master`/`develop` branch after `commit0`;
- `commit0..reference` diffs;
- gold patches;
- solution files;
- model outputs from a later run.

Safe local inspection pattern:

```bash
git -C data/repos/commit0/<repo> \
  show commit0:<path>
```

Before inspection, materialize the pinned public repositories:

```bash
cd /path/to/AsynCodeBench
PYTHONPATH=src python scripts/materialize_commit0_repositories.py
```

The public URLs and expected `commit0` SHAs are recorded in
`configs/tasks/commit0_repositories.v0.3.json`. Local repositories under
`data/repos/` are generated inputs and are intentionally excluded from Git.

### 1.3 Separate task suitability from agent performance

A task can be suitable even if current models fail it. Conversely, a task can
be unsuitable even if one strong model solves it.

Qualification should separate:

```text
task structure
base-model execution competence
runtime/tool protocol failures
semantic integration failures
proactive coordination failures
```

Dry-run model results may help identify structure, but they do not replace
independent annotation and adjudication.

### 1.4 Do not manufacture coordination difficulty

Roles may be used to probe structure, but they must correspond to natural task
subproblems. A task should not be labeled parallelizable merely because we can
split files among agents.

Good evidence:

- multiple implicated implementation modules;
- tests covering separable functionality;
- dependencies across modules;
- an API or semantic contract that one subtask must preserve for another;
- plausible stale assumptions or integration mismatches.

Weak evidence:

- arbitrary file count;
- one core function with many tests;
- role assignments that only add overhead;
- failures caused only by bad prompt formatting or broken patch application.

### 1.5 Treat exploratory dry-runs as non-release evidence

LLM dry-runs are allowed as exploratory sanity checks only when clearly marked:

```text
non-release dry-run
not official benchmark result
not independent annotation
not a baseline comparison
```

Dry-runs can support a qualification rationale if they reveal stable task
structure, e.g. key-contract mismatch, stale assumptions, or integration
failure. They cannot be used to claim a coordination gap.

## 2. Standard review workflow for one Commit0 candidate

### Step 0 — Establish dataset quality evidence

Before human qualification, create a TaskQualityRecord that records:

```text
answer-free task-statement provenance
exact evaluator command
validated Python and dependency versions
successful test collection at commit0
initial pass/fail/error counts
specialist-local test groups
cross-subproblem integration tests
full evaluator tests
completed-version evaluator sanity check
known limitations
remaining annotation tasks, environment records, and pending baseline
evaluations
```

The completed-version check is evaluator validation only. It must not define
the decomposition, proposed label, prompt, or agent-visible context.

If a test file name conflicts with what its test bodies actually exercise,
assign it according to behavior rather than filename. Initial passing control
tests must not be counted as agent implementation progress.

#### Curated import-bootstrap exception

Raw Commit0 remains the default initial state. A candidate that cannot collect
because of a mechanical module/class-definition blocker may use a curated
initial state only when all of the following hold:

```text
the raw base SHA remains pinned and published
the transformation is a small versioned patch
the patch SHA-256 is recorded in a released config
the patch is derived from public source/docstring/test evidence
the patch supplies only import or class-definition prerequisites
the patch does not implement the task's substantive behavior
raw and curated evaluator snapshots are distinguished
the raw repository remains unchanged
two independent annotators review whether the overlay leaks an answer
```

The generated workspace must be reconstructable as:

```text
pinned raw Commit0 archive + ordered checksum-verified overlays
```

Do not use this exception to pre-solve a dependency layer merely so downstream
agents can run. If successful collection requires substantive implementation,
the candidate remains `needs_revision`.

### Step 1 — Read the candidate packet

Start from the answer-free packet:

```text
manifests/candidates/annotation_packets/commit0_v0.2/annotator_a.json
manifests/candidates/annotation_packets/commit0_v0.2/annotator_b.json
```

Inspect:

```text
task_id
issue_summary
publicly_implicated_modules
public_module_count
static_dependency_edges
dependency_separability
test_targets
test_target_independence
candidate_parallel_subproblems
cross_module_constraints
expected_overlap_surface
measured_test_and_build_duration
measurement_return_code
```

### Step 2 — Inspect only the `commit0` tree

Useful commands:

```bash
git -C data/repos/commit0/<repo> \
  ls-tree -r --name-only commit0

git -C data/repos/commit0/<repo> \
  grep -n -E 'TODO|NotImplemented|pass$|\\.\\.\\.' commit0 -- <source> <tests>
```

Then read relevant files with `git show commit0:<path>`.

### Step 3 — Identify natural subproblems

Do not start from agent roles. Start from the task:

```text
What implementation pieces are incomplete?
Which tests exercise each piece?
Which pieces depend on another piece's interface or semantics?
```

### Step 4 — Identify asynchronous coordination risks

Look for:

- stale assumptions about an API;
- hidden implementation choices that another agent depends on;
- delayed test feedback that could invalidate ongoing work;
- semantic integration failure without textual merge conflicts;
- duplicated or inconsistent wrapper/helper logic;
- reviewer/integrator decisions based on incomplete context.

### Step 5 — Assign a qualification label

Use one of:

```text
parallelizable
partially_parallelizable
effectively_serial
```

Recommended interpretation:

- `parallelizable`: several subproblems can proceed substantially in parallel
  and require nontrivial integration.
- `partially_parallelizable`: there is a real split, but one central design or
  API contract creates a bottleneck.
- `effectively_serial`: work is concentrated in one core change, and parallel
  roles mostly add overhead.

### Step 6 — Write a rationale

The rationale should explicitly cover:

```text
natural split
cross-module or semantic dependency
possible stale/conflict/wasted-work mechanism
reason for include/exclude
reason for chosen label
```

## 3. Worked example: `commit0:cachetools`

The generated TaskRecord uses an answer-free synthesis of the public
specification, source docstrings, and tests. The earlier truncated project
description remains only in the historical candidate inventory.

### 3.1 Candidate packet evidence

Key fields:

```text
task_id: commit0:cachetools

publicly_implicated_modules:
- src/cachetools/__init__.py
- src/cachetools/func.py
- src/cachetools/keys.py

static_dependency_edges:
- src/cachetools/func.py imports src/cachetools/__init__.py

test_targets:
- tests/test_cache.py
- tests/test_cached.py
- tests/test_cachedmethod.py
- tests/test_fifo.py
- tests/test_func.py
- tests/test_keys.py
- tests/test_lfu.py
- tests/test_lru.py
- tests/test_mru.py
- tests/test_rr.py
- tests/test_tlru.py
- tests/test_ttl.py

measured_test_and_build_duration: about 0.88 seconds
measurement_return_code: 1
```

Initial interpretation:

- the task is small enough for cheap pilot replay;
- it is not a single-file task;
- it has a cache class layer, decorator layer, and key-builder layer;
- tests cover multiple functional surfaces.

### 3.2 Safe source inspection

Repository:

```text
data/repos/commit0/cachetools
```

Relevant tree at `commit0`:

```text
src/cachetools/__init__.py
src/cachetools/func.py
src/cachetools/keys.py

tests/test_cache.py
tests/test_cached.py
tests/test_cachedmethod.py
tests/test_fifo.py
tests/test_func.py
tests/test_keys.py
tests/test_lfu.py
tests/test_lru.py
tests/test_mru.py
tests/test_rr.py
tests/test_tlru.py
tests/test_ttl.py
```

Incomplete implementation points at `commit0`:

```text
src/cachetools/func.py:
- fifo_cache(...)
- lfu_cache(...)
- lru_cache(...)
- mru_cache(...)
- rr_cache(...)
- ttl_cache(...)

src/cachetools/keys.py:
- hashkey(...)
- methodkey(...)
- typedkey(...)
- typedmethodkey(...)
```

`src/cachetools/__init__.py` contains the existing cache classes and the
`cached()` / `cachedmethod()` decorator utilities. For this candidate,
`__init__.py` is mostly dependency context rather than the main incomplete
surface.

### 3.3 Natural subproblem structure

The task has a natural split:

```text
Subproblem A — key construction
  file: src/cachetools/keys.py
  tests: tests/test_keys.py

Subproblem B — memoizing decorator factories
  file: src/cachetools/func.py
  tests: tests/test_func.py

Subproblem C — integration/review
  dependency: func.py must use keys.py and __init__.py APIs correctly
  tests: tests/test_func.py plus targeted cache tests
```

The split is not fully independent. `func.py` depends on:

- `keys.hashkey` versus `keys.typedkey` semantics;
- existing cache classes such as `FIFOCache`, `LRUCache`, `TTLCache`;
- `cached(..., info=True)` behavior;
- wrapper API expectations such as `cache_info`, `cache_clear`, and
  `cache_parameters`;
- special cases such as `maxsize=0`, `maxsize=None`, user-function shortcut,
  MRU deprecation, RR choice, and recursive equality requiring `RLock`.

The official tests expose an asymmetric decomposition:

```text
key specialist:
  direct local tests: tests/test_keys.py
  wrapper integration: tests/test_cached.py, tests/test_cachedmethod.py

decorator specialist:
  downstream cross-contract tests: tests/test_func.py
  prerequisite: completed key artifact
```

There is no meaningful official test slice that validates `func.py`
independently of key construction. This limitation is recorded rather than
hidden by inventing a synthetic local test.

### 3.4 Expected asynchronous coordination risks

This task can expose the following risks:

1. **Stale key semantics**  
   An agent implementing `func.py` may assume a specific typed/untyped key
   contract while another agent changes `keys.py`.

2. **API contract mismatch**  
   An agent may compose `cached()` and cache classes correctly at a high level
   but omit wrapper-level API requirements such as `cache_parameters()`.

3. **Delayed test feedback**  
   `tests/test_keys.py` can pass while `tests/test_func.py` still fails due to
   integration-level behavior. A worker can continue from a stale local
   assumption until the integration test result is delivered.

4. **Reviewer hallucination or over-correction**  
   A reviewer may incorrectly alter method-key semantics if it does not
   carefully follow tests stating that method keys ignore `self`.

5. **Semantic integration failure without textual merge conflict**  
   `keys.py` and `func.py` can be edited in separate files and merge cleanly,
   yet fail because their semantic contracts are inconsistent.

### 3.5 Recommended qualification judgment

Suggested demonstrative label:

```text
include: true
parallelizability_label: partially_parallelizable
```

Rationale:

```text
The task has a natural split between key construction in keys.py and decorator
construction in func.py. The key layer can be implemented and tested
separately, but func.py depends on the exact typed/untyped key semantics and on
existing cache/cached wrapper APIs. This creates realistic stale-assumption and
semantic integration risks under asynchronous private workspaces. The task is
therefore suitable for AsynCodeBench, but the central decorator API contract
makes it partially parallelizable rather than fully parallelizable.
```

This is a guide-level example, not the final adjudicated label.

## 4. Exploratory dry-run result for `cachetools`

### 4.1 Purpose

The dry-run was used to test whether the candidate exposes useful
AsynCodeBench-style structure. It is not an official benchmark result.

Harness:

```text
scripts/pilot_commit0_cachetools_agents.py
```

Protocol:

- agents received only `commit0` public files and tests;
- agents wrote complete replacement file contents;
- the harness generated diffs and ran pytest;
- outputs were saved under `outputs/pilot/cachetools_agents/`;
- runs were marked as non-release dry-runs.

### 4.2 Conditions run

```text
4B model:
- Qwen/Qwen3-4B-Thinking-2507, single
- Qwen/Qwen3-4B-Thinking-2507, two_agent
- Qwen/Qwen3-4B-Thinking-2507, three_agent

32B model:
- Qwen/Qwen3-32B, single
- Qwen/Qwen3-32B, two_agent
- Qwen/Qwen3-32B, three_agent
```

Modes:

- `single`: one integrator edits both `keys.py` and `func.py`;
- `two_agent`: one agent edits `keys.py`, one edits `func.py`, then the
  harness integrates both;
- `three_agent`: key and func agents produce drafts, then a reviewer produces
  final integrated files.

### 4.3 Summary results

| Model | Mode | Tool/file generation | Test result |
|---|---|---:|---:|
| Qwen3-4B-Thinking-2507 | single | success | 39 failed / 8 passed |
| Qwen3-4B-Thinking-2507 | two_agent | success | 38 failed / 9 passed |
| Qwen3-4B-Thinking-2507 | three_agent | success | 38 failed / 9 passed |
| Qwen3-32B | single | success | 36 failed / 11 passed |
| Qwen3-32B | two_agent | success | 42 failed / 5 passed |
| Qwen3-32B | three_agent | success | 36 failed / 11 passed |

The important outcome is not that the models failed. The important outcome is
that the harness reached real pytest execution and exposed stable semantic
failure modes.

### 4.4 Observed failure modes

1. **4B key semantics failure**  
   The 4B runs repeatedly failed `test_typedkey` and `test_typedmethodkey`.
   This reflects local execution competence limits in `keys.py`.

2. **32B local key improvement**  
   The 32B runs did not show key test failures, suggesting stronger local
   implementation ability.

3. **Universal decorator API failure**  
   All models and modes failed many `tests/test_func.py` cases, especially
   because generated wrappers lacked `cache_parameters()`.

4. **Naive parallel degradation**  
   The 32B two-agent condition performed worse than 32B single and 32B
   three-agent. The `func.py` agent mishandled cases such as `maxsize=None`
   while the `keys.py` agent's local success did not ensure integration
   success.

5. **Reviewer limitation**  
   Reviewer-mediated runs improved or preserved some structure but did not
   repair the central decorator API contract. In the 4B run, the reviewer also
   reasoned incorrectly about whether method keys should include `self`.

### 4.5 How to use this dry-run

Use it as supporting evidence that `cachetools` has:

- natural but incomplete parallel structure;
- cross-module semantic dependency;
- integration failure without textual merge conflict;
- a meaningful distinction between local coding competence and coordination;
- a plausible stale-assumption mechanism.

Do not use it to claim:

- an official coordination gap;
- a valid baseline comparison;
- model superiority;
- final task inclusion;
- final parallelizability label.

Those claims require frozen task/scenario records, controlled model and tool
conditions, repeated runs, and independent annotation/adjudication required by
v0.3. Replay and oracle analysis are later extensions.

## 5. Evaluator quality evidence

The isolated public `commit0` workspace collects all 215 tests:

```text
153 passed
62 failed
0 errors
return code 1
```

The initial passing set includes 127 cache-class controls. They must not be
counted as implementation progress.

An unchanged public completed tag was evaluated only as an evaluator sanity
check:

```text
215 passed
return code 0
```

That completed source is excluded from decomposition, annotation, prompts, and
agent-visible evidence. The validated environment is:

```text
Python 3.10.4
pytest 9.0.3
setuptools 82.0.1
```

The machine-readable evidence is:

```text
manifests/pilot/v0.3/quality/commit0_cachetools.json
```

Its status is `qualification_ready`, not `release_ready`.

## 6. Reusable annotation template

For each Commit0 candidate, produce a rationale in this shape:

```text
Task:
  <task_id>

Natural subproblems:
  - <subproblem A>
  - <subproblem B>
  - <integration/review/test component>

Public evidence:
  - implicated modules
  - tests
  - static dependency edges
  - measured runtime

Async coordination risks:
  - stale assumption:
  - delayed feedback:
  - integration mismatch:
  - duplicated/wasted work:

Confounds to report:
  - base model competence issue:
  - prompt/tool limitation:
  - arbitrary role risk:

Decision:
  include: true/false
  parallelizability_label: parallelizable | partially_parallelizable |
    effectively_serial

Rationale:
  <2-4 precise sentences>
```

## 7. Current action boundary

Under v0.3, the `cachetools` workflow is the canonical vertical slice for
generalizing the benchmark framework. Its numerical dry-run results remain
exploratory, but its data flow is now the implementation template:

```text
task record
-> scenario record
-> iterative inspect/edit/test/repair execution
-> file edits and generated patch
-> integration and tests
-> run record and failure labels
```

The next steps are:

1. implement a shared iterative coding-agent loop;
2. run the cachetools 4B/32B single-agent baseline condition;
3. implement serial specialists with the same scaffold;
4. implement truly concurrent private-workspace specialists;
5. implement structured message/artifact delivery;
6. complete independent annotation and freeze task/scenario records;
7. generalize the hard-coded cachetools runner;
8. continue SWE-bench official timing and qualification;
9. run the repeated two-model by four-condition pilot.

Multiple edit-test-repair rounds are now part of the minimum agent scaffold.
Replay, oracles, and richer policy matrices remain deferred.
