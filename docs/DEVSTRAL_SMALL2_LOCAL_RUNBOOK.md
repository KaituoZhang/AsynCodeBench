# Devstral Small 2 Local vLLM Runbook

This profile connects `mistralai/Devstral-Small-2-24B-Instruct-2512` to the
community-ready AsynCodeBench harness on one A100 80GB. It changes only model
serving and generation configuration; tasks, protocols, agent counts,
Dependency Checkers, scope rules, and evaluators remain benchmark-controlled.

The model publisher describes Devstral Small 2 as a 24B agentic coding model
with structured tool calling and a 256K maximum context. Its full-context vLLM
example uses tensor parallelism. This single-GPU candidate profile starts at a
65,536-token context so that model weights, KV cache, and up to four scheduler
sequences have usable memory headroom. Do not call it a validated profile until
the gates below pass on the target machine.

Official model sources:

- <https://huggingface.co/mistralai/Devstral-Small-2-24B-Instruct-2512>
- <https://huggingface.co/mistralai/Devstral-Small-2-24B-Instruct-2512/blob/main/README.md>

## Prepared Files

- Server wrapper: `reproductions/async-swe-agents/scripts/serve_devstral_small2_24b.sh`
- Public environment template:
  `reproductions/async-swe-agents/configs/model_profiles/devstral-small2-24b.env.example`
- Local ignored environment: `reproductions/async-swe-agents/.env.devstral-small2`

The default profile is:

```text
model=mistralai/Devstral-Small-2-24B-Instruct-2512
max_model_len=65536
max_output_tokens=8192
max_num_seqs=4
max_num_batched_tokens=32768
temperature=0.15
tool_call_parser=mistral
reasoning_parser=none
language_model_only=true
```

## 1. Start vLLM

Run this in the server terminal:

```bash
cd /home/kzhang42/AsyncCodeBench/reproductions/async-swe-agents

VLLM_BIN=/home/kzhang42/anaconda3/envs/vllm_qwen3_128k/bin/vllm \
scripts/serve_devstral_small2_24b.sh 0 8006 4
```

The arguments are `<gpu-id> <vllm-port> <max-seqs>`. The script verifies that
`mistral-common >= 1.8.6`, exposes the OpenAI-compatible API on all host
interfaces, and enables vLLM's `mistral` automatic tool-call parser. Devstral
Small 2 does not use Qwen/Gemma thinking or reasoning parser settings.

Although the checkpoint includes a Pixtral vision tower, AsynCodeBench sends
only text and tool calls. The wrapper uses vLLM's `--language-model-only` mode
to disable image inputs and multimodal profiling. This prevents the unused
Pixtral processor from affecting startup, memory use, or benchmark execution.

The existing `vllm_qwen3_128k` environment resolves part of its dependency set
from the user's Python site directory. The wrapper therefore preserves the
environment's normal Python import behavior. Do not launch it with
`PYTHONNOUSERSITE=1` unless all packages reported by `python -m pip check` have
first been installed directly into that Conda environment.

If startup runs out of memory, stop there. Do not silently alter settings in the
middle of a campaign. First retry the smoke profile with
`DEVSTRAL_MAX_MODEL_LEN=49152`; once a profile passes, freeze it across the four
protocols and record the changed value in the model environment and run ID.

## 2. Preflight

Run this in a separate benchmark terminal after vLLM is ready:

```bash
cd /home/kzhang42/AsyncCodeBench/reproductions/async-swe-agents

export ENV_FILE="$PWD/.env.devstral-small2"
source scripts/env.sh

curl -fsS "$LLM_BASE_URL/models"
docker run --rm --network host curlimages/curl:8.10.1 \
  -fsS http://127.0.0.1:8006/v1/models
uv run asyncodebench doctor --timeout 180
```

All three checks must pass. In particular, `doctor` must receive the forced
healthcheck tool call. A successful `/models` response alone is insufficient.

## 3. Dry-run

```bash
ENV_FILE="$PWD/.env.devstral-small2" \
MODEL_TAG=devstral-small2-24b \
RUN_VERSION=dryrun-65k-seq4-v01 \
DRY_RUN=1 \
scripts/run_asyncodebench_all_protocols_env.sh cachetools
```

Confirm all four public protocols, official task identity, scenario-declared
agent counts, curated source SHA, and matching execution profile.

## 4. Real Smoke

```bash
ENV_FILE="$PWD/.env.devstral-small2" \
MODEL_TAG=devstral-small2-24b \
RUN_VERSION=smoke-65k-o8192-seq4-v01 \
WORKSPACE_PORT_STRATEGY=auto \
SINGLE_ITERATIONS=2 \
SPECIALIST_ITERATIONS=2 \
CAID_MANAGER_ITERATIONS=2 \
CAID_SUB_ITERATIONS=2 \
ROUNDS_OF_CHAT=1 \
scripts/run_asyncodebench_all_protocols_env.sh cachetools
```

This smoke is not an official score. It passes when every protocol has real
model-execution evidence and produces a valid evaluator, Dependency Checker
trace, process metrics, and `run_bundle.json` without provider, parser,
transport, context, or instrumentation errors.

Validate it:

```bash
for protocol in single serial_specialists async_private caid_manager; do
  uv run asyncodebench validate-run \
    "outputs/asyncodebench/v0.3/devstral-small2-24b/cachetools/$protocol/smoke-65k-o8192-seq4-v01" || true
done
```

The smoke intentionally deviates from the official 100-response profile, so it
must not enter the official aggregate.

## 5. Official Cachetools Run

Only after the smoke is operationally clean:

