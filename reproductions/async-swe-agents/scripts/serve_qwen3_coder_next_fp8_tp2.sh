#!/usr/bin/env bash
set -euo pipefail

gpu_ids="${1:?Usage: scripts/serve_qwen3_coder_next_fp8_tp2.sh <gpu-id,gpu-id> <port>}"
port="${2:?Usage: scripts/serve_qwen3_coder_next_fp8_tp2.sh <gpu-id,gpu-id> <port>}"

vllm_bin="${VLLM_BIN:-$(command -v vllm || true)}"
[[ -n "$vllm_bin" && -x "$vllm_bin" ]] || {
  echo "vLLM executable not found; activate its environment or set VLLM_BIN." >&2
  exit 1
}
vllm_python="${VLLM_PYTHON:-$(dirname "$vllm_bin")/python}"
[[ -x "$vllm_python" ]] || { echo "vLLM Python not found: $vllm_python" >&2; exit 1; }
[[ "$gpu_ids" =~ ^[0-9]+,[0-9]+$ ]] || { echo "GPU IDs must have the form 0,1" >&2; exit 1; }
[[ "$port" =~ ^[1-9][0-9]*$ ]] || { echo "port must be a positive integer" >&2; exit 1; }

model="${QWEN3_CODER_NEXT_MODEL:-Qwen/Qwen3-Coder-Next-FP8}"
max_model_len="${QWEN3_CODER_NEXT_MAX_MODEL_LEN:-131000}"
max_num_seqs="${QWEN3_CODER_NEXT_MAX_NUM_SEQS:-3}"
max_batched_tokens="${QWEN3_CODER_NEXT_MAX_BATCHED_TOKENS:-32768}"
gpu_memory_utilization="${QWEN3_CODER_NEXT_GPU_MEMORY_UTILIZATION:-0.90}"
expected_nccl="${QWEN3_CODER_NEXT_NCCL_VERSION:-22705}"

nccl_path="$($vllm_python -c '
import pathlib, sys
version = f"python{sys.version_info.major}.{sys.version_info.minor}"
path = pathlib.Path(sys.prefix) / "lib" / version / "site-packages/nvidia/nccl/lib/libnccl.so.2"
if not path.is_file():
    raise SystemExit(f"NCCL library not found for the selected interpreter: {path}")
print(path)
')"
actual_nccl="$($vllm_python -c '
import ctypes, sys
value = ctypes.c_int()
library = ctypes.CDLL(sys.argv[1])
library.ncclGetVersion(ctypes.byref(value))
print(value.value)
' "$nccl_path")"
if [[ "$actual_nccl" != "$expected_nccl" ]]; then
  echo "NCCL runtime mismatch: expected $expected_nccl, found $actual_nccl at $nccl_path" >&2
  echo "Repair the vLLM environment before starting a reportable campaign." >&2
  exit 1
fi

vllm_version="$($vllm_python -c 'import importlib.metadata as m; print(m.version("vllm"))')"
torch_profile="$($vllm_python -c 'import torch; print(f"{torch.__version__} cuda={torch.version.cuda}")')"
echo "[Qwen3CoderNext] vllm=$vllm_version torch=$torch_profile nccl=$actual_nccl"
echo "[Qwen3CoderNext] gpu=$gpu_ids port=$port model=$model max_model_len=$max_model_len"

exec env \
  LD_PRELOAD="$nccl_path" \
  VLLM_NCCL_SO_PATH="$nccl_path" \
  NCCL_DEBUG="${NCCL_DEBUG:-WARN}" \
  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  TRANSFORMERS_NO_TF=1 \
  USE_TF=0 \
  CUDA_VISIBLE_DEVICES="$gpu_ids" \
  "$vllm_bin" serve "$model" \
    --served-model-name "$model" \
    --trust-remote-code \
    --host 0.0.0.0 \
    --port "$port" \
    --dtype bfloat16 \
    --tensor-parallel-size 2 \
    --disable-custom-all-reduce \
    --gpu-memory-utilization "$gpu_memory_utilization" \
    --max-model-len "$max_model_len" \
    --max-num-seqs "$max_num_seqs" \
    --max-num-batched-tokens "$max_batched_tokens" \
    --seed 1 \
    --enable-auto-tool-choice \
    --tool-call-parser qwen3_coder \
    --language-model-only \
    --generation-config auto
