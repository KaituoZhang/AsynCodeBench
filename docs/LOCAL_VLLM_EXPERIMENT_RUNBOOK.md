# Local vLLM Experiment Runbook

This is the main operational guide for running AsynCodeBench against a local
OpenAI-compatible vLLM server. It is intended for collaborators, fresh agent
sessions, and public reproduction. Use it together with:

- `docs/MODEL_EXPERIMENT_RUNBOOK.md` for the official tasks and evaluation flow.
- `docs/VLLM_QWEN_LOCAL_RUNBOOK.md` for the tested Qwen3.6-27B configuration and
  model-specific failure history.
- `docs/EVALUATION_METRICS.md` for ADPR, DRS, CAIL, FSAR, IFR, and aggregation.

Local inference is not a drop-in replacement for a remote API. A valid local
run requires a compatible model endpoint, enough vLLM scheduling capacity,
working tool-call and reasoning parsers, Docker-to-host connectivity, and
timeouts that tolerate long coding-agent turns.

## Non-negotiable Settings

Before a formal local-model run, verify all of the following:

1. `LLM_MODEL` includes a LiteLLM provider prefix, normally
   `openai/<served-model-name>` for vLLM's OpenAI-compatible endpoint.
2. The model supports chat and structured tool calling with the selected chat
   template and tool parser.
3. Thinking mode is configured explicitly and held constant across all tasks.
4. `--max-num-seqs` is at least `2` for AsynCodeBench multi-agent runs.
5. The Docker workspace can reach the vLLM endpoint, not just the host shell.
6. The same vLLM command and runner environment are used for all four protocols.
7. Runs are executed sequentially unless parallel task execution is an explicit
   serving-capacity experiment.
8. A failed or interrupted output directory is never reused.

`--max-num-seqs 1` is acceptable for a connectivity diagnostic, but not for the
main asynchronous protocol comparison. vLLM defines this option as the maximum
number of sequences processed in one scheduler iteration. `async_private` and
`CAID_multi` can issue multiple concurrent LLM requests; a capacity of one
serializes them at the inference server and can distort overlap, latency, and
timeout behavior. Use `2` as the minimum. If GPU memory permits, a value matching
the largest intended concurrent subagent count can be reported as a separate
serving profile.

## Runtime Architecture

The local path has three processes and two ports:

```text
host runner
  |
  | creates and polls
  v
OpenHands Docker workspace (host port 8000 by default)
  |
  | OpenAI-compatible chat/tool requests
  v
host vLLM server (port 8006 in the tested setup)
```

These ports have different roles:

- `8006`: the vLLM OpenAI-compatible API.
- `8000`: the OpenHands workspace service used by the host runner.

The agent's LLM request can originate from the Docker workspace. Therefore a
successful host-side `curl http://127.0.0.1:8006/v1/models` does not prove that
the full agent can reach vLLM.

On the tested Linux server, the reliable configuration is:

```bash
ASYNCODEBENCH_WORKSPACE_DOCKER_NETWORK=host
ASYNCODEBENCH_WORKSPACE_HOST_PORT=8000
LLM_BASE_URL=http://127.0.0.1:8006/v1
```

With host networking, the workspace and host share the network namespace, so
`127.0.0.1:8006` reaches the host vLLM process. This Linux setup is different
from Docker Desktop on macOS or Windows, where `host.docker.internal` may be
needed and must be tested separately.

## Record The Serving Environment

vLLM flags and parser names change across versions. Record the environment
before choosing a command:

```bash
VLLM_BIN=/path/to/vllm-environment/bin/vllm

"$VLLM_BIN" --version
"$VLLM_BIN" serve --help=all | rg \
  'max-num-seqs|max-num-batched-tokens|reasoning-parser|tool-call-parser|enable-auto-tool-choice'
nvidia-smi
```

For each model result, preserve at least:

- model checkpoint and revision;
- vLLM, Transformers, CUDA, and PyTorch versions;
- GPU model and count;
- tensor/data parallel settings;
- context length, output-token limit, `max-num-seqs`, and batched-token limit;
- reasoning parser, tool-call parser, and thinking-mode setting;
- Docker network mode and workspace port.

