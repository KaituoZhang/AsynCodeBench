# Gemma 4 CAID Harness Diagnosis And Fix

This note records why Gemma 4 produced remote-conversation failures in
AsynCodeBench and the conditions required before its results are considered
formal benchmark evidence.

## Root Cause Summary

Three symptoms were previously grouped under "remote failure," but they have
different meanings.

1. **Exact 3,600-second termination was a runner timeout.** The checked-in
   Gemma profile had a 43,200-second conversation deadline, but endpoint-specific
   `.env.gemma4-*` copies did not. The runner silently used the OpenHands
   compatibility default of 3,600 seconds and stopped long CAID conversations
   while the agent server could still be running.
2. **Raw `<|tool_call>` text was a parser compatibility failure.** The server
   used vLLM 0.19.1, which has separate Gemma reasoning and tool parsers. The
   unified `vllm.parser.gemma4` state machine, including post-tool-response
   reasoning initialization, is present from vLLM 0.24.0. AsynCodeBench feeds
   tool results back repeatedly, so this matters more than in one-turn chat.
3. **`Remote conversation got stuck` is a model trajectory outcome.** The
   OpenHands server emits `STUCK` after detecting repeated actions, repeated
   errors, alternating loops, or a monologue. Repeatedly saying "I will use the
   terminal tool" without issuing a valid call is a genuine agent failure once
   parser and transport gates pass.

The host runner uses OpenHands SDK 1.11.0 while the Docker agent server is built
from repository SDK source at 1.29.2. The newer server has more careful
WebSocket and terminal-state handling. The runner therefore contains an
explicit REST compatibility wait rather than trusting the legacy client's
"any non-running status is complete" behavior.

## Verified Chat Template

The tracked file is:

```text
reproductions/async-swe-agents/configs/chat_templates/tool_chat_template_gemma4.jinja
```

It was compared byte-for-byte with the current Hugging Face model template:

```text
model revision: 4d7ae4984b7db7de8f8457170b3f1a419ee76d52
SHA-256: ae53464bf3be25802b3a5b37def7fd89667067d7577049b3b2d74c4d8de4c6d4
```

Do not modify this template to work around model behavior. The template is not
the remaining defect.

## Required vLLM Environment

Do not upgrade the shared Qwen environment in place. Create a separate Gemma
environment and pin the official CUDA 12.9 x86_64 wheel. Do not install an
unqualified `vllm` package with `unsafe-best-match`: PyPI may provide a newer
CUDA 13 wheel while the PyTorch index supplies CUDA 12.9, producing a mixed
environment that fails on `libcudart.so.13`.

```bash
cd /absolute/path/to/AsynCodeBench/reproductions/async-swe-agents

uv venv --clear --python 3.12 .venv-vllm-gemma4

uv pip install \
  --python .venv-vllm-gemma4/bin/python \
  'https://github.com/vllm-project/vllm/releases/download/v0.24.0/vllm-0.24.0%2Bcu129-cp38-abi3-manylinux_2_28_x86_64.whl' \
  --extra-index-url https://download.pytorch.org/whl/cu129 \
  --index-strategy unsafe-best-match

PYTHONNOUSERSITE=1 .venv-vllm-gemma4/bin/python -c \
  'import importlib.metadata as m; print(m.version("vllm"))'

PYTHONNOUSERSITE=1 .venv-vllm-gemma4/bin/python -c \
  'import torch, vllm; print(torch.__version__, torch.version.cuda, vllm.__version__)'
```

AsynCodeBench requires vLLM 0.24.0 or newer for a formal Gemma run. The pinned
CUDA 12.9 release above or the official `vllm/vllm-openai:gemma4` image is
preferred on the current A100 host. The server
wrapper rejects older versions unless `GEMMA_ALLOW_LEGACY_VLLM=1` is explicitly
set for diagnostic reproduction.

## Start And Validate The Server

For a two-specialist task on GPU 0 and port 8006:

```bash
cd /absolute/path/to/AsynCodeBench/reproductions/async-swe-agents

VLLM_BIN="$PWD/.venv-vllm-gemma4/bin/vllm" \
scripts/serve_gemma4_26b_a4b.sh 0 8006 2
```

