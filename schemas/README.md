# Public schemas

Machine-readable benchmark contracts will be published here. Python models in
`src/asyncodebench/contracts/` are the implementation, while exported schemas
in this directory are versioned public assets.

Regenerate the current schemas with:

```bash
PYTHONPATH=src python scripts/export_schemas.py --output schemas/v0.2
```

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

The v0.4 PR-hard pilot adds
`v0.4/pr_hard_candidate_registry.schema.json`. It describes qualification
candidates rather than official release tasks and is validated directly by the
contract suite. Promotion into a release still requires a frozen environment,
red-green evaluator evidence, and semantic human review.
