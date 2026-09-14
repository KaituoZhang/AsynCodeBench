# AsynCodeBench Native Agent Harness

This directory contains the native execution harness for AsynCodeBench. It
ships an OpenHands coding agent and a public adapter for third-party agents.

AsynCodeBench owns the released task contracts, protocol scheduling, private
workspace visibility, writable scope, integration order, dependency probes,
evaluation, and result provenance. OpenHands supplies the coding-agent loop,
tools, remote agent server, and Docker workspace runtime.

## Install

From the repository root:

```bash
bash scripts/setup_evaluation.sh
```

The script creates this runner's `.venv`, checks out the exact OpenHands SDK
revision recorded in `../software-agent-sdk.lock`, checks Docker, and runs the
harness tests.

Then edit the untracked `.env` in this directory with an OpenAI-compatible
endpoint, API key, LiteLLM model identifier, and `SDK_SOURCE_DIR`.

Verify the installation:

```bash
uv run asyncodebench doctor
uv run asyncodebench tasks
```

## Run

For the qualified Apache TVM 20153 task, first reconstruct the isolated TVM
runtime and follow
[`../../docs/PR_HARD_20153_COLLABORATOR_RUNBOOK.md`](../../docs/PR_HARD_20153_COLLABORATOR_RUNBOOK.md).
The task wrapper validates the runtime before any model call:

```bash
ENV_FILE="$PWD/.env" \
RUN_ID="my-model-20153-seed1-$(date -u +%Y%m%dT%H%M%SZ)" \
scripts/run_pr_hard_20153_all_protocols_env.sh
```

Run the original four-protocol profile for one task:

```bash
ENV_FILE="$PWD/.env" \
MODEL_TAG=my-model \
RUN_VERSION=official-v01 \
WORKSPACE_PORT_STRATEGY=auto \
scripts/run_asyncodebench_all_protocols_env.sh cachetools
```

The public task ID is `asyncodebench:<task>`. The wrapper accepts a short task
name for convenience, resolves the official release record, reads the agent
count from the scenario manifest, and calls `run_asyncodebench.py`.

Supported protocols:

```text
single
serial_specialists
async_private
caid_manager
async_manager
```

`caid_manager` is the read-only-manager condition (Async-RO-Manager), while
`async_manager` is the online, scope-constrained editing manager. Run all five
official protocols with:

```bash
ENV_FILE="$PWD/.env" \
MODEL_TAG=my-model \
RUN_VERSION=five-protocol-v01 \
WORKSPACE_PORT_STRATEGY=auto \
scripts/run_asyncodebench_five_protocols_env.sh cachetools
```

Use `DRY_RUN=1` to verify task selection, assignments, integration order, and
workspace configuration without calling a model.

Run one protocol directly:

```bash
uv run asyncodebench run \
  --task asyncodebench:cachetools \
  --protocol async_private \
  --model "$LLM_MODEL" \
  --run-id smoke-v01
```

Load a third-party agent with `--agent-import-path module:Class`. The class must
implement `agents.AgentAdapter`; see
[`../../docs/AGENT_ADAPTER.md`](../../docs/AGENT_ADAPTER.md).

## Outputs

Native output directories contain frozen task/scenario/metric snapshots,
protocol metadata, model and environment provenance, agent events, patches,
scope and integration decisions, dependency checkpoints, final evaluator
results, process metrics, cost, tokens, and runtime.

The runner generates `process_metrics_summary.json` and a checksum-indexed
`run_bundle.json` automatically. The bundle records the released execution
profile, metric-specific and provenance eligibility, infrastructure health, and
recursive artifact hashes. Validate a completed run with
`uv run asyncodebench validate-run <run-dir>`; use
`uv run asyncodebench inspect-run <run-dir>` for a historical directory that
predates bundles. See [`../../docs/RESULT_VALIDITY.md`](../../docs/RESULT_VALIDITY.md)
for admission rules and see
[`../../docs/EVALUATION_METRICS.md`](../../docs/EVALUATION_METRICS.md) for the
formal metrics and unresolved-value policy.

## Public Documentation

- [`../../docs/QUICKSTART.md`](../../docs/QUICKSTART.md)
- [`../../docs/ASYNCODEBENCH_HARNESS_V2.md`](../../docs/ASYNCODEBENCH_HARNESS_V2.md)
- [`../../docs/MODEL_EXPERIMENT_RUNBOOK.md`](../../docs/MODEL_EXPERIMENT_RUNBOOK.md)
- [`../../docs/LOCAL_VLLM_EXPERIMENT_RUNBOOK.md`](../../docs/LOCAL_VLLM_EXPERIMENT_RUNBOOK.md)
- [`../../docs/AGENT_ADAPTER.md`](../../docs/AGENT_ADAPTER.md)

## Lineage And Legacy Reproduction

The manager-mediated protocol derives from CAID's centralized asynchronous
isolated delegation design. AsynCodeBench adds released task manifests,
controlled protocol baselines, dependency labels and probes, scope and
delegation gates, deterministic integration, evaluator contracts, and standard
run provenance.

The `run_commit0_*` scripts, `tasks/commit0.py`, PaperBench adapter, and older
prompt files remain for historical result reproduction. They are not the public
interface for new AsynCodeBench runs.

See the repository-level `LICENSE`, `THIRD_PARTY_NOTICES.md`, and `CITATION.cff`
for licensing, attribution, and citation information.
