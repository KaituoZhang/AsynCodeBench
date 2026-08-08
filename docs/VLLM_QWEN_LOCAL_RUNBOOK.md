# Local vLLM Qwen Runbook

This document records the working procedure for running AsynCodeBench with a
local Qwen model served by vLLM. It is based on the `Qwen/Qwen3.6-27B` setup on
port `8006`, but the same pattern applies to other OpenAI-compatible local
vLLM servers.

Use this together with:

- `docs/LOCAL_VLLM_EXPERIMENT_RUNBOOK.md` for the authoritative local-serving
  checklist, concurrency requirements, and four-protocol template.
- `docs/MODEL_EXPERIMENT_RUNBOOK.md` for the full 16-task experiment flow.
- `docs/EVALUATION_METRICS.md` for post-run metric computation.
- `reproductions/async-swe-agents/scripts/env.sh` for loading model env files.

## Why This Needs A Separate Runbook

Running GPT-style remote APIs is simpler because the agent runner can reach the
provider endpoint from both the host process and the Docker workspace. A local
vLLM server adds two extra failure modes:

1. LiteLLM must know the provider namespace. Local OpenAI-compatible models
   should usually be configured as `openai/<served-model-name>`.
2. The real agent conversation may run through an OpenHands Docker workspace.
   `127.0.0.1` inside that workspace is the container itself, not necessarily
   the host vLLM server.

In this project, the reliable solution is to run the AsynCodeBench Docker
workspace with host networking and keep vLLM reachable at
`http://127.0.0.1:8006/v1`.

## Environment File

Create a model-specific env file:

```bash
cd /absolute/path/to/AsynCodeBench/reproductions/async-swe-agents
cp .env.example .env.qwen36-27
```

Recommended contents:

```bash
LLM_BASE_URL=http://127.0.0.1:8006/v1
LLM_API_KEY=local-dummy-key
LLM_MODEL=openai/Qwen/Qwen3.6-27B
LLM_SUBAGENT_MODEL=openai/Qwen/Qwen3.6-27B

# Qwen thinking mode through vLLM chat_template_kwargs.
LLM_EXTRA_BODY_JSON='{"chat_template_kwargs":{"enable_thinking":true}}'

# For official runs, prefer a larger vLLM context and keep this stable.
LLM_MAX_OUTPUT_TOKENS=32768
LLM_TEMPERATURE=0.6
LLM_TOP_P=0.95
LLM_TOP_K=20
LLM_TIMEOUT=7200
LLM_NUM_RETRIES=2

# OpenHands remote-conversation status polling. Long local generations can
# exceed the legacy SDK's 30-second per-request timeout.
ASYNCODEBENCH_CONVERSATION_RUN_TIMEOUT=43200
ASYNCODEBENCH_REMOTE_TRIGGER_TIMEOUT=30
ASYNCODEBENCH_REMOTE_POLL_TIMEOUT=3600
ASYNCODEBENCH_REMOTE_POLL_INTERVAL=5

COMMIT0_DATASET_PATH=/absolute/path/to/AsynCodeBench/reproductions/async-swe-agents/data/commit0/commit0_combined
SDK_SOURCE_DIR=/absolute/path/to/AsynCodeBench/reproductions/software-agent-sdk
```

Load it before running experiments:

```bash
cd /absolute/path/to/AsynCodeBench/reproductions/async-swe-agents
export ENV_FILE="$PWD/.env.qwen36-27"
source scripts/env.sh

unset ASYNCODEBENCH_DISABLE_CURATED_TASK_SOURCE
unset ASYNCODEBENCH_DISABLE_CURATED_TASK_CONFIG
unset ASYNCODEBENCH_DISABLE_MANIFEST_EVALUATOR
```

Important details:

- `LLM_MODEL` must include the LiteLLM provider prefix:
  `openai/Qwen/Qwen3.6-27B`.
- `LLM_BASE_URL` should stay as `http://127.0.0.1:8006/v1` when the workspace
  is launched with host networking.
- `LLM_API_KEY` can be a dummy value for local vLLM, but it must be non-empty.
- `LLM_EXTRA_BODY_JSON` must be valid JSON. Use double quotes inside the JSON
  and quote the whole value in the shell env file.

