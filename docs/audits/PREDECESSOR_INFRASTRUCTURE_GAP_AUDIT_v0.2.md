# Predecessor infrastructure gap audit against AsyncCodeBench v0.2

Status: initial code-level audit  
Specification: `SPECIFICATION_v0.2.md`  
Audit scope: the local predecessor prototype as observed on 2026-06-21

## 1. Executive decision

The predecessor contains useful deterministic infrastructure, but it is not an
AsyncCodeBench implementation. Migration must be selective.

The strongest reusable components are:

- deterministic equal-time event ordering;
- in-memory immutable workspace versions and branchable snapshots;
- unified-diff application;
- official Commit0 ref materialization without checkout mutation;
- policy-visible versus privileged-state separation tests;
- fixed-policy prototypes;
- trajectory and snapshot prototypes.

The largest gaps are:

- incomplete event and action semantics;
- no first-class causal, artifact, or message provenance;
- no configurable information-sharing profiles;
- no resource model or integration lifecycle;
- opaque pickle snapshots rather than public replay contracts;
- no capability-card or semantic-card enforcement;
- no systematic anti-leakage and exploit audit;
- qualification based partly on reference diffs rather than the v0.2
  agent-independent rubric;
- historical modules are coupled to FreshGRPO/Checkpoint-A assumptions.

The migration disposition is therefore `adapt`, not bulk reuse.

## 2. Evidence baseline

The existing predecessor Conda environment passed `pip check`, and pytest
collected 80 tests. The audit did not modify or execute write-producing
predecessor experiments.

Key evidence files:

- `freshcomm/schemas.py`
- `freshcomm/async_env/events.py`
- `freshcomm/async_env/simulator.py`
- `freshcomm/async_env/coding.py`
- `freshcomm/workspace/version_store.py`
- `freshcomm/workspace/patches.py`
- `freshcomm/marl/observations.py`
- `freshcomm/offline/environment_snapshots.py`
- `freshcomm/offline/trajectories.py`
- `freshcomm/policies/baselines.py`
- `freshcomm/tasks/commit0_official.py`
- `freshcomm/experiments/commit0_qualification.py`

## 3. Component disposition

| Predecessor component | Evidence | Status against v0.2 | Disposition | Main gap or constraint |
|---|---|---|---|---|
| `schemas.py` | Pydantic action, message, job, local-state models | Incompatible | Adapt | Uses coarse `ACT/VERIFY/SYNC/WAIT`; lacks required events, causal parents, visibility, provenance, profiles, artifacts, resources, cards |
| `async_env/events.py` | deterministic heap ordering and snapshots | Partial | Adapt | Event payload lacks schema version, causal parents, visibility, wall-clock time and payload reference |
| `async_env/simulator.py` | deterministic handlers, fork and restore | Partial | Adapt | Generic world snapshot is useful; no resource lifecycle, replay schedule contract, policy activation contract or public snapshot format |
| `workspace/version_store.py` | immutable versions, diff, ancestry, fork | Partial | Adapt | Strong primitive; identifiers are process-local, files are memory-only, no integrated/private workspace distinction, provenance or content hash |
| `workspace/patches.py` | trusted `git apply` in temporary directory | Partial | Adapt | Useful primitive; requires path/symlink/security audit and artifact provenance |
| `async_env/coding.py` | delayed jobs, local versions, stale/conflict counters | Incompatible | Rewrite around primitives | Role/action space is historical; messages are not separately sent/delivered/read; no profile/resource/integration semantics |
| `marl/observations.py` | policy-visible and privileged fingerprints | Partial | Adapt | Valid separation idea and test; tied to FreshGRPO namespace and one strict-hidden observation shape |
| `offline/environment_snapshots.py` | snapshot round trip | Incompatible for release | Rewrite | Pickle is opaque and unsafe as a public interchange format; does not meet v0.2 logical snapshot contents |
| `offline/trajectories.py` | serialized decisions/events | Partial | Adapt | Coupled to Checkpoint-A observations and scalar reward; missing artifacts, provenance, costs and public replay fields |
| `policies/baselines.py` | naive, sync, wait, periodic prototypes | Partial | Adapt later | No semantic cards; policy names hide exact messaging, workspace, repair, integration and resource semantics |
| `tasks/base.py` | repository task and pytest evaluation | Partial | Adapt | Useful evaluator abstraction; copies repository broadly and lacks evaluator isolation/leakage controls |
| `tasks/commit0_official.py` | read-only Git archive materialization | Partial | Adapt later | Uses reference-informed changed files, exposes changed tests, and writes predecessor-specific markers/cache paths |
| `experiments/commit0_qualification.py` | refs, executable baseline/reference checks | Partial | Rewrite qualification layer | Reference diff is gold-informed; no dual annotation, agreement, dependency separability, task cards or adjudication |
| agent backends | cached OpenAI-compatible inference | Partial | Defer | Only needed for live validation; cache isolation and audit policy are missing |
| `marl/`, compatible returns, Checkpoint-A generators | training/teacher-data code | Out of scope | Exclude | First paper does not train FreshGRPO or publish Checkpoint-A |
| Robotouille/Collab-Overcooked code | embodied adapters and scripts | Out of scope | Exclude | Not part of AsyncCodeBench |
| controlled cachetools freshness experiments | historical mechanism experiment | Out of scope as benchmark implementation | Exclude, retain as historical evidence | Synthetic/controlled intervention cannot define release tasks |

