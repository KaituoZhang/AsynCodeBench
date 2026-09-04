# Qwen3-Coder-Next FP8 Local vLLM Runbook

This runbook records the validated local-serving profile for
`Qwen/Qwen3-Coder-Next-FP8` and the NCCL failure observed before the first
AsynCodeBench request was sent. The serving incident was an infrastructure
failure. It was not a benchmark task, protocol, Dependency Checker, evaluator,
or model-capability failure.

## Validated Profile

The profile validated on 2026-08-30 uses:

| Component | Validated value |
| --- | --- |
| GPUs | 2 x NVIDIA A100-SXM4-80GB |
| NVIDIA driver | 550.127.05 |
| Model | `Qwen/Qwen3-Coder-Next-FP8` |
| vLLM | 0.19.1 |
| PyTorch | 2.10.0+cu128 |
| CUDA runtime reported by PyTorch | 12.8 |
| NCCL | 2.27.5 (`ncclGetVersion=22705`) |
| Tensor parallel size | 2 |
| Context limit | 131,000 tokens |
| Output limit | 32,768 tokens |
| Scheduler capacity | 3 sequences; 32,768 batched tokens |
| Tool parser | `qwen3_coder` |
| Generation configuration | model `generation_config.json` |
| Seed | 1 |

On A100, vLLM reports that native FP8 compute is unavailable and selects the
Marlin weight-only FP8 path. This is an expected hardware/backend warning, not
a startup failure. The validated startup loaded all 40 checkpoint shards,
reported 38.07 GiB of model memory, completed `torch.compile`, initialized the
KV cache for the 131,000-token profile, captured CUDA graphs, and exposed the
OpenAI-compatible `/v1/models` and `/v1/chat/completions` routes.

## Recorded Startup Failure

The original environment had inconsistent package metadata and shared-library
contents:

- `torch==2.10.0+cu128` depended on `nvidia-nccl-cu12==2.27.5`;
- the `nvidia-nccl-cu12` distribution metadata reported 2.27.5;
- the actual environment library returned NCCL 2.28.9;
- the host used NVIDIA driver 550.127.05.

Model loading succeeded, but the first tensor-parallel
`torch.distributed.all_reduce` failed with:

```text
NCCL version 2.28.9
Cuda failure 'CUDA driver version is insufficient for CUDA runtime version'
```

The final Python warning about leaked `shared_memory` objects was shutdown
cleanup after the worker crash. It was not the root cause.

Setting only `VLLM_NCCL_SO_PATH` to a system NCCL 2.20.5 library did not fix
the run: it changed vLLM's direct NCCL wrapper, while PyTorch collectives still
loaded NCCL 2.28.9. Preloading NCCL 2.20.5 was also invalid because PyTorch
2.10 requires the newer `ncclCommShrink` symbol. The working repair was to
restore the environment's declared NCCL 2.27.5 and load that same library for
both PyTorch and vLLM.

## Result-Validity Classification

This incident occurred during model-server initialization, before an
AsynCodeBench task request or agent trajectory began. Therefore:

- no failed startup is a model score or task outcome;
- no startup attempt enters an aggregate or statistical analysis;
- previously completed bundles are unchanged and do not require rerunning;
- subsequent reportable runs must record the repaired serving environment;
- a later coding failure after the endpoint passes the normal preflight gates
  remains a valid model/agent outcome and must not be selectively rerun.

The model checkpoint itself is not implicated: the same weights and 131k
profile completed startup once the NCCL library was made consistent. The
precise classification is **model-serving environment incompatibility**, not
“benchmark bug” and not “model failure.”

## Repair And Verification

Reinstall the NCCL version required by the selected PyTorch environment:

```bash
uv pip install \
  --python /path/to/vllm-environment/bin/python \
  --reinstall \
  --no-deps \
  'nvidia-nccl-cu12==2.27.5'
```

Do not trust distribution metadata alone. Verify the actual shared object:

```bash
/path/to/vllm-environment/bin/python - <<'PY'
import ctypes
import pathlib
import sys

root = pathlib.Path(sys.prefix)
version = f"python{sys.version_info.major}.{sys.version_info.minor}"
path = root / "lib" / version / "site-packages/nvidia/nccl/lib/libnccl.so.2"
if not path.is_file():
    raise SystemExit(f"NCCL library not found: {path}")
version = ctypes.c_int()
library = ctypes.CDLL(str(path))
library.ncclGetVersion(ctypes.byref(version))
print(path)
print(version.value)
PY
```

The validated value is `22705`. Stop if the value differs; silently changing
the serving stack in the middle of a campaign would break provenance.

## Start Two TP2 Servers

The checked-in wrapper resolves NCCL from the selected vLLM Python environment,
verifies its runtime version, and supplies the same path through `LD_PRELOAD`
and `VLLM_NCCL_SO_PATH`:

```bash
cd reproductions/async-swe-agents

VLLM_BIN=/path/to/vllm-environment/bin/vllm \
scripts/serve_qwen3_coder_next_fp8_tp2.sh 0,1 8100
```

In a second terminal:

```bash
cd reproductions/async-swe-agents

VLLM_BIN=/path/to/vllm-environment/bin/vllm \
scripts/serve_qwen3_coder_next_fp8_tp2.sh 2,3 8101
```

Each server stays in the foreground. Stop it with `Ctrl+C` after its assigned
benchmark queue completes.

## Preflight

Do not start a task merely because the process exists. Check both endpoints:

```bash
curl -fsS http://127.0.0.1:8100/v1/models
curl -fsS http://127.0.0.1:8101/v1/models
```

Then load the corresponding ignored runner environment and execute the normal
host, Docker-network, and structured-tool-call gates from
`LOCAL_VLLM_EXPERIMENT_RUNBOOK.md`. Keep the model revision, NCCL runtime,
vLLM/PyTorch versions, context and output limits, generation settings, and
server command fixed across all four protocols.

The public runner template is
`reproductions/async-swe-agents/configs/model_profiles/qwen3-coder-next-fp8.env.example`.
Local per-port files are intentionally ignored by Git.