## vLLM Launch Command

For a single A100 80G allocation, use exactly one visible GPU and do not add
`--data-parallel-size` or `--tensor-parallel-size`. Keep at least two sequence
slots so local serving does not serialize every asynchronous subagent request.
The following is the tested long-context profile when only GPU 1 is available.

```bash
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
TRANSFORMERS_NO_TF=1 USE_TF=0 CUDA_VISIBLE_DEVICES=1 \
/home/kzhang42/anaconda3/envs/vllm_qwen3_128k/bin/vllm serve Qwen/Qwen3.6-27B \
  --served-model-name Qwen/Qwen3.6-27B \
  --trust-remote-code \
  --host 0.0.0.0 \
  --max-model-len 131000 \
  --gpu-memory-utilization 0.90 \
  --max-num-seqs 2 \
  --max-num-batched-tokens 32768 \
  --port 8006 \
  --reasoning-parser deepseek_r1 \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_xml
```

If this profile OOMs on a single GPU, reduce context and batched tokens while
keeping the formal async minimum of two sequence slots:

```bash
--max-model-len 81920
--max-num-seqs 2
--max-num-batched-tokens 32768
```

For a 2 x A100 80G data-parallel allocation, each GPU hosts a full replica.
Use this only when both GPUs are explicitly allocated for the run.

```bash
TRANSFORMERS_NO_TF=1 USE_TF=0 CUDA_VISIBLE_DEVICES=0,1 \
/home/kzhang42/anaconda3/envs/vllm_qwen3_128k/bin/vllm serve Qwen/Qwen3.6-27B \
  --served-model-name Qwen/Qwen3.6-27B \
  --trust-remote-code \
  --host 0.0.0.0 \
  --max-model-len 65536 \
  --gpu-memory-utilization 0.95 \
  --max-num-seqs 8 \
  --max-num-batched-tokens 65536 \
  --port 8006 \
  --reasoning-parser deepseek_r1 \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_xml \
  --data-parallel-size 2 \
  --data-parallel-size-local 2 \
  --data-parallel-backend mp
```

Notes:

- vLLM `0.19.1` supports `--reasoning-parser`, but does not accept
  `--enable-reasoning`. If the server says `unrecognized arguments:
  --enable-reasoning`, remove that flag.
- Single-GPU runs should not set data parallel or tensor parallel flags.
- `--max-num-seqs 2` is the minimum formal local-async profile. A value of one
  is useful only for connectivity diagnostics because it serializes vLLM
  scheduling across concurrent subagent requests.
- `--enable-auto-tool-choice` is required because OpenHands sends
  `tool_choice="auto"`.
- `--tool-call-parser qwen3_xml` is recommended for this Qwen3-family setup.
  `hermes` can accept the request but may fail with JSON parsing errors because
  it expects a different `<tool_call>{...json...}</tool_call>` format.
- If 64K context causes OOM, lower `--max-model-len` to `32768`. If 64K works,
  keep it fixed for all Qwen runs for comparability.

## Host And Docker Networking

There are two different network perspectives:

| Location | `127.0.0.1` means | What should work |
| --- | --- | --- |
| Host shell | The server machine | `curl http://127.0.0.1:8006/v1/models` |
| Docker workspace with bridge network | The container itself | Usually cannot reach host vLLM through `127.0.0.1` |
| Docker workspace with host network | The server machine | Can reach host vLLM through `127.0.0.1` |

The confusing case is the Docker bridge gateway. On this server,
`docker network inspect bridge` returned `192.168.1.1`, and the host shell could
query `http://192.168.1.1:8006/v1/models`, but a container-side curl timed out.
Therefore do not rely on the bridge gateway unless this test succeeds:

```bash
docker run --rm curlimages/curl:8.10.1 \
  -Ssv --connect-timeout 5 \
  http://192.168.1.1:8006/v1/models
```

For this project, use host networking for the AsynCodeBench workspace:

```bash
ASYNCODEBENCH_WORKSPACE_DOCKER_NETWORK=host
ASYNCODEBENCH_WORKSPACE_HOST_PORT=8000
```

With host networking:

- Keep `LLM_BASE_URL=http://127.0.0.1:8006/v1`.
- Do not run multiple host-network workspace containers in parallel with the
  same `ASYNCODEBENCH_WORKSPACE_HOST_PORT`; they will conflict.
- If you need parallel runs, use separate ports or run tasks sequentially.

## Smoke Tests

First confirm the host can see vLLM:

```bash
curl -s "$LLM_BASE_URL/models"
```

Then confirm LiteLLM can call the model with thinking enabled:

```bash
uv run python - <<'PY'
import os, json
from litellm import completion

resp = completion(
    model=os.environ["LLM_MODEL"],
    api_base=os.environ["LLM_BASE_URL"],
    api_key=os.environ["LLM_API_KEY"],
    messages=[{"role": "user", "content": "Think briefly, then output exactly: OK"}],
    extra_body=json.loads(os.environ.get("LLM_EXTRA_BODY_JSON") or "{}"),
    max_completion_tokens=4096,
    temperature=0.6,
    top_p=0.95,
    top_k=20,
)
msg = resp.choices[0].message
print("content:", repr(msg.content))
print("reasoning_content exists:", bool(getattr(msg, "reasoning_content", None)))
print("finish_reason:", resp.choices[0].finish_reason)
PY
```

Expected:

```text
content: '\n\nOK'
reasoning_content exists: True
finish_reason: stop
```

Then confirm vLLM accepts OpenAI-style tool calls:

```bash
uv run python - <<'PY'
import os, json
from litellm import completion

resp = completion(
    model=os.environ["LLM_MODEL"],
    api_base=os.environ["LLM_BASE_URL"],
    api_key=os.environ["LLM_API_KEY"],
    messages=[{"role": "user", "content": "Use the tool to echo hello."}],
    tools=[{
        "type": "function",
        "function": {
            "name": "echo",
            "description": "Echo a string.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    }],
    tool_choice="auto",
    extra_body=json.loads(os.environ.get("LLM_EXTRA_BODY_JSON") or "{}"),
    max_completion_tokens=1024,
    temperature=0.6,
    top_p=0.95,
    top_k=20,
)
msg = resp.choices[0].message
print("content:", repr(msg.content))
print("reasoning_content exists:", bool(getattr(msg, "reasoning_content", None)))
print("tool_calls:", msg.tool_calls)
print("finish_reason:", resp.choices[0].finish_reason)
PY
```

This smoke test should not raise:

```text
"auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser
```

It also should not emit a `hermes_tool_parser.py` JSON decode error if the
server uses `--tool-call-parser qwen3_xml`.

## Cachetools Single-Agent Test

After the smoke tests pass, run one real AsynCodeBench task:

```bash
cd /absolute/path/to/AsynCodeBench/reproductions/async-swe-agents
export ENV_FILE="$PWD/.env.qwen36-27"
source scripts/env.sh

TASK=cachetools
MODEL_TAG=qwen36-27
RUN_VERSION=curated_thinking_v08

MODEL_TAG="$MODEL_TAG" \
RUN_VERSION="$RUN_VERSION" \
SINGLE_ITERATIONS=30 \
RUN_SERIAL=0 \
RUN_ASYNC_PRIVATE=0 \
RUN_CAID=0 \
WORKSPACE_PORT_STRATEGY=auto \
scripts/run_asyncodebench_all_protocols_env.sh "$TASK"
```

A valid real run should show:

- vLLM server logs receiving `/v1/chat/completions` requests.
- `Iterations used` greater than zero.
- `report.json`, `cost.json`, `runtime.txt`, and
  `dependency_probe_checkpoints.jsonl` in the output directory.
- No `ConversationErrorEvent` caused by connection, tool-choice, parser, or
  context-window errors.

The local model cost may show as zero or produce a LiteLLM price-map warning.
That is expected for an unmapped local model; use token counts and runtime for
resource reporting.

## Cachetools GPU1 Result Snapshot

An earlier `Qwen/Qwen3.6-27B` 65K single-GPU profile was run on `cachetools`
with the following historical configuration:

```text
RUN_VERSION=curated_thinking_gpu1_65k_o4096_v01
LLM_MAX_OUTPUT_TOKENS=4096
MAX_SUBAGENTS=2
```

