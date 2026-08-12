# Community Release And Agent Adapter Plan

## Goal

Make AsynCodeBench usable through the same basic workflow as established coding
benchmarks:

```text
install the harness
-> select a released task set
-> select a built-in or custom agent
-> run one command
-> validate a standard result bundle
```

This plan does not replace the native harness. It packages the existing task,
protocol, workspace, probe, and evaluator contracts behind a smaller public
interface.

## Reference Pattern

The implementation follows two established patterns:

1. SWE-bench separates agent inference from a reproducible Docker evaluator and
   accepts a documented prediction format.
2. Harbor keeps the benchmark and environment fixed while allowing a custom
   agent to be loaded from an import path.

AsynCodeBench needs both properties because final patches alone cannot recover
strict DRS, CAIL, scope violations, handoffs, or integration failures. Custom
agents must therefore run inside the AsynCodeBench protocol harness for formal
process-metric results.

## Target User Experience

### Built-in OpenHands agent

```bash
asyncodebench run \
  --task cachetools \
  --agent openhands \
  --model openai/my-model \
  --protocol all \
  --run-id model-cachetools-v01
```

### Custom agent

```bash
asyncodebench run \
  --task cachetools \
  --agent-import-path my_agents.codex_agent:CodexAgent \
  --model my-model \
  --protocol all \
  --run-id codex-cachetools-v01
```

### Validate and summarize

```bash
asyncodebench validate-run outputs/.../run-id
asyncodebench summarize outputs/.../run-id
```

The existing shell wrapper remains available for compatibility. The commands
above become the documented public interface after the adapter work is complete.

## Benchmark Boundary

The harness, not an agent adapter, owns:

- official task selection and source SHA verification;
- bootstrap overlay application;
- task decomposition and writable paths;
- protocol scheduling and information visibility;
- private worktree creation;
- integration order and scope validation;
- dependency checkpoints;
- final evaluator execution;
- result validation and aggregation.

An agent adapter owns only:

- consuming an assigned instruction and visible context;
- using tools in the assigned workspace;
- producing a commit or patch;
- returning usage and status metadata;
- optionally emitting messages through harness-provided callbacks.

This boundary prevents a custom agent from silently changing the benchmark
protocol while still allowing different coding-agent implementations.

## Required Public Files

### Reuse without changing semantics

```text
configs/tasks/commit0_official_tasks.v0.3.json
configs/tasks/commit0_curated_tasks.v0.3.json
manifests/pilot/v0.3/{tasks,scenarios,metrics,quality}/
data/overlays/commit0/
reproductions/async-swe-agents/tasks/asyncodebench.py
reproductions/async-swe-agents/protocols/asyncodebench/
reproductions/async-swe-agents/core/dependency_probes.py
scripts/analyze_run_process_metrics.py
scripts/aggregate_model_task_results.py
```

### Add for a clean release

```text
.github/workflows/ci.yml
manifests/release/1.0/official_tasks.json
manifests/release/1.0/task_index.json
reproductions/software-agent-sdk.lock
scripts/setup_evaluation.sh
examples/results/cachetools/
docs/QUICKSTART.md
docs/AGENT_ADAPTER.md
```

### Add for custom agents

```text
src/asyncodebench/agents/base.py
src/asyncodebench/agents/loader.py
src/asyncodebench/agents/openhands.py
src/asyncodebench/cli.py
src/asyncodebench/results/models.py
src/asyncodebench/results/validation.py
schemas/release/agent_request.schema.json
schemas/release/agent_result.schema.json
schemas/release/run_bundle.schema.json
examples/agents/minimal_agent.py
tests/agents/test_agent_loader.py
tests/agents/test_agent_contract.py
tests/integration/test_custom_agent_protocols.py
tests/results/test_run_bundle_validation.py
```

## Agent Contract

Keep the adapter interface deliberately small:

```python
class AgentAdapter(ABC):
    async def run(self, request: AgentRequest) -> AgentResult:
        ...
```

`AgentRequest` contains:

```text
task_id
protocol
agent_id
subproblem_id
instruction
workspace handle
writable_paths
visible_handoffs
iteration or time budget
output directory
```

`AgentResult` contains:

```text
status
commit_hash or patch
changed_paths
messages
iterations
input_tokens
output_tokens
cost
runtime
error
```

The adapter does not merge its own patch and does not run the official final
evaluator. The harness validates scope, integrates the artifact, runs probes,
and writes the formal result.

## Standard Result Bundle

Every formal task-protocol run must contain:

```text
run_metadata.json
task_snapshot.json
scenario_snapshot.json
metrics_snapshot.json
quality_snapshot.json
protocol.json
agent_result.json
patch.diff
report.json
dependency_probe_checkpoints.jsonl
process_metrics_summary.json
cost.json
runtime.txt
```

Multi-agent protocols additionally contain the applicable files:

```text
scope_validation.jsonl
artifact_handoffs.jsonl
delegations.json
delegation_validation.jsonl
agent_events/
```

`run_bundle.schema.json` defines required files, schema versions, benchmark
revision, task ID, protocol, agent identity, model identity, budgets, serving
configuration, and evaluator status. A run with a provider, transport,
workspace, parser, or evaluator instrumentation failure is invalid rather than
counted as a coding failure.

## Implementation Stages

### Stage 1: Release hygiene and one-command setup

1. Add GitHub Actions for the existing 122 dataset contracts and 76 harness
   tests.
2. Generate a clean release index containing exactly the 16 official tasks.
3. Pin OpenHands `software-agent-sdk` to the currently validated commit instead
   of cloning an arbitrary latest revision.
4. Add `scripts/setup_evaluation.sh` to create the runner environment, fetch the
   pinned SDK checkout, and verify Docker.
5. Remove `COMMIT0_DATASET_PATH` from the native quickstart. Native curated runs
   clone the pinned source repository directly; the local dataset is only a
   legacy-runner requirement.
6. Replace the inherited CAID body in the runner README with links to lineage
   and historical reproduction documentation.
7. Publish one small cachetools example result without credentials or large
   repository archives.

Acceptance criteria:

- a fresh clone reaches a four-protocol dry-run using one setup script;
- CI runs on every pull request;
- the release index contains 16 tasks and 64 scenarios;
- no native quickstart requires the legacy Commit0 dataset;
- the SDK revision recorded in run metadata matches the lock file.

### Stage 2: Extract the built-in OpenHands adapter

1. Introduce `AgentRequest`, `AgentResult`, and `AgentAdapter`.
2. Move the existing OpenHands conversation/subagent invocation behind
   `OpenHandsAgentAdapter` without changing scheduling or evaluation behavior.
3. Make all four native protocols call the adapter instead of constructing an
   OpenHands agent directly.
4. Add a deterministic fake adapter for contract tests.

Acceptance criteria:

- existing OpenHands runs preserve their current prompts and output semantics;
- all existing 198 tests remain green;
- the fake adapter can exercise all four protocols without an API key;
- scope, stale visibility, handoff, integration, and probe gates remain owned by
  the harness.

### Stage 3: Add Harbor-style custom agent loading

1. Add `--agent openhands` and `--agent-import-path module:Class`.
2. Validate that an imported class implements `AgentAdapter`.
3. Provide `examples/agents/minimal_agent.py` and an adapter guide.
4. Record adapter module, class, package version, and source revision in
   `run_metadata.json`.
5. Reject adapters that attempt to bypass the assigned workspace or return an
   artifact outside writable scope.

Acceptance criteria:

- a third-party agent can run without editing AsynCodeBench source;
- the same custom agent works under all four protocols;
- an out-of-scope fake agent is rejected and recorded;
- serial handoffs are visible and async-private in-flight handoffs are hidden.

### Stage 4: Standardize validation and reporting

1. Define Pydantic and JSON Schema models for an agent result and run bundle.
2. Add `validate-run` and `summarize` commands around existing analysis scripts.
3. Generate per-instance JSONL and aggregate JSON/CSV tables.
4. Add a submission example and a CI test that validates it.

Acceptance criteria:

- results from different agents have the same top-level schema;
- aggregate scripts never infer protocol or model identity from folder names;
- unresolved DRS and CAIL use the documented penalty policy;
- final-only patches are labeled `final_only` and cannot claim strict process
  metrics.

### Stage 5: Versioned public release

1. Merge the evaluation branch into the public default branch.
2. Publish a release tag and GitHub release notes.
3. Publish the 16-task metadata bundle through GitHub Releases or Hugging Face.
4. Document tested host platforms, Docker requirements, resource requirements,
   known issues, and expected runtime/cost.
5. Accept community result bundles only after schema validation and provenance
   checks.

## CI Matrix

The initial CI should stay small:

```text
benchmark-contracts:
  install top-level package
  run tests/contracts

harness-unit:
  install runner with uv
  run reproductions/async-swe-agents/tests

release-consistency:
  validate exactly 16 official tasks
  validate four scenarios per task
  validate all manifest and overlay checksums
  run native four-protocol dry-run with a fake model configuration

documentation:
  reject broken relative Markdown links
  reject committed .env files, outputs, datasets, and API-key patterns
```

A Docker-backed cachetools evaluator smoke can run on a scheduled workflow after
the no-cost CI is stable; it does not need to block every documentation pull
request.

## Deliberate Non-goals

Do not add these before the four stages above work:

- a hosted leaderboard service;
- cloud execution providers;
- a web UI;
- a new agent runtime;
- automatic conversion of arbitrary benchmarks;
- support for custom protocols that change benchmark semantics.

The first public goal is narrower: install reliably, run the released tasks,
plug in a custom coding agent through one interface, and produce a comparable
validated result bundle.