Do not compare runtime directly between a paid API and a local GPU endpoint, or
between different local hardware profiles. Accuracy and dependency metrics can
be compared, while runtime should be reported with its serving configuration.
Unmapped local models normally report `$0` cost; report tokens and GPU-hours
instead of interpreting that value as free computation.

## Tested Qwen3.6-27B Server Profile

The following single-GPU command is the profile that successfully served
`Qwen/Qwen3.6-27B` on one A100 80GB in this project. It keeps two sequence slots
so an asynchronous run is not reduced to single-request scheduling.

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

This is a tested project configuration, not a universal Qwen command. The
installed vLLM accepted `--reasoning-parser deepseek_r1` but rejected
`--enable-reasoning`; newer vLLM versions may require or support different
reasoning flags. The tested `qwen3_xml` tool parser was selected after the
`hermes` parser produced malformed-tool JSON errors in this environment.
Always inspect the installed version's help and run the tool smoke test below.

Qwen's published vLLM guidance uses explicit thinking configuration, structured
reasoning parsing, and automatic tool calling. For Qwen3 thinking mode it also
recommends non-greedy sampling; the project uses temperature `0.6`, top-p
`0.95`, top-k `20`, and an output budget of `32768`.

If the server cannot initialize, use this reduction order:

1. Confirm no stale process is holding GPU memory.
2. Reduce `--max-model-len`, for example from `131000` to `81920` or `65536`.
3. Reduce `--max-num-batched-tokens`, while keeping chunked-prefill constraints
   for the installed vLLM version in mind.
4. Keep `--max-num-seqs 2` for the formal async experiment. If two sequences
   still do not fit, label the hardware profile insufficient rather than
   silently changing the benchmark's serving concurrency.

`--max-num-batched-tokens` is a per-scheduler-iteration token budget. It is not
the same as `LLM_MAX_OUTPUT_TOKENS`, which caps one model completion.

### Two-GPU Choices

Use data parallelism when the model fits on one GPU and the goal is additional
request throughput. Each GPU holds a full model replica. A single active request
may use only one GPU, so seeing one busy GPU during a single-agent turn is
expected; concurrent requests are needed to exercise both replicas.

```bash
CUDA_VISIBLE_DEVICES=0,1 "$VLLM_BIN" serve "$MODEL_PATH" \
  ... \
  --max-num-seqs 2 \
  --data-parallel-size 2 \
  --data-parallel-size-local 2 \
  --data-parallel-backend mp
```

Use tensor parallelism when the model must be sharded or when that exact model
and vLLM version have been validated under tensor parallel execution. Every
request then uses both GPUs. Do not switch between data and tensor parallelism
within one reported model experiment because it changes the serving profile.

## Model-specific Environment File

Create an untracked env file under the runner directory:

```bash
cd /absolute/path/to/AsynCodeBench/reproductions/async-swe-agents
cp .env.example .env.local-model
```

Example for the tested Qwen endpoint:

```bash
LLM_BASE_URL=http://127.0.0.1:8006/v1
LLM_API_KEY=local-dummy-key
LLM_MODEL=openai/Qwen/Qwen3.6-27B
LLM_SUBAGENT_MODEL=openai/Qwen/Qwen3.6-27B

LLM_EXTRA_BODY_JSON='{"chat_template_kwargs":{"enable_thinking":true}}'
LLM_MAX_INPUT_TOKENS=131000
LLM_MAX_OUTPUT_TOKENS=32768
LLM_TEMPERATURE=0.6
LLM_TOP_P=0.95
LLM_TOP_K=20
LLM_TIMEOUT=7200
LLM_NUM_RETRIES=2

ASYNCODEBENCH_CONVERSATION_RUN_TIMEOUT=43200
ASYNCODEBENCH_REMOTE_TRIGGER_TIMEOUT=30
ASYNCODEBENCH_REMOTE_POLL_TIMEOUT=3600
ASYNCODEBENCH_REMOTE_POLL_INTERVAL=5

ASYNCODEBENCH_WORKSPACE_DOCKER_NETWORK=host
ASYNCODEBENCH_WORKSPACE_HOST_PORT=8000

COMMIT0_DATASET_PATH=/absolute/path/to/AsynCodeBench/reproductions/async-swe-agents/data/commit0/commit0_combined
SDK_SOURCE_DIR=/absolute/path/to/AsynCodeBench/reproductions/software-agent-sdk
```

