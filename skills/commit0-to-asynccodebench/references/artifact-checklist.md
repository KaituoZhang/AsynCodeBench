# Artifact Checklist

For each transformed Commit0 task, produce:

```text
src/asynccodebench/dataset/<repo>_v03.py
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
configs/tasks/commit0_curated_tasks.v0.3.json entry
```

Task record essentials:

- stripped upstream version;
- repository;
- source materialization;
- problem statement;
- evaluator command;
- test targets;
- publicly implicated modules;
- natural subproblems;
- dependency annotations;
- `pending_independent_annotation`;
- quality evidence file.

Quality record essentials:

- `qualification_ready`;
- coordination structure tags;
- public statement sources;
- environment requirements;
- local specialist test groups;
- cross-subproblem test groups;
- full evaluator group;
- initial and complete evaluation snapshots;
- known limitations;
- remaining gates.

Metrics record essentials:

- `0.3-async-metrics`;
- metric definitions;
- dependency points;
- aggregate metrics;
- checkpoint policy;
- annotation notes.