```bash
ENV_FILE="$PWD/.env.devstral-small2" \
MODEL_TAG=devstral-small2-24b \
RUN_VERSION=standard100-65k-o8192-seq4-v01 \
WORKSPACE_PORT_STRATEGY=auto \
scripts/run_asyncodebench_all_protocols_env.sh cachetools
```

The wrapper runs `single`, `serial_specialists`, `async_private`, and
`caid_manager` sequentially with the official 100-response cap and manifest
agent count. Never reuse an interrupted output directory; use a new run version
only for an infrastructure-invalid retry.

## 6. What Must Remain Fixed

For a reportable campaign, keep the model revision, vLLM version, context and
output limits, temperature, tool parser, sequence capacity, OpenHands adapter,
and benchmark revision fixed across the four protocols. A valid coding failure
is benchmark evidence and must not be rerun to select a better trajectory.

## 7. Three-Port Official Campaign

The prepared local files `.env.devstral-small2-8007`,
`.env.devstral-small2-8008`, and `.env.devstral-small2-8009` bind each benchmark
queue to exactly one vLLM endpoint. They are intentionally ignored by Git.
Start three servers on GPUs 1, 2, and 3, respectively:

```bash
cd /home/kzhang42/AsyncCodeBench/reproductions/async-swe-agents
VLLM_BIN=/home/kzhang42/anaconda3/envs/vllm_qwen3_128k/bin/vllm scripts/serve_devstral_small2_24b.sh 1 8007 4
```

```bash
cd /home/kzhang42/AsyncCodeBench/reproductions/async-swe-agents
VLLM_BIN=/home/kzhang42/anaconda3/envs/vllm_qwen3_128k/bin/vllm scripts/serve_devstral_small2_24b.sh 2 8008 4
```

```bash
cd /home/kzhang42/AsyncCodeBench/reproductions/async-swe-agents
VLLM_BIN=/home/kzhang42/anaconda3/envs/vllm_qwen3_128k/bin/vllm scripts/serve_devstral_small2_24b.sh 3 8009 4
```

After all three `/models` endpoints and `asyncodebench doctor` checks pass,
run these queues concurrently in three additional terminals:

| vLLM port | Workspace scan range | Tasks |
| --- | --- | --- |
| 8007 | 20000-29999 | cachetools, wcwidth, requests, simpy, marshmallow, flask |
| 8008 | 30000-39999 | deprecated, tinydb, parsel, graphene, pexpect |
| 8009 | 40000-49999 | portalocker, filesystem_spec, imapclient, python-rsa, cookiecutter |

Each queue must use `WORKSPACE_PORT_STRATEGY=auto` and its assigned scan range.
The commands record failures and continue to the next task. Do not retry a
valid model failure; use a new `RUN_VERSION` only for an invalid infrastructure
run.

Use this queue template in each benchmark terminal, replacing the three values
shown in the comments with that terminal's environment file, scan range, and
task list:

```bash
cd /home/kzhang42/AsyncCodeBench/reproductions/async-swe-agents

export ENV_FILE="$PWD/.env.devstral-small2-8007"  # change per terminal
source scripts/env.sh

# Do not start the first task until the model server is actually ready.
endpoint_ready=0
for attempt in $(seq 1 120); do
  if curl -fsS --max-time 10 "$LLM_BASE_URL/models" >/dev/null; then
    endpoint_ready=1
    break
  fi
  echo "Waiting for $LLM_BASE_URL ($attempt/120)..."
  sleep 10
done
if [[ "$endpoint_ready" != "1" ]]; then
  echo "Model endpoint did not become ready: $LLM_BASE_URL" >&2
  exit 1
fi
if ! docker run --rm --network host curlimages/curl:8.10.1 \
     -fsS --max-time 10 "$LLM_BASE_URL/models" >/dev/null; then
  echo "Docker cannot reach model endpoint: $LLM_BASE_URL" >&2
  exit 1
fi
if ! uv run asyncodebench doctor --timeout 180; then
  echo "AsynCodeBench model/tool-calling preflight failed" >&2
  exit 1
fi

MODEL_TAG=devstral-small2-24b
RUN_VERSION=standard100-65k-o8192-seq4-v01
WORKSPACE_PORT_SCAN_START=20000  # change per terminal
WORKSPACE_PORT_SCAN_END=29999    # change per terminal
TASKS=(cachetools wcwidth requests simpy marshmallow flask)  # change per terminal
LAUNCH_LOG_DIR="outputs/asyncodebench/v0.3/${MODEL_TAG}/launcher_logs"
mkdir -p "$LAUNCH_LOG_DIR"

failed=()
for task in "${TASKS[@]}"; do
  echo "Running asyncodebench:${task} through ${LLM_BASE_URL}"
  launch_log="${LAUNCH_LOG_DIR}/${task}-${RUN_VERSION}.log"
  if ! ENV_FILE="$ENV_FILE" \
       MODEL_TAG="$MODEL_TAG" \
       RUN_VERSION="$RUN_VERSION" \
       WORKSPACE_PORT_STRATEGY=auto \
       WORKSPACE_PORT_SCAN_START="$WORKSPACE_PORT_SCAN_START" \
       WORKSPACE_PORT_SCAN_END="$WORKSPACE_PORT_SCAN_END" \
       scripts/run_asyncodebench_all_protocols_env.sh "asyncodebench:${task}" \
       > >(tee -a "$launch_log") 2>&1; then
    failed+=("$task")
  fi
done

printf 'Failed tasks:'
printf ' %s' "${failed[@]}"
printf '\n'
```
