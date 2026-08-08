# Commit0 TinyDB curated data example — v0.3

Specification: `SPECIFICATION_v0.3.md`  
Status: curated task; `qualification_ready`  
Task: `commit0:tinydb`

This document records how raw Commit0 TinyDB is converted into a reproducible,
answer-free curated initial state that satisfies the AsynCodeBench data
quality gates. It applies the same TaskQualityRecord standard used for
cachetools and Deprecated.

## 1. Public task identity

```text
repository: data/repos/commit0/tinydb
origin: https://github.com/commit-0/tinydb.git
commit0 SHA: ed761a72c8c1e1cb24ca4dbcc089f35c5264d357
curated overlay:
  data/overlays/commit0/tinydb/0001-import-bootstrap.patch
overlay SHA-256:
  fa0d43a64a64d6bcd085661328bfca566f678f384ac4bf6c8bf2b79b0c01a464
completed evaluator-sanity tag: v4.8.0
```

The task structure uses only public source, docstrings, tests, and static
dependencies at `commit0`. The completed tag is used only to validate the
unchanged evaluator.

## 2. Corrected implementation surface

The automatic inventory lists `tinydb/__init__.py`, but manual review shows
that its incomplete marker is a false positive. The meaningful unfinished
surface is:

```text
query_and_utility_layer:
  tinydb/utils.py
  tinydb/queries.py
  tinydb/operations.py

persistence_and_table_layer:
  tinydb/storages.py
  tinydb/table.py

database_and_middleware_layer:
  tinydb/database.py
  tinydb/middlewares.py
```

## 3. Curated initial-state rule

Raw Commit0 has two class-definition blockers:

```text
with_typehint(...) returns None because its body is pass
FrozenDict aliases an undefined _immutable name
```

The versioned overlay makes exactly two changes:

```text
with_typehint(...) returns object at runtime
FrozenDict defines _immutable(*args, **kwargs) as pass
```

The second edit deliberately does not implement correct immutability. The
public tests must still force an agent to implement TypeError behavior. The
overlay supplies no query, LRU cache, operation, storage, table, database, or
middleware implementation.

The overlay is checksum-pinned in:

```text
configs/tasks/commit0_curated_tasks.v0.3.json
```

The released initial state is reconstructed with:

```bash
PYTHONPATH=src python scripts/materialize_curated_commit0_task.py \
  commit0:tinydb
```

This writes the generated workspace to:

```text
data/processed/commit0_curated/v0.3/tinydb
```

The raw repository under `data/repos/commit0/tinydb` remains unchanged.

## 4. Why the task fits the intended structure

TinyDB has both v0.3 coordination structures.

Interface Dependency:

```text
utils/query contracts
-> Table search and query cache
-> TinyDB default-table and lifecycle behavior
```

Shared State / Shared Abstraction:

```text
Storage
<-> Table
<-> TinyDB
<-> CachingMiddleware
```

These modules must agree on one complete-database mapping, table names,
document IDs, storage read/write lifecycle, and cache invalidation behavior.
Agents can produce individually plausible code that merges cleanly while
disagreeing semantically about those contracts.

The split is therefore not arbitrary file partitioning. It is a natural
producer/consumer chain around shared persistent state.

## 5. Natural specialist split

The final scenario uses two specialists:

```text
query_contract_layer:
  tinydb/utils.py
  tinydb/queries.py
  tinydb/operations.py

database_state_stack:
  tinydb/storages.py
  tinydb/table.py
  tinydb/database.py
  tinydb/middlewares.py
```

This split is preferred over three agents because database and middleware
cannot make meaningful independent progress without storage and table
foundations. Keeping those modules with one state-stack specialist avoids
manufacturing a worker whose main behavior is dependency blocking.

The query specialist produces query hashing, matching, cache, and update
contracts consumed by the state-stack specialist. The state-stack specialist
owns the shared persistent representation and lifecycle.

## 6. Curated initial evaluator evidence

All unchanged public tests collect:

```text
collected: 201
passed: 5
failed: 71
errors: 125
return code: 1
duration: 53.19 seconds
```

The failures and errors are caused by unfinished implementation surfaces, not
missing dependencies or evaluator setup.

Explicit evaluator groups:

```text
query_contract_local:
  tests/test_utils.py tests/test_queries.py
  2 passed, 39 failed

database_state_local:
  tests/test_storages.py tests/test_middlewares.py
  2 passed, 14 failed, 5 errors

query_state_cross_contract:
  tests/test_operations.py tests/test_tables.py tests/test_tinydb.py
  1 passed, 18 failed, 120 errors
```

Initial passing tests are controls or already-complete behavior and must not be
counted as agent progress.

## 7. Evaluator sanity

The unchanged evaluator passes on the completed public tag:

```text
201 passed
0 failed
0 errors
duration: 0.66 seconds
```

Environment:

```text
Python 3.10.4
pytest 9.0.3
PyYAML 6.0.3
setuptools 82.0.1
```

This establishes that the public tests and environment are viable. It does not
repair initial collection and is not used to define prompts, decomposition, or
agent-visible evidence.

## 8. Current decision

```text
quality_status: qualification_ready
coordination_structure:
  - interface_dependency
  - shared_abstraction
proposed structural label: partially_parallelizable
qualification status: pending independent annotation
official result eligibility: false until annotation and evaluation are complete
```

TinyDB now satisfies the dataset-construction gates for successful collection,
explicit local/cross/full evaluators, answer-free task provenance, and
completed-version evaluator sanity.

`qualification_ready` does not mean automatically included. Two independent
humans must still approve the task and its parallelizability label.
Single-agent, serial-specialist, and async outcomes are evaluation results to
be reported after inclusion, not prerequisites for inclusion.

## 9. Remaining release tasks and pending evaluations

1. two independent human annotations and adjudication if needed;
2. recorded environment requirements and evaluator command;
3. single-agent baseline result;
4. specialist-local, serial-specialist, and async results;
5. scenario execution using equal model, scaffold, tools, and budgets.

The many initial cross-group errors are expected but cannot themselves be
reported as asynchronous degradation.

## 10. Generated assets

```text
configs/tasks/commit0_curated_tasks.v0.3.json
data/overlays/commit0/tinydb/0001-import-bootstrap.patch
manifests/pilot/v0.3/tasks/commit0_tinydb.json
manifests/pilot/v0.3/scenarios/commit0_tinydb.json
manifests/pilot/v0.3/quality/commit0_tinydb.json
manifests/annotations/commit0_v0.3/tinydb/
scripts/build_tinydb_v03_data.py
scripts/materialize_curated_commit0_task.py
```
