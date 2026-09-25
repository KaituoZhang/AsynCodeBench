# Validation gates

Run these checks from the repository root. Replace `<repo>` with the normalized
task name used in filenames.

## Candidate build and JSON validation

```bash
PYTHONNOUSERSITE=1 PYTHONPATH=src \
  python scripts/build_<repo>_v03_data.py

python - <<'PY'
import json
from pathlib import Path

repo = "<repo>"
paths = [
    Path(f"manifests/pilot/v0.3/tasks/commit0_{repo}.json"),
    Path(f"manifests/pilot/v0.3/scenarios/commit0_{repo}.json"),
    Path(f"manifests/pilot/v0.3/quality/commit0_{repo}.json"),
    Path(f"manifests/pilot/v0.3/metrics/commit0_{repo}_async_metrics.json"),
    *Path(f"manifests/annotations/asyncodebench_v0.3/{repo}").glob("*.json"),
]
for path in paths:
    json.loads(path.read_text(encoding="utf-8"))
print(f"validated {len(paths)} JSON files")
PY
```

## Focused contracts

Materialize the pinned public repositories before running source-aware
contracts. Use `--source-root` when an approved local mirror is available.

```bash
PYTHONPATH=src python scripts/materialize_contract_test_repositories.py
```

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src python -m pytest -q \
  tests/contracts/test_missing_async_metrics_v03.py \
  tests/contracts/test_annotation_namespace_v03.py \
  tests/contracts/test_<repo>_dataset_v03.py \
  tests/contracts/test_<repo>_async_metrics_v03.py
```

The contracts must verify source provenance, evaluator snapshots, scenario
modes, natural specialist ownership, annotation state, metric schema version,
dependency count, and exact public probe resolution.

## Overlay integrity

If the curated task uses overlays, verify every checksum recorded in
`configs/tasks/commit0_curated_tasks.v0.3.json`, then apply the patches in their
recorded order to a fresh archive of the pinned base SHA. `git apply --check`
and the evaluator must both succeed. Review the resulting diff to confirm it
contains no target implementation or semantic shortcut.

## Python and repository checks

```bash
python -m py_compile \
  src/asyncodebench/dataset/<repo>_v03.py \
  scripts/build_<repo>_v03_data.py \
  tests/contracts/test_<repo>_dataset_v03.py \
  tests/contracts/test_<repo>_async_metrics_v03.py

python scripts/build_release_index.py --check
python scripts/build_v04_release_index.py --check
python scripts/check_repository_hygiene.py
```

Run the broader contract suite when shared configuration, schemas, release
builders, or common dataset code changes. A candidate must not change the
frozen 19-task release merely by being constructed.

## Human and promotion gates

Before promotion, require the current human-review policy recorded in
`manifests/release/v0.4/official_tasks.json`. Validate that the required human
annotation approves inclusion and that the automated audit is distinct from
the human decision. Promotion additionally requires a frozen official task
image, release-index consistency, executable dependency probes, and the
release's baseline/admission requirements.
