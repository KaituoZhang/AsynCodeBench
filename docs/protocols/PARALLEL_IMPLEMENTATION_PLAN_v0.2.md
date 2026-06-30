# Parallel implementation plan

Specification: AsyncCodeBench v0.2  
Status: active implementation protocol  
Date: 2026-06-22

## 1. Purpose

Two independent workstreams proceed concurrently:

1. pilot task qualification and candidate manifests;
2. deterministic causal event infrastructure.

They must not depend on each other's internal implementation. Their first
integration point is a task-agnostic smoke episode selected from an approved
candidate manifest.

## 2. Workstream A — task qualification

Owns:

- candidate task metadata;
- independent annotation records;
- agreement statistics;
- adjudication records;
- exclusion reasons;
- JSON and CSV candidate manifests.

Must not:

- execute agent policies;
- depend on event scheduling;
- use gold patches as the primary label;
- silently discard excluded candidates;
- assign benchmark roles to manufacture parallelism.

Completion gate:

- deterministic manifest generation;
- at least two annotator decisions per finalized card;
- explicit disagreement and adjudication handling;
- agreement summary by task source and overall;
- complete included and excluded candidate records;
- schema-valid `QualificationCard` output.

## 3. Workstream B — causal event queue

Owns:

- deterministic priority and equal-time ordering;
- event identity;
- causal-parent validation;
- event visibility preservation;
- queue snapshot, restoration, and fork;
- processed-event history needed to validate new causal parents.

Must not:

- know Commit0 or SWE-bench task semantics;
- inspect policy-hidden payloads;
- implement agent turns;
- introduce implicit workspace synchronization;
- serialize arbitrary operating-system processes.

Completion gate:

- deterministic ordering under repeated runs;
- rejection of missing, future, duplicate, and self causal parents;
- snapshot/restore continuation equality;
- fork independence;
- exact preservation of `visible_to` and payload references;
- compatibility with `WorkspaceStore` identifiers.

## 4. Shared contracts

The shared boundary is limited to:

- `QualificationCard`;
- `EventRecord`;
- `WorkspaceVersionRecord`;
- `WorkspaceStateRecord`;
- stable task, event, artifact, and workspace identifiers.

Neither workstream may change shared contracts independently. Contract changes
require a main integration review and regenerated public JSON Schemas.

## 5. Integration smoke gate

After both workstreams pass independently:

1. select two or three Commit0 candidates without using their reference patch
   as a primary qualification signal;
2. create one integrated workspace and two private workspaces;
3. schedule deterministic agent activation and tool-job events;
4. apply one private patch artifact;
5. record workspace-update and integration events with causal parents;
6. snapshot before integration;
7. restore and verify identical event and workspace continuation;
8. verify that a strict-hidden agent cannot infer another private workspace
   from event visibility;
9. produce a smoke trajectory only after trajectory contracts are frozen.

This gate tests protocol compatibility. It does not establish the scientific
coordination gap.

## 6. Current candidate evidence

The predecessor prototype's historical Commit0 qualification file contains six
repositories:

- `cachetools`;
- `tinydb`;
- `wcwidth`;
- `voluptuous`;
- `deprecated`;
- `portalocker`.

The historical labels and changed-file lists are gold-informed secondary
evidence only. AsyncCodeBench must regenerate primary qualification cards from
public task information, executable tests, dependency structure, and measured
runtime.

## 7. Model boundary

No model server is needed for either workstream or their contract-level smoke
gate. vLLM is introduced later for:

- strong single-agent live validation;
- multi-agent live baseline runs;
- empirical LLM latency traces;
- replay-to-live transfer checks.

Model outputs, cache keys, generation settings, hardware, and latency must be
recorded when that phase begins.
