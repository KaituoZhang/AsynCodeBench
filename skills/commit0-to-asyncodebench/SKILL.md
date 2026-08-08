---
name: commit0-to-asyncodebench
description: Transform a public Commit0-style coding task into an AsynCodeBench v0.3 dependency-aware asynchronous multi-agent benchmark candidate with manifests, async metrics, validation gates, and human annotation forms. Use when asked to process the next Commit0 task, generate AsynCodeBench task artifacts, label async dependency points, or validate a transformed task.
---

# Commit0-to-AsynCodeBench

Use this skill to convert a public Commit0-style task into a
qualification-ready AsynCodeBench v0.3 candidate. The output is a candidate for
human review, not release-ready data.

## Hard Rules

- Use only public initial source, public tests, candidate evidence, and protocol
  documents.
- Do not inspect gold patches or reference diffs to design decomposition,
  labels, probes, prompts, or metrics.
- Do not modify public tests.
- Bootstrap overlays may only fix collection/import/mechanical blockers. They
  must not implement benchmark behavior or satisfy semantic tests.
- Dependency points must be public-test-observable.
- A generated task is at most `qualification_ready` until independent human
  annotation and adjudication are complete.

## Workflow

### 1. Skip Check

Before transforming a task:

1. Inspect existing task manifests, metrics manifests, annotation directories,
   and `configs/tasks/commit0_curated_tasks.v0.3.json`.
2. Skip any task that already has both a task manifest and async metrics file.
3. Confirm the selected task is the next unprocessed task in the requested
   candidate list.

### 2. Public Evidence Intake

Inspect:

- candidate screening record;
- public initial ref, usually `origin/commit0_combined` or `commit0`;
- local complete/sanity ref;
- public source modules;
- public tests and test dependencies.

Record base SHA and complete sanity SHA.

### 3. Evaluator Construction

Run a scoped public-test evaluator on the stripped initial ref.

If collection/import fails, add the smallest possible bootstrap overlay:

- import symbol stubs;
- setup hooks;
- syntax fixes;
- class construction placeholders.

Every overlay needs:

- path;
- SHA-256 checksum;
- rationale;
- `git apply --check` validation against the public initial ref.

Then record:

- initial snapshot counts;
- complete sanity snapshot counts;
- excluded tests and why.

### 4. Dependency-Aware Repartitioning

Identify natural subproblems from public modules and tests. Avoid arbitrary file
partitioning.

For each dependency annotation, specify:

- producer subproblem;
- consumer subproblem;
- dependency type;
- description;
- evidence paths.

Good dependencies are semantic contracts, such as:

- producer API semantics consumed by downstream behavior;
- shared state shape consumed across modules;
- registry or schema lookup consumed by nested behavior;
- utility parsing or conversion contract consumed by core logic.

Weak dependencies merely say two agents edit different files.

### 5. Scenario Recomposition

Generate four scenarios:

- `iterative_single`;
- `serial_specialists`;
- `async_private`;
- `async_message`.

For each scenario, define:

- agent assignments;
- writable paths;
- primary test targets;
- information profile;
- communication policy;
- integration policy;
- dependency annotations.

### 6. Artifact Generation

Create or update:

```text
src/asyncodebench/dataset/<repo>_v03.py
scripts/build_<repo>_v03_data.py
manifests/pilot/v0.3/tasks/commit0_<repo>.json
manifests/pilot/v0.3/scenarios/commit0_<repo>.json
manifests/pilot/v0.3/quality/commit0_<repo>.json
manifests/pilot/v0.3/metrics/commit0_<repo>_async_metrics.json
manifests/annotations/commit0_v0.3/<repo>/annotator_a.json
manifests/annotations/commit0_v0.3/<repo>/annotator_b.json
manifests/annotations/commit0_v0.3/<repo>/adjudication.template.json
tests/contracts/test_<repo>_dataset_v03.py
tests/contracts/test_<repo>_async_metrics_v03.py
configs/tasks/commit0_curated_tasks.v0.3.json
```

### 7. Async Metrics

Each metrics manifest must use `schema_version == "0.3-async-metrics"` and
define one or more dependency points with:

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

Enable `ADPR`, `DRS`, `CAIL`, and `SAD` unless a task-specific reason is
documented.

### 8. Validation Gates

Run and report:

- JSON parse for all generated JSON files;
- contract tests for the task and async metrics;
- global missing async metrics contract;
- overlay checksum and apply checks;
- probe selector resolution to public tests;
- Python compile for new Python files;
- lightweight build script if it does not require unavailable project
  dependencies.

If a validation gate cannot run, document why and what evidence remains.

## Human Annotation Boundary

Do not mark generated records as release-ready. Leave annotation forms with
`include`, `parallelizability_label`, and rationale unset. Annotators decide
whether the dependency structure is real and whether the task should be included.

## Reporting

Final summaries should state:

- which task was transformed;
- current total task and async metrics manifest counts;
- evaluator snapshot counts;
- files added or updated;
- validation commands and results;
- known limitations and remaining human gates.
