# Validation Gates

Required local checks:

```bash
python - <<'PY'
import json
from pathlib import Path
for path in Path("manifests").glob("**/*.json"):
    json.loads(path.read_text())
PY
```

Run task-specific contracts:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q \
  tests/contracts/test_missing_async_metrics_v03.py \
  tests/contracts/test_<repo>_dataset_v03.py \
  tests/contracts/test_<repo>_async_metrics_v03.py
```

Check overlays:

```bash
tmpdir=$(mktemp -d /tmp/acb_<repo>_check.XXXXXX)
git -C data/repos/commit0/<repo> archive <base_ref> | tar -x -C "$tmpdir"
for patch in data/overlays/commit0/<repo>/*.patch; do
  git -C "$tmpdir" apply --check "$PWD/$patch"
  git -C "$tmpdir" apply "$PWD/$patch"
done
```

Check new Python files:

```bash
python -m py_compile \
  src/asynccodebench/dataset/<repo>_v03.py \
  scripts/build_<repo>_v03_data.py \
  tests/contracts/test_<repo>_dataset_v03.py \
  tests/contracts/test_<repo>_async_metrics_v03.py
```

Task-specific contract tests should verify:

- task id and stripped SHA;
- source materialization mentions public initial ref;
- quality status is `qualification_ready`;
- initial and complete snapshot counts;
- curated config base ref, base SHA, and overlay checksums;
- scenario modes and natural specialists;
- annotation forms remain unset and instruct independent review;
- metrics schema version;
- dependency point count;
- primary dependency id;
- every probe selector resolves to a public test node;
- primary dependency has upstream and downstream probes.
