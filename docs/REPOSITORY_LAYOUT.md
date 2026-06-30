# AsyncCodeBench repository layout

This layout implements Specification v0.2. It separates benchmark semantics
from executable pipelines, task material, experimental configuration, and
generated outputs.

## Core library

`src/asynccodebench/` contains importable benchmark code:

- `contracts/`: typed task, event, action, observation, message, job, resource,
  artifact, snapshot, trajectory, and outcome contracts;
- `adapters/`: official task-source adapters without benchmark-specific task
  modification;
- `runtime/`: event scheduling, information profiles, workspace isolation,
  asynchronous jobs, messaging, provenance, snapshots, replay, and live
  execution;
- `policies/`: fixed policies, runtime-protection conditions, and audited
  oracles;
- `qualification/`: task-card generation, annotation, agreement, and
  adjudication;
- `metrics/`: task outcomes, cost accounting, staleness harm, invalidation,
  synchronization, and integration diagnostics;
- `audit/`: leakage, exploit, capability, semantic-card, and trajectory audits;
- `agents/`: model/tool interfaces shared by policies, without training code;
- `utils/`: narrow utilities with no benchmark semantics.

## Top-level operational directories

- `pipelines/`: reproducible workflows that compose library components;
- `scripts/`: thin human-facing CLIs; business logic belongs in the library;
- `configs/`: versioned profiles, policies, latency schedules, task selection,
  and pilot matrices;
- `schemas/`: published JSON Schema or equivalent machine-readable contracts;
- `manifests/`: candidate task inventories and frozen benchmark manifests;
- `tests/`: contract, unit, integration, and smoke validation;
- `docs/audits/`: evidence-backed infrastructure and leakage reports;
- `docs/design/`: design decisions that do not override the specification;
- `docs/protocols/`: operational protocols and preregistered experiment plans;
- `data/`: local source material and derived task metadata;
- `outputs/`: generated trajectories, logs, metrics, and reports.

## Predecessor-code migration rule

The predecessor prototype remains external to AsyncCodeBench. Components are
copied only after they receive one of these audit dispositions:

1. `reuse`: semantics already satisfy v0.2;
2. `adapt`: useful implementation with a documented contract gap;
3. `rewrite`: concept is needed but implementation violates the new boundary;
4. `exclude`: historical training, embodied, or obsolete preliminary code.

Migration is copy-and-verify, not a destructive filesystem move. AsyncCodeBench
must not contain runtime paths or imports that point to the predecessor
workspace.

Public task repositories are independently materialized under:

```text
data/repos/commit0/<repo>
```

Their public origins and pinned refs live in
`configs/tasks/commit0_repositories.v0.3.json`. The repositories themselves are
local generated data and are not committed.

## Historical migration order

1. contracts and pure schemas;
2. immutable workspace/version and patch primitives;
3. deterministic event scheduler and snapshots;
4. official Commit0 qualification and adapter code;
5. fixed baseline policies;
6. trajectory serialization and replay support;
7. agent backends needed by live validation.

Training, GRPO, LoRA, Robotouille, Collab-Overcooked, and historical
Checkpoint-A-specific code are excluded from the initial migration.
