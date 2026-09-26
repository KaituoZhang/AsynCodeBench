# Task manifests

- `candidates/`: complete candidate inventories, including exclusions;
- `pilot/`: frozen pilot selections;
- `release/`: final benchmark splits after the Go decision.

Every frozen manifest records its specification and schema versions.

The first unlabelled public-evidence inventory is:

`candidates/commit0_public_candidates_v0.2.json`

It contains six Commit0 repositories and no annotator decisions or primary
labels.

Its filename and embedded protocol version remain unchanged because released
v0.3 records cite it as immutable provenance. This retained inventory documents
the Commit0 evidence used by the official task-construction pipeline.
Historical cross-source
SWE-bench screening assets are not part of the community runtime release.

AsynCodeBench v0.3 Commit0 draft assets:

- `pilot/v0.3/tasks/commit0_cachetools.json`: portable task record; pending
  independent human annotation;
- `pilot/v0.3/scenarios/commit0_cachetools.json`: four draft scenarios
  (`iterative_single`, `serial_specialists`, `async_private`,
  `async_message`);
- `pilot/v0.3/quality/commit0_cachetools.json`: statement provenance, exact
  evaluator environment, initial and completed sanity snapshots, asymmetric
  test groups, limitations, and remaining release gates;
- `annotations/asyncodebench_v0.3/cachetools/annotator_a.json` and
  `annotator_b.json`: blank independent human decision forms;
- `annotations/asyncodebench_v0.3/cachetools/adjudication.template.json`: blank
  independent adjudication form, used only when annotators disagree.
- `pilot/v0.3/tasks/commit0_deprecated.json`: second portable task record,
  pending independent human annotation;
- `pilot/v0.3/scenarios/commit0_deprecated.json`: four draft scenarios over
  the natural Classic and Sphinx subproblems;
- `pilot/v0.3/quality/commit0_deprecated.json`: task-statement provenance,
  frozen dependency versions, test-group boundaries, evaluator snapshots,
  limitations, and remaining release gates;
- `annotations/asyncodebench_v0.3/deprecated/`: two blank independent annotation
  forms and one adjudication template.
- `pilot/v0.3/{tasks,scenarios,quality}/commit0_portalocker.json`: audited
  Interface Dependency candidate whose quality status is `needs_revision`;
- `annotations/asyncodebench_v0.3/portalocker/`: independent inclusion/exclusion
  forms and adjudication template for the unresolved candidate.

Rebuild these assets and the public v0.3 schemas with:

```bash
PYTHONPATH=src python scripts/build_cachetools_v03_data.py
PYTHONPATH=src python scripts/build_deprecated_v03_data.py
PYTHONPATH=src python scripts/build_portalocker_v03_data.py
```

After both human forms are complete, finalize the task with
`scripts/finalize_v03_task_annotation.py`. A disagreement requires a completed
independent adjudication form.
