# Public schemas

This directory contains the machine-readable contracts used by the released
dataset and evaluation harness.

The v0.3 dataset schemas are:

- `task_record.schema.json`;
- `task_quality_record.schema.json`;
- `scenario_record.schema.json`;
- `annotation_form.schema.json`;
- `adjudication_form.schema.json`.

Regenerate them with either v0.3 data builder:

```bash
PYTHONPATH=src python scripts/build_cachetools_v03_data.py
PYTHONPATH=src python scripts/build_deprecated_v03_data.py
```

Generated schemas must match the implementation and are checked by contract
tests.

The v0.4 qualification path adds
`v0.4/pr_hard_candidate_registry.schema.json` and
`v0.4/pr_hard_qualification_record.schema.json`. The distribution layer adds
`v0.4/official_task_images.schema.json` for the 19 digest-pinned official
images. The candidate registry retains both
promoted and non-promoted construction records; the unified release index
contains only tasks that have a frozen environment, red-green evaluator
evidence, executable dependency evidence, and an approved human review.