## 4. Requirement-by-requirement gaps

### 4.1 Events and activation

Existing support:

- deterministic logical clock;
- equal-time insertion ordering;
- event queue snapshot and fork;
- delayed job completion.

Missing:

- the complete v0.2 event vocabulary;
- separate message send, delivery, and read events;
- patch production and transfer;
- integration attempts and completion;
- resource acquisition and release;
- artifact invalidation;
- causal parent IDs and policy visibility;
- wall-clock timestamps for live mode;
- payload references separated from event records.

Decision: adapt the queue algorithm only after the new event contract is
frozen.

### 4.2 Actions

Existing support uses role-specific high-level actions grouped into
`ACT/VERIFY/SYNC/WAIT`.

This conflicts with v0.2, where those labels may be analysis categories but
must not replace concrete software-engineering operations. A new operation
contract is required for inspect, edit, test, message, transfer, synchronize,
review, integrate, cancel, submit, and terminate operations.

Decision: rewrite the action contract.

### 4.3 Information boundaries

The predecessor has a useful strict-hidden prototype: a hidden pending update changes
the privileged fingerprint without changing the policy observation. However:

- profile identity is not recorded;
- `shared-status` is absent;
- `manager-mediated` is absent;
- visibility is encoded procedurally rather than as a tested contract;
- no machine-readable capability cards constrain policies and oracles.

Decision: adapt the separation test, then implement profile-specific
observation builders.

### 4.4 Provenance and invalidation

Message envelopes retain a base version and evidence IDs, and jobs retain a
base version. This is insufficient to reconstruct:

- send/delivery/read lifecycle;
- artifact input lineage;
- read and write sets;
- producer command;
- consumer workspace version;
- validity and invalidation lifecycle.

Decision: introduce first-class message and artifact provenance contracts
before migrating runtime behavior.

### 4.5 Workspace and integration

`VersionedWorkspace` is a useful pure primitive and has tests for diff,
ancestry, branching, and fork isolation.

Missing:

- stable content-addressed identifiers;
- explicit private versus integrated branches;
- integration attempts, rejection and rollback;
- artifact/read/write provenance;
- safe filesystem-backed task worktrees;
- symlink, path traversal and evaluator boundary controls.

Decision: migrate only after contracts; retain behavior tests and add security
and integration tests.

### 4.6 Trace, replay, and live execution

Predecessor snapshots can reproduce in-process branches, but their serialized
form is opaque pickle. This is useful for local historical experiments but
cannot serve as a safe, versioned public replay asset.

Missing:

- recorded exogenous schedules;
- resource assignments;
- replay input/output references;
- public logical snapshot schema;
- paired replay checks;
- replay-to-live agreement metrics.

Decision: reuse snapshot concepts, not the serialization format.

### 4.7 Commit0 qualification and adapter

Strengths:

- ref resolution without mutating source checkouts;
- archive-based materialization;
- baseline and reference test execution;
- timeout and failure classification.

Risks:

- changed source/test files are derived from reference diffs;
- visible changed tests may expose gold-informed localization;
- cached materialization has no general exploit audit;
- direct local pytest does not reproduce every official environment;
- current suitability is mostly based on changed-file count.

Decision: retain these tools as secondary evidence. Implement the v0.2 task
card and agent-independent qualification process before importing tasks.

### 4.8 Anti-leakage

