# Local benchmark data

This directory contains generated or externally materialized task inputs. The
large contents are intentionally excluded from Git.

Commit0 repositories are materialized independently from the public inventory:

```bash
PYTHONPATH=src python scripts/materialize_commit0_repositories.py
```

The result is:

```text
data/repos/commit0/<repo>
```

The versioned source of truth is
`configs/tasks/commit0_repositories.v0.3.json`, which records each public
origin and expected `commit0` SHA. Runtime code must not point to another local
project as a repository source.
Raw external repositories are materialized under `data/repos/`. Curated
Commit0 benchmark states are defined as pinned raw refs plus versioned patches
under `data/overlays/` and reconstructed under `data/processed/`.

Do not edit generated repositories in place. Change the reviewed overlay and
its checksum, then rerun the curated materializer.
