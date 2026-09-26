# AsynCodeBench repository layout

This layout separates frozen benchmark material from task-construction tools,
the executable evaluation harness, and generated outputs.

## Core library

`src/asyncodebench/` contains the importable task-construction and analysis
library:

- `dataset/`: strict v0.3 task, scenario, annotation, and metric records plus
  the builders used to reproduce the frozen Commit0 manifests;
- `qualification/`: public-source candidate screening, pinned repository
  materialization, curated overlays, and contribution-review support;
- `metrics/`: dependency-resolution analysis for compatible event-log bundles.

The executable five-protocol harness is
`reproductions/async-swe-agents/asyncodebench_harness/`, with protocol and task
implementations in the neighboring `protocols/` and `tasks/` packages. During
evaluation it consumes the frozen JSON records under
`manifests/release/v0.4/` rather than a second runtime implementation under
`src/`.

## Top-level operational directories

- `scripts/`: task construction, release validation, image management, and
  result-analysis entry points;
- `configs/`: versioned profiles, policies, latency schedules, task selection,
  and pilot matrices;
- `schemas/`: published JSON Schema or equivalent machine-readable contracts;
- `manifests/`: candidate task inventories and frozen benchmark manifests;
- `tests/`: contract, unit, integration, and smoke validation;
- `docs/audits/`: evidence-backed infrastructure and leakage reports;
- `docs/design/`: design decisions that do not override the specification;
- `docs/protocols/`: operational protocols and preregistered experiment plans;
- `data/`: local source material and derived task metadata;
- `reproductions/`: the installable evaluation harness and protocol runtime;
- `outputs/`: generated trajectories, logs, metrics, and reports; outputs are
  local artifacts and are not part of the source release.

Public task repositories are independently materialized under:

```text
data/repos/commit0/<repo>
```

Their public origins and pinned refs live in
`configs/tasks/commit0_repositories.v0.3.json`. The repositories themselves are
local generated data and are not committed.

## Community contribution boundary

The official 19-task release is frozen. New Commit0-derived tasks are prepared
as qualification-ready candidates and promoted only through an explicit
release review. See `skills/contribute-commit0-task/` for the scoped authoring
workflow. Training code and unrelated predecessor-project components are not
part of this repository.