No complete protocol currently checks Git history, hidden refs, caches,
environment variables, mounted paths, network access, cross-agent files,
replay visibility, or evaluator artifacts. Existing local repositories contain
reference refs and historical caches, so direct reuse would violate the
release threat model.

Decision: leakage audit is a release-blocking feature.

### 4.9 Baselines and oracles

Predecessor fixed policies are prototypes. There is no state-oracle policy
matching v0.2 capability constraints, no protected state oracle, and no
machine-tested parity of model, tools, decomposition, and budget.

Decision: migrate fixed policy ideas only after semantic cards and capability
cards exist.

### 4.10 Metrics

The predecessor records simple stale-action, sync, verification, conflict, message,
test, and update counts. It does not compute intervention-based semantic
staleness harm, normalized coordination regret, invalidation quality,
integration churn, critical-path cost, or replay/live divergence.

Decision: rewrite metrics against the new trajectory and provenance contracts.

## 5. Migration gates

A component may enter AsyncCodeBench only when:

1. its v0.2 contract is explicit;
2. no import points back to `freshcomm`;
3. behavior tests are copied or rewritten;
4. new information-boundary tests are added where relevant;
5. the component runs in the `AsyncCodeBench` Conda environment;
6. historical reward, training, and embodied assumptions are removed;
7. the migration is documented in this report.

## 6. Approved migration sequence

1. benchmark-native contracts and schema tests;
2. workspace and patch primitives;
3. deterministic event queue under the new event contract;
4. information-profile observation boundaries;
5. task qualification cards and annotation records;
6. sanitized Commit0 materialization;
7. trajectory and logical snapshot contracts;
8. replay and live runtime;
9. baseline and oracle policies;
10. metrics and Go/No-Go pipelines.

## 7. Current migration record

### Batch 1 — contracts

Disposition: `adapt`.

The original predecessor schema is not copied. AsyncCodeBench defines fresh
versioned contracts for events, concrete operations, messages, artifacts,
jobs, resources, task qualification, capability cards, and baseline semantic
cards. Tests enforce the most important information and lifecycle invariants.

No predecessor files were deleted or modified.

### Batch 2 — workspace and patch primitives

Disposition: `adapt`.

Migrated behavior:

- immutable workspace versions;
- deterministic diff and ancestry checks;
- independent workspace forks;
- unified-diff application through `git apply`.

Added v0.2 requirements:

- content-addressed version and content identifiers;
- explicit integrated and per-agent private branch heads;
- compare-and-swap integration;
- rejection of stale private integration even when the caller knows the
  current integrated version;
- source artifact lineage on private and integrated versions;
- strict relative-path validation and `.git` metadata protection;
- editable-path allowlists;
- bounded text-only patch handling;
- automatically generated patch artifact provenance.

The implementation intentionally does not perform automatic merge, rebase, or
repair. Those are runtime-protection conditions and must be represented as
explicit benchmark operations rather than hidden workspace behavior.

Files:

- `src/asynccodebench/runtime/workspace.py`
- `src/asynccodebench/runtime/patches.py`
- `tests/unit/test_workspace.py`
- `tests/unit/test_patches.py`

No predecessor files were deleted or moved.

### Parallel batch — qualification and causal event queue

The two independent workstreams completed under
`docs/protocols/PARALLEL_IMPLEMENTATION_PLAN_v0.2.md`.

Qualification now provides:

- strict candidate, annotation, and adjudication inputs;
- exactly two independent annotators per task;
- independent adjudicator checks;
- pre-adjudication agreement rates and Cohen's kappa;
- deterministic JSON and CSV manifests retaining excluded candidates.

The deterministic causal event queue now provides:

- logical-time, priority, and stable insertion ordering;
- event identity and causal-parent validation;
- visibility-preserving pending and processed views;
- deterministic snapshot, restore, and fork.

A task-agnostic integration test confirms that workspace versions reference
causal event IDs without exposing private patch events to unauthorized
observers. No model inference is involved.

### Strict-route correction — qualification freeze

After the compliance review, runtime expansion was paused and Phase 2 resumed.
The qualification rubric now records all eight v0.2 evidence categories in
structured form, including test-target independence, static dependency edges,
shared-resource contention, and reproducible timing metadata.

The first Commit0 candidate inventory was regenerated from public `commit0`
refs only. The extractor contains no reference-ref or solution-diff path, does
not follow repository symlinks, and leaves the gold secondary label empty.
This inventory is evidence for annotation, not a frozen pilot manifest.