Important rules:

- The vLLM `--served-model-name` must match the name after `openai/` in
  `LLM_MODEL`.
- A local dummy API key must still be non-empty because the runner validates it.
- `LLM_EXTRA_BODY_JSON` must be valid JSON, quoted as one shell value.
- For local vLLM, `LLM_MAX_INPUT_TOKENS` must equal the server's
  `--max-model-len`. Choose `LLM_MAX_OUTPUT_TOKENS` separately so their sum
  still leaves enough room for the observed prompt history.
- Do not commit `.env*` files containing credentials or private endpoints.
- Do not set any `ASYNCODEBENCH_DISABLE_CURATED_*` variable for formal runs.

Load and verify the environment:

```bash
cd /absolute/path/to/AsynCodeBench/reproductions/async-swe-agents
export ENV_FILE="$PWD/.env.local-model"
source scripts/env.sh

unset ASYNCODEBENCH_DISABLE_CURATED_TASK_SOURCE
unset ASYNCODEBENCH_DISABLE_CURATED_TASK_CONFIG
unset ASYNCODEBENCH_DISABLE_MANIFEST_EVALUATOR

printf 'model=%s\nbase=%s\n' "$LLM_MODEL" "$LLM_BASE_URL"
```

Never print the full API key into logs or screenshots.

## Three-stage Connectivity Gate

Do not spend full-run compute until all three stages pass.

### Gate 1: Host To vLLM

```bash
curl -fsS "$LLM_BASE_URL/models"
```

The returned model ID must match `LLM_MODEL` after removing `openai/`.

### Gate 2: Docker Workspace Network To vLLM

For the tested Linux host-network setup:

```bash
docker run --rm --network host curlimages/curl:8.10.1 \
  -fsS http://127.0.0.1:8006/v1/models
```

If Gate 1 passes but Gate 2 fails, the agent run will usually show connection
errors while the vLLM log receives no request. Fix Docker networking before
testing the model or parsers.

Do not assume the default Docker bridge gateway is reachable. On the reference
server, the host could access `192.168.1.1:8006` but a bridge-network container
timed out. Test any bridge address from a container before using it.

### Gate 3: Thinking And Tool Calling

Run an OpenAI-compatible request through the same LiteLLM dependency used by the
runner:

```bash
uv run python - <<'PY'
import json
import os

from litellm import completion

response = completion(
    model=os.environ["LLM_MODEL"],
    api_base=os.environ["LLM_BASE_URL"],
    api_key=os.environ["LLM_API_KEY"],
    messages=[{"role": "user", "content": "Think briefly, then call echo with text OK."}],
    tools=[{
        "type": "function",
        "function": {
            "name": "echo",
            "description": "Echo text.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    }],
    tool_choice="auto",
    extra_body=json.loads(os.environ.get("LLM_EXTRA_BODY_JSON") or "{}"),
    max_completion_tokens=4096,
    temperature=float(os.environ.get("LLM_TEMPERATURE", "0.6")),
    top_p=float(os.environ.get("LLM_TOP_P", "0.95")),
    top_k=float(os.environ.get("LLM_TOP_K", "20")),
)
message = response.choices[0].message
print("finish_reason:", response.choices[0].finish_reason)
print("has_reasoning:", bool(getattr(message, "reasoning_content", None)))
print("content:", repr(message.content))
print("tool_calls:", message.tool_calls)
PY
```

The request must reach vLLM and return either a valid structured tool call or a
clear final response. Reject the configuration if it produces parser exceptions,
ends by length with only `reasoning_content`, or returns malformed arguments.

## AsynCodeBench Smoke Test

The three gates validate transport and parsing, but only a real runner smoke
validates OpenHands. Start with `cachetools` and a fresh directory:

