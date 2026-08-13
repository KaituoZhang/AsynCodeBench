# Community Release And Agent Adapter Implementation Record

Implementation status: Stages 1-3 and strict run admission and script-level
aggregation in Stage 4 are implemented on `agent/community-ready-release`.
Run bundles execute their JSON Schema, record metric-specific eligibility,
verify the official execution profile, and reject infrastructure-invalid
evidence. Model-level aggregation is fail-closed and emits a checksum-linked
campaign manifest. Remaining release work is publishing a real validated
native model result; historical pre-bundle runs are not accepted as a substitute.

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
uv run asyncodebench run \
  --task asyncodebench:cachetools \
  --agent openhands \
  --model openai/my-model \
  --protocol all \
  --run-id model-cachetools-v01
```

### Custom agent

```bash
uv run asyncodebench run \
  --task asyncodebench:cachetools \
  --agent-import-path my_agents.codex_agent:CodexAgent \
  --model my-model \
  --protocol all \
  --run-id codex-cachetools-v01
```

### Validate and summarize

```bash
uv run asyncodebench validate-run outputs/.../run-id
```

The shell wrapper remains the supported way to run all four protocols in one
campaign. It accepts the same adapter through `ASYNCODEBENCH_AGENT_IMPORT_PATH`.

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
configs/evaluation/official_execution_profile.v2.json
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
manifests/release/v0.3/official_tasks.json
manifests/release/v0.3/task_index.json
reproductions/software-agent-sdk.lock
scripts/setup_evaluation.sh
examples/results/cachetools/
docs/QUICKSTART.md
docs/AGENT_ADAPTER.md
docs/RESULT_VALIDITY.md
```

### Add for custom agents

```text
reproductions/async-swe-agents/agents/base.py
reproductions/async-swe-agents/agents/loader.py
reproductions/async-swe-agents/agents/openhands.py
reproductions/async-swe-agents/asyncodebench_harness/cli.py
reproductions/async-swe-agents/asyncodebench_harness/results.py
reproductions/async-swe-agents/asyncodebench_harness/health.py
schemas/release/agent_request.schema.json
schemas/release/agent_response.schema.json
schemas/release/run_bundle.schema.json
reproductions/async-swe-agents/examples/agents/diagnostic_adapter.py
reproductions/async-swe-agents/tests/test_agent_adapter_contract.py
reproductions/async-swe-agents/tests/test_run_bundle.py
```

## Agent Contract

Keep the adapter interface deliberately small:

```python
class AgentAdapter(ABC):
    def execute(self, request: AgentRunRequest) -> AgentRunResponse:
        ...
```

`AgentRunRequest` contains:

```text
benchmark_task_id
source_task_id
protocol
scenario_id
agent_id
assignment_id
round_num
instruction
workspace handle
writable_paths
primary_test_targets
dependency_annotations
iteration budget
output directory
```

`AgentRunResponse` contains only execution telemetry:

```text
iterations
input_tokens
output_tokens
cost
error
events
adapter metadata
```

The harness derives commit, changed paths, patch success, runtime, merge status,
and final score independently. The adapter does not merge its own patch and does
not run the official final evaluator.

## Standard Result Bundle

Every formal task-protocol run must contain:

```text
run_metadata.json
task_snapshot.json
scenario_snapshot.json
scenario_manifest_snapshot.json
metrics_snapshot.json
quality_snapshot.json
execution_profile_snapshot.json
protocol.json
report.json
dependency_probe_checkpoints.jsonl
process_metrics_summary.json
cost.json
runtime.txt
run_bundle.json
```

`patch.diff` is emitted when the protocol has an integrated patch. It is not a
required artifact for a valid unchanged single-agent failure.

Multi-agent protocols additionally contain the applicable files:

```text
scope_validation.jsonl
artifact_handoffs.jsonl
delegations.json
delegation_validation.json
agent_events/
```

`run_bundle.schema.json` defines identity, profile, provenance, status,
metric-specific eligibility, evaluator outcome, and recursive artifact hashes.
Detailed model, budget, serving, and generation configuration remains frozen in
the checksum-indexed `run_metadata.json`. A run with provider, transport,
workspace, context, model-server, or evaluator instrumentation failure is
invalid rather than counted as a coding failure.

## Implementation Stages

### Stage 1: Release hygiene and one-command setup (implemented except example publication)

1. Add GitHub Actions for the dataset contracts and harness tests.
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

### Stage 2: Extract the built-in OpenHands adapter (implemented)

1. Introduce `AgentRunRequest`, `AgentRunResponse`, and `AgentAdapter`.
2. Move the existing OpenHands conversation/subagent invocation behind
   `OpenHandsAgentAdapter` without changing scheduling or evaluation behavior.
3. Make all four native protocols call the adapter instead of constructing an
   OpenHands agent directly.
4. Add a deterministic fake adapter for contract tests.

Acceptance criteria:

- existing OpenHands runs preserve their current prompts and output semantics;
- all benchmark-contract and native-harness tests remain green;
- the fake adapter can exercise all four protocols without an API key;
- scope, stale visibility, handoff, integration, and probe gates remain owned by
  the harness.

### Stage 3: Add Harbor-style custom agent loading (implemented)

1. Add `--agent openhands` and `--agent-import-path module:Class`.
2. Validate that an imported class implements `AgentAdapter`.
3. Provide `examples/agents/diagnostic_adapter.py` and an adapter guide.
4. Record adapter module, class, package version, and source revision in
   `run_metadata.json`.
5. Reject adapters that attempt to bypass the assigned workspace or return an
   artifact outside writable scope.

Acceptance criteria:

- a third-party agent can run without editing AsynCodeBench source;
- the same custom agent works under all four protocols;
- an out-of-scope fake agent is rejected and recorded;
- serial handoffs are visible and async-private in-flight handoffs are hidden.

### Stage 4: Standardize validation and reporting (implemented; unified CLI pending)

1. Define dataclass request/response contracts and JSON Schemas for agent and
   run-bundle interchange.
2. Add `inspect-run` and `validate-run`; a unified `summarize` CLI remains
   pending while the existing analysis scripts remain available.
3. Generate per-task Markdown/CSV/index records and model-level CSV/Markdown
   tables with a campaign manifest.
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
