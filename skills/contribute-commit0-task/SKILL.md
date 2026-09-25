---
name: contribute-commit0-task
description: Prepare or review a new Commit0-derived AsynCodeBench task contribution from public source and tests, including manifests, dependency probes, annotation templates, and validation evidence. Use for adding Commit0 task candidates; do not use for running the frozen 19-task benchmark or for PR-hard/TVM task construction.
---

# Contribute a Commit0 Task

Create a qualification-ready candidate without changing the frozen official
release. Treat promotion into the release as a separate, explicitly authorized
review step.

## Evidence boundary

- Use only the pinned public initial source, public tests, task statement,
  candidate screening evidence, and documented environment requirements.
- Never inspect a gold patch, reference implementation diff, hidden test, or
  prior model solution to choose decomposition, writable scopes, probes, or
  metrics.
- Do not modify public tests.
- A bootstrap overlay may fix only collection, import, syntax, or mechanical
  setup blockers. It must not implement target behavior or satisfy a semantic
  dependency probe.
- Every dependency must be natural, cross-component, and observable through
  public tests.

## Intake

1. Check the task, scenario, metric, annotation, and curated-source records.
   Stop if an equivalent candidate already exists unless the request is to
   repair or review it.
2. Record the repository URL, pinned public base ref and SHA, candidate
   evidence, evaluator command, and complete/sanity ref used only to verify
   evaluator feasibility.
3. Run the evaluator on the public initial state. Record collected, passed,
   failed, skipped, error, return-code, environment, and duration evidence.

For detailed construction rules, use the repository's
`docs/protocols/COMMIT0_DATA_AND_METRIC_LABEL_GUIDE_v0.3.md` and
`docs/protocols/ANNOTATOR_GUIDANCE_v0.3.md`.

## Dependency-aware construction

Identify meaningful producer and consumer subproblems before assigning files.
For each dependency, document its semantic contract, stale-assumption failure
mode, evidence paths, and exact upstream, downstream, and integrated public
test selectors. File separation alone is not a dependency.

Generate the four source scenarios used by the native harness:

- `iterative_single` for `single`;
- `serial_specialists` for `serial_specialists`;
- `async_private` for `async_private`;
- `async_message` for `caid_manager` (Async-RO-Manager).

Do not invent a fifth task scenario. The official `async_manager` protocol
reuses the `caid_manager` scenario contract and adds its own online manager
execution policy through `configs/evaluation/protocol_registry.v2.json`.

## Contribution artifacts

Create or update only the candidate's scoped artifacts:

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
tests/contracts/test_<repo>_dataset_v03.py
tests/contracts/test_<repo>_async_metrics_v03.py
configs/tasks/commit0_curated_tasks.v0.3.json
```

Use `schema_version: "0.3-async-metrics"` for the metric record. Keep source
filenames and `source_task_id` values as Commit0 provenance, but use
`asyncodebench:<repo>` as the public benchmark identity.

The required human decision is `annotator_a.json`. Keep all decision fields
unset when preparing the candidate. `annotator_b.json` and the adjudication
template are optional provenance and must not be presented as completed human
reviews.

## Release boundary

A generated task may be `qualification_ready`; it is not automatically an
official task. Do not edit `manifests/release/v0.4/official_tasks.json`, the
release indexes, the official image registry, or validated baseline registry
unless the user explicitly requests release promotion after validation and
human approval.

Before reporting completion, read and run
[references/validation-gates.md](references/validation-gates.md). Report the
evidence used, files changed, evaluator snapshots, dependency/probe choices,
validation results, and remaining human or release gates.