```bash
cd /absolute/path/to/AsynCodeBench/reproductions/async-swe-agents
export ENV_FILE="$PWD/.env.local-model"
source scripts/env.sh

TASK=cachetools
MODEL_TAG=local-model
RUN_VERSION=local_smoke_v01

MODEL_TAG="$MODEL_TAG" \
RUN_VERSION="$RUN_VERSION" \
SINGLE_ITERATIONS=5 \
SPECIALIST_ITERATIONS=0 \
CAID_MANAGER_ITERATIONS=0 \
CAID_SUB_ITERATIONS=0 \
RUN_SERIAL=0 \
RUN_ASYNC_PRIVATE=0 \
RUN_CAID=0 \
WORKSPACE_PORT_STRATEGY=auto \
scripts/run_asyncodebench_all_protocols_env.sh "$TASK"
```

A valid smoke run has all of these properties:

- vLLM logs receive `/v1/chat/completions` requests;
- `Iterations used` is greater than zero;
- no provider, connection, tool-parser, or context-window error occurs;
- the output directory contains `report.json`, `cost.json`, `runtime.txt`, and
  `dependency_probe_checkpoints.jsonl`;
- `report.json` identifies the AsynCodeBench manifest evaluator;
- the run tests the curated task source rather than raw Commit0 fallback.

The model does not need to solve the smoke task. The smoke gate checks the
harness, not model quality.

## Four-protocol Cachetools Template

After the smoke passes, use the same server process and environment for all four
protocols. Run these commands sequentially:

```bash
cd /absolute/path/to/AsynCodeBench/reproductions/async-swe-agents
export ENV_FILE="$PWD/.env.local-model"
source scripts/env.sh

unset ASYNCODEBENCH_DISABLE_CURATED_TASK_SOURCE
unset ASYNCODEBENCH_DISABLE_CURATED_TASK_CONFIG
unset ASYNCODEBENCH_DISABLE_MANIFEST_EVALUATOR

TASK=cachetools
MODEL_TAG=local-model
RUN_VERSION=thinking_131k_o32768_seq2_v01

MODEL_TAG="$MODEL_TAG" \
RUN_VERSION="$RUN_VERSION" \
SINGLE_ITERATIONS=100 \
SPECIALIST_ITERATIONS=100 \
CAID_MANAGER_ITERATIONS=100 \
CAID_SUB_ITERATIONS=100 \
ROUNDS_OF_CHAT=2 \
WORKSPACE_PORT_STRATEGY=auto \
scripts/run_asyncodebench_all_protocols_env.sh "$TASK"
```

Use `docs/MODEL_EXPERIMENT_RUNBOOK.md` for per-task specialist counts and the
post-run analysis commands.

## Gemma 4 26B-A4B Corrected Profile

The first Gemma sweep included an outdated template/configuration phase and
configured the server at 131,000 tokens. One repeated failure was the boundary case
`98,233 + 32,768 = 131,001`. The corrected profile uses Gemma's exact supported
131,072-token client limit with a 135,168-token server window while preserving
the 32,768-token completion budget. That
sweep is useful for
debugging, but it must not be interpreted as the model's clean capability
result: 13 of 68 selected runs contained explicit context-window failures, and
many more contained unparsed raw tool-call text.

The corrected profile changes only the model adapter and serving harness:

- the chat template is synchronized with vLLM's official Gemma 4 template;
- thinking and the `gemma4` reasoning/tool parsers remain enabled;
- the client input limit is 131,072 tokens and the server window is 135,168;
- the fixed per-call output limit remains 32,768 tokens, preserving Gemma's
  long-reasoning capacity;
- task/scenario manifests, agent assignments, four protocols, and the released
  100-response capability profile remain unchanged.

The currently tracked template exactly matches Hugging Face model revision
`4d7ae4984b7db7de8f8457170b3f1a419ee76d52` (SHA-256
`ae53464bf3be25802b3a5b37def7fd89667067d7577049b3b2d74c4d8de4c6d4`).
The remaining parser requirement is vLLM 0.24.0 or newer. The previously used
vLLM 0.19.1 has the legacy split parser and is not valid for formal multi-turn
Gemma agent runs. See `docs/GEMMA4_CAID_HARNESS_FIX.md` for the diagnosis,
separate environment setup, and result-classification rules.