Summary:

| Protocol | Final tests | Final success | ADPR | Resolved deps | FSAR | IFR |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| single | 199/215 | no | 0.20 | 1/5 | 0.00 | 0.00 |
| serial_specialists | 215/215 | yes | 1.00 | 5/5 | 0.00 | 0.00 |
| async_private | 198/215 | no | 0.20 | 1/5 | 0.50 | 1.00 |
| CAID_multi | 210/215 | no | 0.80 | 4/5 | 0.67 | 1.00 |

Interpretation:

- `serial_specialists` is the only fully successful cachetools protocol under
  this single-GPU Qwen3.6 run.
- `CAID_multi` improves dependency resolution over `async_private` but leaves
  one final integrated dependency unresolved.
- Runtime from this single-GPU profile should not be compared directly with
  earlier two-GPU data-parallel runs.

## Common Errors And Fixes

### Missing scipy.optimize During vLLM Startup

Error:

```text
ModuleNotFoundError: No module named 'scipy.optimize'
```

On the reference server, Python found an incomplete user-site namespace at
`~/.local/lib/python3.10/site-packages/scipy`, while the vLLM conda environment
did not contain a complete SciPy installation. Install SciPy into the actual
vLLM environment:

```bash
/home/kzhang42/anaconda3/envs/vllm_qwen3_128k/bin/pip install --no-deps \
  'scipy>=1.14,<1.16'
```

Verify the exact interpreter before starting vLLM:

```bash
/home/kzhang42/anaconda3/envs/vllm_qwen3_128k/bin/python -c \
  'import scipy, scipy.optimize; print(scipy.__version__, scipy.__file__)'
```

The current legacy `vllm_qwen3_128k` environment also reads several HTTP and
async packages from `~/.local`, including `aiohttp`, `httpx`, and `httpcore`.
Therefore do not set `PYTHONNOUSERSITE=1` for this environment unless its full
dependency set has first been rebuilt inside conda. Isolating only part of the
environment changes a previously working launch into a sequence of missing
module errors.

### LiteLLM Provider Missing

Error:

```text
LLM Provider NOT provided. You passed model=qwen3.6-27
```

Fix:

```bash
LLM_MODEL=openai/Qwen/Qwen3.6-27B
LLM_SUBAGENT_MODEL=openai/Qwen/Qwen3.6-27B
```

### vLLM Gets No Requests During Agent Run

Symptom:

- Direct host-side LiteLLM smoke test works.
- Full agent run fails with connection errors.
- vLLM logs show no `/v1/chat/completions` request.

Cause:

The agent conversation is going through a Docker workspace that cannot reach
the host vLLM endpoint through the configured URL.

Fix:

```bash
ASYNCODEBENCH_WORKSPACE_DOCKER_NETWORK=host \
ASYNCODEBENCH_WORKSPACE_HOST_PORT=8000 \
...
```

and keep:

```bash
LLM_BASE_URL=http://127.0.0.1:8006/v1
```

### Auto Tool Choice Rejected

Error:

```text
"auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser to be set
```

Fix:

Restart vLLM with:

```bash
--enable-auto-tool-choice \
--tool-call-parser qwen3_xml
```

### Hermes Parser JSON Decode Error

Error in vLLM log:

```text
hermes_tool_parser.py
json.decoder.JSONDecodeError
```

Cause:

`hermes` expects a JSON tool-call body, but Qwen3-family output may use XML
tool-call syntax.

Fix:

Restart vLLM with:

```bash
--tool-call-parser qwen3_xml
```

### Context Window Exceeded

Error:

```text
maximum context length is 16384 tokens
requested 4096 output tokens
prompt contains at least 12289 input tokens
```

Cause:

The 16K context is too small for OpenHands agent prompts plus a thinking-model
completion budget.

Fix for official runs:

```bash
--max-model-len 131000
LLM_MAX_OUTPUT_TOKENS=32768
```

Qwen's official thinking-mode examples use a `32768` generation budget. A
smaller value may be used for connectivity smoke tests, but not for formal
agent results. In particular, a run is harness-truncated when repeated
responses finish at the configured output limit with both assistant `content`
and `tool_calls` empty.

