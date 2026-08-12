# AsynCodeBench Quickstart

This is the shortest supported path from a fresh clone to one complete
four-protocol task evaluation.

## Requirements

- Linux on `x86_64`;
- Git and Docker with permission to run containers without `sudo`;
- Python 3.10 or newer;
- [`uv`](https://docs.astral.sh/uv/);
- an OpenAI-compatible model endpoint.

Local models additionally require a vLLM configuration that supports the
model's tool-call and reasoning formats. Read
[`LOCAL_VLLM_EXPERIMENT_RUNBOOK.md`](LOCAL_VLLM_EXPERIMENT_RUNBOOK.md) before
starting a local campaign.

## 1. Install

```bash
git clone https://github.com/KaituoZhang/Asynccodebench.git AsynCodeBench
cd AsynCodeBench
bash scripts/setup_evaluation.sh
```

The setup script:

1. installs the benchmark contract environment;
2. checks out the validated OpenHands SDK revision;
3. creates the native runner environment;
4. checks Docker;
5. runs the dataset and harness tests;
6. creates an untracked runner `.env` from the example when needed.

Native runs clone and verify their pinned public source repositories directly.
They do not require a local Commit0 dataset.

## 2. Configure A Model

Edit:

```text
reproductions/async-swe-agents/.env
```

For a hosted OpenAI-compatible endpoint, set:

```dotenv
LLM_BASE_URL=https://your-endpoint.example/v1
LLM_API_KEY=your-api-key
LLM_MODEL=openai/your-model-name
LLM_SUBAGENT_MODEL=
SDK_SOURCE_DIR=/absolute/path/to/AsynCodeBench/reproductions/software-agent-sdk
```

The provider prefix in `LLM_MODEL` is required by LiteLLM. Local endpoints may
use a non-secret dummy API key when their server requires a non-empty value.

## 3. Dry-run

```bash
cd reproductions/async-swe-agents

export ENV_FILE="$PWD/.env"
source scripts/env.sh

uv run asyncodebench doctor
uv run asyncodebench tasks

uv run asyncodebench run \
  --task asyncodebench:cachetools \
  --protocol all \
  --model "$LLM_MODEL" \
  --dry-run
```

To dry-run all four protocols with the campaign wrapper:

```bash

ENV_FILE="$PWD/.env" \
MODEL_TAG=my-model \
RUN_VERSION=smoke-v01 \
DRY_RUN=1 \
scripts/run_asyncodebench_all_protocols_env.sh cachetools
```

The four dry-runs should report:

```text
task_id=asyncodebench:cachetools
protocol=single | serial_specialists | async_private | caid_manager
official=True
curated_base_sha=<sha>
```

Dry-run does not call the model or start a task container.

## 4. Run One Task

```bash
ENV_FILE="$PWD/.env" \
MODEL_TAG=my-model \
RUN_VERSION=official-v01 \
WORKSPACE_PORT_STRATEGY=auto \
scripts/run_asyncodebench_all_protocols_env.sh cachetools
```

The wrapper runs the four protocols sequentially. It reads specialist counts
from the released scenario manifest and uses the official 30-iteration budgets.
An interrupted output directory remains immutable evidence; retry with a new
`RUN_VERSION`.

To run one protocol only, use the corresponding flag:

```bash
RUN_SINGLE=0 \
RUN_SERIAL=0 \
RUN_ASYNC_PRIVATE=1 \
RUN_CAID=0 \
ENV_FILE="$PWD/.env" \
MODEL_TAG=my-model \
RUN_VERSION=async-private-v01 \
WORKSPACE_PORT_STRATEGY=auto \
scripts/run_asyncodebench_all_protocols_env.sh cachetools
```

## 5. Inspect Results

Results are written under:

```text
outputs/asyncodebench/v0.3/<model>/<task>/<protocol>/<run-version>/
```

Each formal run should include:

```text
run_metadata.json
task_snapshot.json
scenario_snapshot.json
metrics_snapshot.json
protocol.json
report.json
dependency_probe_checkpoints.jsonl
process_metrics_summary.json
run_bundle.json
cost.json
runtime.txt
patch.diff
```

Validate any completed task-protocol run without calling the model again:

```bash
uv run asyncodebench validate-run \
  outputs/asyncodebench/v0.3/<model>/<task>/<protocol>/<run-version>
```

Coding failure is valid benchmark evidence. Provider, transport, parser,
workspace, or evaluator instrumentation failure invalidates the run. See
[`EVALUATION_METRICS.md`](EVALUATION_METRICS.md) for metric definitions and
[`MODEL_EXPERIMENT_RUNBOOK.md`](MODEL_EXPERIMENT_RUNBOOK.md) before running all
16 tasks.

## Use A Custom Agent

The built-in agent is `openhands`. A third-party adapter can replace coding
assignment execution while the harness retains protocol and evaluation control:

```bash
uv run asyncodebench run \
  --task asyncodebench:cachetools \
  --protocol serial_specialists \
  --model "$LLM_MODEL" \
  --agent-import-path my_agents.cache_agent:CacheAgent \
  --run-id custom-agent-v01
```

Read [`AGENT_ADAPTER.md`](AGENT_ADAPTER.md) before reporting custom-agent
results.