The tracked collaborator profile is:

```text
reproductions/async-swe-agents/configs/model_profiles/gemma4-26b-a4b.env.example
```

Create one ignored env file per endpoint:

```bash
cd /absolute/path/to/AsynCodeBench/reproductions/async-swe-agents
cp configs/model_profiles/gemma4-26b-a4b.env.example .env.gemma4-26b-a4b.8006
```

The server wrapper accepts GPU ID, API port, and `max-num-seqs`:

```bash
scripts/serve_gemma4_26b_a4b.sh 0 8006 2
```

Use `2`, `3`, or `4` sequence slots according to the task's specialist count.
Do not change that value between the four protocols for one task. The wrapper
starts the text-only profile with a 135,168-token server window, 32K scheduler
batching, official Gemma 4 parsers, and the repository's pinned official
template. It rejects vLLM older than 0.24.0 before loading the model.

After the server and the three connectivity gates pass, run one task with:

```bash
cd /absolute/path/to/AsynCodeBench/reproductions/async-swe-agents

ENV_FILE="$PWD/.env.gemma4-26b-a4b.8006" \
ASYNCODEBENCH_WORKSPACE_HOST_PORT=18000 \
RUN_VERSION=officialtmpl_131072_o32768_v02 \
scripts/run_gemma4_task_env.sh cachetools
```

The wrapper rejects non-official tasks, selects the official number of
specialists, verifies the Gemma model and context settings, checks the endpoint,
and invokes the shared four-protocol runner. For parallel task sweeps, each
terminal needs a different vLLM port, env file, GPU, and a non-overlapping block
of four OpenHands workspace ports, for example `18000`, `18010`, `18020`, and
`18030`.

Before restarting all 16 tasks, run `cachetools` as the formal v2 smoke and
inspect every protocol. A valid corrected run must have nonzero iterations, no
context-window exception, no raw `<|tool_call>` assistant output, no early
pytest race, and the normal AsynCodeBench evaluator/probe artifacts. Preserve
the old v1 directories; use the new model tag/version rather than overwriting
them.

Run the automatic infrastructure gate on the four new directories before
starting the other 16 tasks:

```bash
python scripts/check_run_health.py \
  outputs/repro_commit0/cachetools/gemma4-26b-a4b-v2_single_i30_officialtmpl_131072_o32768_v02 \
  outputs/repro_commit0/cachetools/gemma4-26b-a4b-v2_serial_2agents_s30_officialtmpl_131072_o32768_v02 \
  outputs/repro_commit0/cachetools/gemma4-26b-a4b-v2_async_private_2agents_s30_officialtmpl_131072_o32768_v02 \
  outputs/repro_commit0/cachetools/gemma4-26b-a4b-v2_caid_multi_2agents_m30_s30_officialtmpl_131072_o32768_v02
```

Exit code `0` means the run is infrastructure-clean; it does not mean the model
solved the task. A nonzero exit identifies missing artifacts, a wrong evaluator,
zero-iteration races, context/provider failures, or unparsed raw tool calls.

## Shared All-protocol Runner

To avoid terminal corruption from pasting a long nested `bash -lc` block, the
same sequence is available through a repository script:

```bash
cd /absolute/path/to/AsynCodeBench/reproductions/async-swe-agents

ENV_FILE="$PWD/.env.local-model" \
ASYNCODEBENCH_WORKSPACE_DOCKER_NETWORK=host \
ASYNCODEBENCH_WORKSPACE_HOST_PORT=8000 \
MODEL_TAG=local-model \
RUN_VERSION=thinking_131k_o32768_seq2_v01 \
scripts/run_asyncodebench_all_protocols_env.sh cachetools
```

The script rejects every pre-existing output directory before making any model
call. After an interruption, preserve the old directory and increment
`RUN_VERSION`.