Temporary connectivity-only smoke-test fallback:

```bash
LLM_MAX_OUTPUT_TOKENS=2048
```

Do not treat the 2048-token setting as the preferred official configuration for
coding-agent comparisons; it can truncate reasoning or tool-use decisions.

### Thinking Exhausts The Output Budget

Symptoms:

```text
LLM response contained no tool call and no content - sending corrective feedback
```

and the remote conversation statistics repeatedly report exactly the configured
completion limit, for example `completion_tokens=4096`.

Cause:

The reasoning parser correctly separates `reasoning_content`, but the model
uses the entire completion budget before reaching `</think>` and the subsequent
tool call. OpenHands receives neither an actionable tool call nor visible final
content, sends corrective feedback, and can repeat the same truncated cycle.

Fix:

```bash
export LLM_MAX_OUTPUT_TOKENS=32768
```

Use a fresh output directory after changing this setting. A run that already
entered the repeated empty-response loop is not suitable for the formal
aggregate.

### Repeated Remote-Conversation Poll Timeouts

Symptom:

```text
Request failed: timed out
Error polling status (will retry): timed out
```

This can occur even while vLLM is still generating normally. The host runner's
legacy OpenHands client used a fixed 30-second timeout for each conversation
status request. Long Qwen reasoning or tool turns can keep the remote
conversation endpoint busy longer than that interval.

The AsynCodeBench runner installs a per-conversation compatibility shim in
`reproductions/async-swe-agents/core/subagent.py`. Configure it before local
Qwen runs:

```bash
export ASYNCODEBENCH_CONVERSATION_RUN_TIMEOUT=43200
export ASYNCODEBENCH_REMOTE_TRIGGER_TIMEOUT=30
export ASYNCODEBENCH_REMOTE_POLL_TIMEOUT=3600
export ASYNCODEBENCH_REMOTE_POLL_INTERVAL=5
```

These variables have separate meanings:

- `ASYNCODEBENCH_CONVERSATION_RUN_TIMEOUT` is the maximum duration of the
  complete agent conversation.
- `ASYNCODEBENCH_REMOTE_TRIGGER_TIMEOUT` bounds only the initial `/run`
  acknowledgement. If the acknowledgement is delayed, the runner follows the
  same conversation ID without submitting duplicate work.
- `ASYNCODEBENCH_REMOTE_POLL_TIMEOUT` is the timeout for one remote status
  request. It must be long enough for a slow local generation.
- `ASYNCODEBENCH_REMOTE_POLL_INTERVAL` controls how often the host checks for
  terminal conversation state.

A healthy run logs a line similar to:

```text
Configured remote status polling: interval=5.0s, request_timeout=900.0s
```

Do not classify a run as failed merely because it is quiet for more than 30
seconds. Confirm whether vLLM is processing a request and whether the run log is
advancing. Repeated poll timeout warnings after this configuration indicate an
instrumentation or network problem and should exclude that run from the formal
aggregate.

### Invalid JSON In LLM_EXTRA_BODY_JSON

Error:

```text
LLM_EXTRA_BODY_JSON must be valid JSON
```

Fix:

Use valid JSON and quote the whole shell value:

```bash
LLM_EXTRA_BODY_JSON='{"chat_template_kwargs":{"enable_thinking":true}}'
```

### Server Rejects --enable-reasoning

Error:

```text
vllm: error: unrecognized arguments: --enable-reasoning
```

Fix:

For vLLM `0.19.1`, remove `--enable-reasoning` and keep:

```bash
--reasoning-parser deepseek_r1
```

## Validity Notes

Runs that fail before the agent begins real iterations are harness failures, not
model results. Do not include runs with these failures in official aggregates:

- provider namespace missing;
- Docker workspace cannot reach vLLM;
- vLLM rejects `tool_choice="auto"`;
- parser mismatch prevents tool calls;
- context-window failure at the beginning of the task.

For Qwen3-family official runs, keep the following stable across tasks:

- same vLLM server command;
- same `LLM_MAX_OUTPUT_TOKENS`;
- same thinking setting;
- same Docker workspace networking mode;
- same AsynCodeBench curated task source and manifest evaluator.
