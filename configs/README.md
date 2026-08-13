# Configurations

Versioned experimental conditions are grouped as:

- `profiles/`: information-sharing profiles;
- `latency/`: empirical replay and stress schedules;
- `policies/`: baseline and oracle semantic cards;
- `tasks/`: task-source and qualification settings;
- `pilot/`: locked smoke and Go/No-Go matrices.
- `evaluation/`: public execution profiles used to decide whether completed
  runs are comparable in the official aggregate.

Configuration files select semantics defined in code and schemas; they must
not silently introduce new semantics.

`evaluation/official_execution_profile.v2.json` is the authoritative public
comparison profile. It fixes the 100-response capability budgets and
instrumentation timeouts used by the official aggregate. The v1 file is
retained as the historical 30-response profile. Scenario-level historical
budget fields remain construction provenance; a run's actual eligibility is
decided from its recorded execution-profile match and post-run health gates.

`tasks/commit0_repositories.v0.3.json` is the portable source inventory for
Commit0. It records public repository URLs and pinned `commit0` SHAs; local
clones are generated under `data/repos/commit0/`.

`tasks/commit0_curated_tasks.v0.3.json` records benchmark-owned,
checksum-verified overlays applied to pinned public Commit0 archives. Generated
curated workspaces are written under `data/processed/commit0_curated/v0.3/`;
the raw repositories remain unchanged.