By default, it assigns one workspace port per protocol from the configured base:
single uses `BASE`, serial `BASE+1`, async-private `BASE+2`, and CAID `BASE+3`.
This avoids the OpenHands SDK bind check failing on a recently closed port. It
also verifies each selected port with the same socket-bind operation used by the
SDK. Set `WORKSPACE_PORT_STRATEGY=fixed` only when a single reusable port is
required.

When several experiments share a host, let the runner find a free four-port
block instead of guessing a base port:

```bash
WORKSPACE_PORT_STRATEGY=auto \
WORKSPACE_PORT_SCAN_START=20000 \
WORKSPACE_PORT_SCAN_END=60000 \
scripts/run_asyncodebench_all_protocols_env.sh cachetools
```

Automatic selection changes only OpenHands workspace ports. It does not change
the vLLM endpoint in `LLM_BASE_URL`.

To continue after one protocol completed but a later protocol failed, disable
completed modes and use a fresh version for the remaining outputs:

```bash
RUN_SINGLE=0 \
RUN_VERSION=thinking_131k_o32768_seq2_v02 \
scripts/run_asyncodebench_all_protocols_env.sh cachetools
```

Available mode flags are `RUN_SINGLE`, `RUN_SERIAL`, `RUN_ASYNC_PRIVATE`, and
`RUN_CAID`; each accepts `0` or `1` and defaults to `1`.

## Concurrency And Experimental Fairness

There are two different forms of concurrency:

1. **Within-run agent concurrency:** `async_private` and CAID subagents can make
   overlapping requests. This is part of the benchmark condition and requires
   at least two vLLM sequence slots.
2. **Across-run concurrency:** launching multiple tasks or protocols at once.
   This is an infrastructure choice that competes for KV cache, GPU scheduling,
   Docker ports, CPU, and disk.

For the main benchmark, preserve within-run concurrency but execute task runs
sequentially. Across-run parallelism makes runtime and timeout outcomes depend on
uncontrolled server load. If it is intentionally studied, allocate a unique
OpenHands host port to each process and report vLLM capacity and concurrent load.

Keep the server configuration fixed for single, serial, async-private, and CAID.
Changing `max-num-seqs`, context length, parser, or output budget by protocol
confounds agent protocol with inference infrastructure.

## Troubleshooting Matrix

### `LLM Provider NOT provided`

Cause: the model lacks a LiteLLM provider namespace.

```bash
LLM_MODEL=openai/Qwen/Qwen3.6-27B
```

### Direct Call Works But vLLM Receives Nothing From The Agent

Cause: the Docker workspace cannot reach the host endpoint, or the wrong env
file was loaded.

Check Gate 2, then verify:

```bash
echo "$ENV_FILE"
echo "$LLM_BASE_URL"
echo "$LLM_MODEL"
```

Use host networking on the tested Linux setup.

### `auto tool choice requires --enable-auto-tool-choice`

Restart vLLM with both:

```text
--enable-auto-tool-choice
--tool-call-parser <parser-compatible-with-this-model>
```

### Tool Parser Emits JSON/XML Errors

The server parser does not match the model's tool-call format. Do not treat this
as model failure. Select a parser supported by the installed vLLM and model, then
repeat Gate 3. The tested Qwen3.6 setup uses `qwen3_xml`; another Qwen or vLLM
release may use a different parser.

### Thinking Exists But `content` And `tool_calls` Are Empty

If `finish_reason=length` and completion tokens equal the configured cap, the
thinking trace consumed the full output budget. Increase
`LLM_MAX_OUTPUT_TOKENS`, make sure the reasoning parser is compatible, and use a
fresh run directory. This is harness truncation, not a valid task result.

### Context Window Exceeded

The prompt plus requested completion exceeds `--max-model-len`. Confirm that
`LLM_MAX_INPUT_TOKENS` equals `--max-model-len`. The corrected Gemma profile
uses its supported 131,072-token context with 32,768 output tokens; do not set a
larger context without an explicitly validated long-context extension. If the
same error persists beyond the old one-token boundary, stop the sweep and
inspect the actual prompt size before changing all protocols.

### Repeated Remote Conversation Poll Timeouts

Long local generations may exceed the legacy OpenHands request timeout even
while vLLM is working. Use:

```bash
ASYNCODEBENCH_CONVERSATION_RUN_TIMEOUT=43200
ASYNCODEBENCH_REMOTE_TRIGGER_TIMEOUT=30
ASYNCODEBENCH_REMOTE_POLL_TIMEOUT=3600
ASYNCODEBENCH_REMOTE_POLL_INTERVAL=5
```

If vLLM logs are advancing, do not submit the same run again. The trigger shim
polls the existing conversation after a delayed `/run` acknowledgement. If vLLM
is idle and the same poll repeatedly times out, investigate Docker networking or
the workspace service.

### `Port 8000 is not available`

Another OpenHands workspace or stale process owns the host port.

```bash
ss -ltnp | rg ':8000'
docker ps --format 'table {{.ID}}\t{{.Names}}\t{{.Ports}}'
```

Finish or stop only the workspace you own, or choose another free
`ASYNCODEBENCH_WORKSPACE_HOST_PORT`. Do not run two formal protocols against the
same host port.

### vLLM Engine Initialization Fails Or OOMs

Check `nvidia-smi` for stale GPU users, preserve `max-num-seqs=2`, and reduce the
context length first. Tensor parallel and data parallel are not interchangeable:
DP duplicates the model, while TP shards it. A command that starts under DP may
fail under TP because communication, memory layout, and engine initialization
are different.

### Only One GPU Is Busy Under Data Parallelism

This can be normal when only one request is active. Data parallelism provides
replicas; it does not split every request across all GPUs. Validate distribution
under multiple concurrent requests rather than a single-agent turn.

### Missing `scipy.optimize`, `httpcore`, Or Similar At Startup

The vLLM executable is importing a mixed conda/user-site environment. Verify the
exact interpreter and imports before installing anything:

```bash
VLLM_PY=/path/to/vllm-environment/bin/python
"$VLLM_PY" -c 'import sys; print(sys.executable); print(*sys.path, sep="\n")'
"$VLLM_PY" -c 'import scipy, scipy.optimize, httpcore; print("imports ok")'
```

Install missing packages into that exact environment. Do not enable
`PYTHONNOUSERSITE=1` on a partially mixed environment unless all dependencies
have first been installed inside the environment.

### Local Cost Is `$0`

LiteLLM may not have a price mapping for a local served model. This is expected.
Keep `cost.json`, but report input/output tokens, wall-clock time, GPU type/count,
and GPU-hours.

## Formal Result Acceptance Gate

Include a local run in the official result set only when:

- the output directory was fresh and contains one run log;
- agent iterations are greater than zero;
- no provider/network/parser/context instrumentation failure occurred;
- the same vLLM profile was used across all four protocols;
- the run used the curated AsynCodeBench task source and manifest evaluator;
- `dependency_probe_checkpoints.jsonl` and `process_metrics_summary.json` exist;
- final tests were collected consistently with the task manifest;
- the model patch, not a harness failure, explains any test failure;
- the server command and hardware profile are recorded.

A model is allowed to fail the coding task. Failed final tests, unresolved
dependencies, failed subagent attempts, and manager recovery are benchmark
outcomes. Connection failures, parser mismatches, zero iterations, and accidental
test non-collection are infrastructure failures and must be fixed or rerun.

## Source References

- vLLM CLI serve arguments: <https://docs.vllm.ai/en/latest/cli/serve/>
- vLLM OpenAI-compatible automatic tool calling:
  <https://docs.vllm.ai/en/v0.6.4/serving/openai_compatible_server.html>
- Qwen vLLM deployment, thinking, reasoning, and tools:
  <https://qwen.readthedocs.io/en/stable/deployment/vllm.html>
- Qwen function calling:
  <https://qwen.readthedocs.io/en/stable/framework/function_call.html>
- vLLM Gemma 4 usage guide:
  <https://docs.vllm.ai/projects/recipes/en/stable/Google/Gemma4.html>
- vLLM official Gemma 4 tool chat template:
  <https://raw.githubusercontent.com/vllm-project/vllm/refs/heads/main/examples/tool_chat_template_gemma4.jinja>
