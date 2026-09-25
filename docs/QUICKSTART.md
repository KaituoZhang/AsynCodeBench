# AsynCodeBench Quickstart

This is the shortest supported path from a fresh clone to one complete
five-protocol task evaluation.

## Requirements

- Linux on `x86_64`;
- Git and Docker with permission to run containers without `sudo`;
- Python 3.12 (required by the native OpenHands runner);
- [`uv`](https://docs.astral.sh/uv/);
- an OpenAI-compatible model endpoint.

If Python 3.12 is not already visible to `uv`, install its managed build with
`uv python install 3.12`. The setup script resolves that interpreter through
`uv python find 3.12`, so an older system `python3` does not interfere.

Local models additionally require a vLLM configuration that supports the
model's tool-call and reasoning formats. Read
[`LOCAL_VLLM_EXPERIMENT_RUNBOOK.md`](LOCAL_VLLM_EXPERIMENT_RUNBOOK.md) before
starting a local campaign.

## 1. Install

```bash
git clone --branch agent/community-ready-release --single-branch \
  https://github.com/KaituoZhang/Asynccodebench.git AsynCodeBench
cd AsynCodeBench
bash scripts/setup_evaluation.sh
```

The setup script:

1. installs the benchmark contract environment;
2. checks out the validated OpenHands SDK revision and rejects local changes;
3. creates the native runner environment and verifies that host and server
   package versions and event schemas match;
4. checks Docker;
5. materializes pinned repositories used by source contract tests;
6. runs the dataset and harness tests;
7. creates an untracked runner `.env` from the example when needed.

See [`OPENHANDS_RUNTIME_CONSISTENCY.md`](OPENHANDS_RUNTIME_CONSISTENCY.md) for
the exact lock and the `dynamic_context` compatibility gate.

Official v0.4 runs use digest-pinned task images. The first 16 images contain
the same already-qualified repository environments; the four compiler images
contain a sanitized one-commit seed and frozen native toolchain. Native runs do
not require a local source dataset. See
[`TASK_IMAGE_DISTRIBUTION.md`](TASK_IMAGE_DISTRIBUTION.md).

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
uv run asyncodebench release-status --require preview
uv run asyncodebench tasks
uv run asyncodebench images list

uv run asyncodebench run \
  --task asyncodebench:cachetools \
  --protocol all \
  --model "$LLM_MODEL" \
  --dry-run
```

After preserving the desired run bundles, preview and remove only the official
task images and their matching OpenHands derived images with:

```bash
uv run asyncodebench images remove --all --dry-run
uv run asyncodebench images remove --all --yes
```

This cleanup does not delete `outputs/` or invoke a global Docker prune.

To dry-run all five protocols with the campaign wrapper:

```bash

ENV_FILE="$PWD/.env" \
MODEL_TAG=my-model \
RUN_VERSION=smoke-v01 \
DRY_RUN=1 \
scripts/run_asyncodebench_five_protocols_env.sh cachetools
```

For any of the four official TVM tasks, use the parallel five-protocol entry
point (the digest-pinned container backend is the default):

```bash
ENV_FILE="$PWD/.env.my-model" RUN_ID=tvm-five-v01 \
  scripts/run_pr_hard_five_protocols_env.sh apache-tvm-20153
```

The five dry-runs should report:

```text
task_id=asyncodebench:cachetools
protocol=single | serial_specialists | async_private | caid_manager | async_manager
official=True
curated_base_sha=<sha>
```

Dry-run does not call the model or start a task container.

`doctor` does make one small authenticated completion request with a forced
function call. This catches invalid API keys, unreachable endpoints, incorrect
model IDs, and missing tool-call support before a paid run. Use `doctor
--offline` only when checking installation without a configured endpoint.

## 4. Run One Task

```bash
ENV_FILE="$PWD/.env" \
MODEL_TAG=my-model \
RUN_VERSION=official-v01 \
WORKSPACE_PORT_STRATEGY=auto \
scripts/run_asyncodebench_five_protocols_env.sh cachetools
```

The wrapper runs the five protocols sequentially. It reads specialist counts
from the released scenario manifest and uses the official 100-response cap.
An interrupted output directory remains immutable evidence; retry with a new
`RUN_VERSION`.

To run one protocol only, use the corresponding flag:

```bash
RUN_SINGLE=0 \
RUN_SERIAL=0 \
RUN_ASYNC_PRIVATE=1 \
RUN_CAID=0 \
RUN_ASYNC_MANAGER=0 \
ENV_FILE="$PWD/.env" \
MODEL_TAG=my-model \
RUN_VERSION=async-private-v01 \
WORKSPACE_PORT_STRATEGY=auto \
scripts/run_asyncodebench_five_protocols_env.sh cachetools
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
scenario_manifest_snapshot.json
metrics_snapshot.json
quality_snapshot.json
execution_profile_snapshot.json
protocol.json
report.json
dependency_probe_checkpoints.jsonl
process_metrics_summary.json
run_bundle.json
cost.json
runtime.txt
patch.diff
```

`patch.diff` is optional for a valid run that produces no integrated patch.
Use `inspect-run` instead of `validate-run` when triaging a historical directory
that predates `run_bundle.json`:

```bash
uv run asyncodebench inspect-run \
  outputs/asyncodebench/v0.3/<model>/<task>/<protocol>/<run-version>
```

Validate any completed task-protocol run without calling the model again:

```bash
uv run asyncodebench validate-run \
  outputs/asyncodebench/v0.3/<model>/<task>/<protocol>/<run-version>
```

Coding failure is valid benchmark evidence. Provider, transport, parser,
workspace, or evaluator instrumentation failure invalidates the run. A valid
run enters the official aggregate only when its execution profile matches and
its required provenance is complete.
See [`RESULT_VALIDITY.md`](RESULT_VALIDITY.md) for the exact machine-checked
rules, and see
[`EVALUATION_METRICS.md`](EVALUATION_METRICS.md) for metric definitions and
[`MODEL_EXPERIMENT_RUNBOOK.md`](MODEL_EXPERIMENT_RUNBOOK.md) before running all
19 tasks.

The same command also runs one of the four compiler tasks; its immutable image
is pulled automatically when absent:

```bash
uv run asyncodebench run \
  --task asyncodebench:apache-tvm-20018 \
  --protocol all \
  --model "$LLM_MODEL"
```

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
