# AsynCodeBench Human Review

This is the canonical checklist for the required human review of the 16-task
release. The policy is one human approval per task plus a separate automated
audit. The human completes `annotator_a.json`; the automated audit does not
count as a second human.

## Files To Review

For each repository, read these public, answer-free artifacts:

```text
manifests/pilot/v0.3/tasks/commit0_<task>.json
manifests/pilot/v0.3/quality/commit0_<task>.json
manifests/pilot/v0.3/scenarios/commit0_<task>.json
manifests/pilot/v0.3/metrics/commit0_<task>_async_metrics.json
configs/tasks/commit0_curated_tasks.v0.3.json
```

The `commit0_` filenames and `source_task_id` fields preserve source
provenance. The public benchmark identity remains `asyncodebench:<task>`.
Do not inspect a reference solution, hidden patch, or model-generated answer.

## Fields To Fill

Edit only these fields in each required `annotator_a.json`:

```json
{
  "annotator_id": "your-stable-public-or-pseudonymous-id",
  "include": true,
  "parallelizability_label": "partially_parallelizable",
  "rationale": "A concrete explanation of the natural subproblems, their dependency, evaluator validity, and asynchronous failure risk.",
  "exclusion_reason": null
}
```

Allowed labels are `parallelizable`, `partially_parallelizable`, and
`effectively_serial`. If `include` is `false`, provide a non-empty
`exclusion_reason`. If `include` is `true`, keep `exclusion_reason` null.

## Acceptance Checklist

Approve a task only after confirming all of the following:

- the public task statement describes real repository-level implementation;
- the pinned curated source and bootstrap overlays are answer-free;
- the manifest evaluator is executable and measures the requested behavior;
- the task has at least two natural, non-artificial subproblems;
- the writable ownership labels cover the intended implementation surfaces;
- at least one producer/consumer dependency crosses an agent boundary;
- Dependency Checker selectors execute and observe that contract;
- asynchronous execution can create stale assumptions, delayed adaptation, or
  integration failure;
- the task is not primarily testing package installation or environment repair.

The rationale must name the relevant subproblems and dependency. A statement
such as "the task is difficult and supports multiple agents" is insufficient.

## Review Status

The required `annotator_a.json` form is complete and approved for all 16
official tasks. The generated release index records both
`human_review_complete_task_count: 16` and
`human_review_passed_task_count: 16`.

`annotator_b.json` and `adjudication.template.json` remain optional provenance
artifacts. They do not block the one-human release gate.

## Validate The Review

From the repository root:

```bash
python scripts/build_release_index.py
python scripts/build_release_index.py --check

cd reproductions/async-swe-agents
uv run asyncodebench release-status --json
```

The release index distinguishes `human_review_complete` from
`human_review_passed`. A completed rejection remains visible but does not pass
the stable-release gate. Stable release additionally requires a registered,
checksum-validated public baseline bundle.
