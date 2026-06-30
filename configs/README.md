# Configurations

Versioned experimental conditions are grouped as:

- `profiles/`: information-sharing profiles;
- `latency/`: empirical replay and stress schedules;
- `policies/`: baseline and oracle semantic cards;
- `tasks/`: task-source and qualification settings;
- `pilot/`: locked smoke and Go/No-Go matrices.

Configuration files select semantics defined in code and schemas; they must
not silently introduce new semantics.

`tasks/commit0_repositories.v0.3.json` is the portable source inventory for
Commit0. It records public repository URLs and pinned `commit0` SHAs; local
clones are generated under `data/repos/commit0/`.

`tasks/commit0_curated_tasks.v0.3.json` records benchmark-owned,
checksum-verified overlays applied to pinned public Commit0 archives. Generated
curated workspaces are written under `data/processed/commit0_curated/v0.3/`;
the raw repositories remain unchanged.
