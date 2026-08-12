# AsynCodeBench Native Agent Harness

This directory contains the OpenHands-powered execution harness for
AsynCodeBench.

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

## Run

Run all four official protocols for one task:

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
```

Use `DRY_RUN=1` to verify task selection, assignments, integration order, and
workspace configuration without calling a model.

## Outputs

Native output directories contain frozen task/scenario/metric snapshots,
protocol metadata, model and environment provenance, agent events, patches,
scope and integration decisions, dependency checkpoints, final evaluator
results, process metrics, cost, tokens, and runtime.

The runner generates `process_metrics_summary.json` automatically. See
[`../../docs/EVALUATION_METRICS.md`](../../docs/EVALUATION_METRICS.md) for the
formal metrics and unresolved-value policy.

## Public Documentation

- [`../../docs/QUICKSTART.md`](../../docs/QUICKSTART.md)
- [`../../docs/ASYNCODEBENCH_HARNESS_V2.md`](../../docs/ASYNCODEBENCH_HARNESS_V2.md)
- [`../../docs/MODEL_EXPERIMENT_RUNBOOK.md`](../../docs/MODEL_EXPERIMENT_RUNBOOK.md)
- [`../../docs/LOCAL_VLLM_EXPERIMENT_RUNBOOK.md`](../../docs/LOCAL_VLLM_EXPERIMENT_RUNBOOK.md)

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