The wrapper keeps the official Gemma reasoning parser, tool parser, chat
template, thinking mode, a server window of at least 163,840 tokens, and the
32,768-token scheduler batch setting. The third argument is `max-num-seqs`; set it to the task's
specialist count and keep it unchanged across all four protocols for that task.
It also prepends the selected vLLM environment's `bin` directory to `PATH`.
This is required because FlashInfer may invoke that environment's `ninja`
executable while profiling sampling kernels.

The wrapper also removes an inherited `CUDA_HOME` and sets
`VLLM_USE_FLASHINFER_SAMPLER=0`. On this server, login shells exported the
nonexistent path `/usr/local/cuda-11.8`, while the pinned vLLM and PyTorch
wheels use CUDA 12.9. FlashInfer's sampler therefore attempted to JIT compile
with a missing and incompatible `nvcc`, then surfaced only the generic
`Engine core initialization failed` message. The alternative vLLM sampler does
not require a local CUDA toolkit; this changes only the sampling implementation,
not the model, decoding parameters, context window, or benchmark protocol.

In another terminal:

```bash
cd /absolute/path/to/AsynCodeBench/reproductions/async-swe-agents

curl -fsS http://127.0.0.1:8006/version

uv run python scripts/check_gemma4_server.py \
  --base-url http://127.0.0.1:8006/v1 \
  --model google/gemma-4-26B-A4B-it \
  --minimum-version 0.24.0 \
  --minimum-context 163840

docker run --rm --network host curlimages/curl:8.10.1 \
  -fsS http://127.0.0.1:8006/v1/models
```

The metadata preflight rejects a legacy parser server, wrong served model, or
insufficient context before any benchmark request is made. The Docker command
checks the separate container-to-vLLM path. A successful host-side request is
not sufficient because `127.0.0.1` otherwise refers to the task container.

## Run One Formal Task

Endpoint env files must contain the Gemma model profile and matching port.
`run_gemma4_task_env.sh` now exports the remote lifecycle defaults itself, so a
stale endpoint copy cannot restore the old one-hour timeout. For this local
Linux profile it also defaults `ASYNCODEBENCH_WORKSPACE_DOCKER_NETWORK` to
`host`, while preserving an explicit override for other platforms.

```bash
cd /absolute/path/to/AsynCodeBench/reproductions/async-swe-agents

ENV_FILE="$PWD/.env.gemma4-26b-a4b.8006" \
ASYNCODEBENCH_WORKSPACE_HOST_PORT=18000 \
RUN_VERSION=vllm024plus_remotev2_v01 \
scripts/run_gemma4_task_env.sh cachetools
```

If a run reports `LLMServiceUnavailableError` with `Iterations used: 0`, treat
it as infrastructure-invalid. Keep the failed directory as evidence and rerun
with a new `RUN_VERSION` after the Docker connectivity gate passes.

The formal defaults are:

```text
conversation deadline:       43200 seconds
status request timeout:       3600 seconds
message request timeout:      3600 seconds
run trigger timeout:            30 seconds
initial IDLE grace:              30 seconds
REST terminal confirmation:      30 seconds
```

The runner waits through the initial IDLE race, retries `/run` at most once,
does not resend the user instruction after an ambiguous trigger timeout, and
confirms REST `FINISHED` before collecting events.

## Result Classification

Treat these as infrastructure-invalid and rerun after fixing the harness:

- vLLM below 0.24.0;
- raw `<|tool_call>` emitted as assistant text;
- connection/provider errors;
- context-window errors;
- `Run timed out ... conversation may still be running`;
- zero model iterations caused by any of the above.

Treat `Remote conversation got stuck` as a valid failed model trajectory when
all preflight gates passed. It may produce unresolved dependencies, zero patch
progress, high token use, or failed subagent attempts. Those are coordination
failures AsynCodeBench is designed to expose.

The health checker now reports this as the non-blocking observation
`model_trajectory_stuck`; it no longer labels it a transport failure.

## Sources

- vLLM Gemma 4 guide:
  <https://docs.vllm.ai/projects/recipes/en/stable/Google/Gemma4.html>
- vLLM unified Gemma parser:
  <https://docs.vllm.ai/en/latest/api/vllm/parser/gemma4/>
- Gemma 4 model and canonical chat template:
  <https://huggingface.co/google/gemma-4-26B-A4B-it>
- OpenHands remote conversation state:
  <https://github.com/OpenHands/software-agent-sdk/blob/main/openhands-sdk/openhands/sdk/conversation/state.py>
