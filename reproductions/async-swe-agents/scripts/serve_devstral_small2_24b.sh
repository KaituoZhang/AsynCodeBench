#!/usr/bin/env bash
set -euo pipefail

gpu_id="${1:?Usage: scripts/serve_devstral_small2_24b.sh <gpu-id> <port> <max-seqs>}"
port="${2:?Usage: scripts/serve_devstral_small2_24b.sh <gpu-id> <port> <max-seqs>}"
max_seqs="${3:?Usage: scripts/serve_devstral_small2_24b.sh <gpu-id> <port> <max-seqs>}"

vllm_bin="${VLLM_BIN:-$(command -v vllm || true)}"
[[ -n "$vllm_bin" && -x "$vllm_bin" ]] || {
  echo "vLLM executable not found; activate its environment or set VLLM_BIN." >&2
  exit 1
}
vllm_python="${VLLM_PYTHON:-$(dirname "$vllm_bin")/python}"
[[ -x "$vllm_python" ]] || { echo "vLLM Python not found: $vllm_python" >&2; exit 1; }
[[ "$gpu_id" =~ ^[0-9]+$ ]] || { echo "gpu-id must be a non-negative integer" >&2; exit 1; }
[[ "$port" =~ ^[1-9][0-9]*$ ]] || { echo "port must be a positive integer" >&2; exit 1; }
[[ "$max_seqs" =~ ^[1-9][0-9]*$ ]] || { echo "max-seqs must be positive" >&2; exit 1; }

model="${DEVSTRAL_MODEL:-mistralai/Devstral-Small-2-24B-Instruct-2512}"
max_model_len="${DEVSTRAL_MAX_MODEL_LEN:-65536}"
max_batched_tokens="${DEVSTRAL_MAX_BATCHED_TOKENS:-32768}"
gpu_memory_utilization="${DEVSTRAL_GPU_MEMORY_UTILIZATION:-0.92}"

vllm_version="$($vllm_python -c 'import importlib.metadata as m; print(m.version("vllm"))')"
mistral_common_version="$($vllm_python -c 'import importlib.metadata as m; print(m.version("mistral-common"))')"
if ! "$vllm_python" -c \
  'import re, sys; p=[int(x) for x in re.findall(r"\d+", sys.argv[1])[:3]]; raise SystemExit(tuple((p+[0,0,0])[:3]) < (1,8,6))' \
  "$mistral_common_version"; then
  echo "Devstral Small 2 requires mistral-common >= 1.8.6; found $mistral_common_version" >&2
  exit 1
fi

echo "[DevstralSmall2] vllm=$vllm_version mistral_common=$mistral_common_version"
echo "[DevstralSmall2] gpu=$gpu_id port=$port max_seqs=$max_seqs max_model_len=$max_model_len model=$model"

exec env \
  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  TRANSFORMERS_NO_TF=1 \
  USE_TF=0 \
  CUDA_VISIBLE_DEVICES="$gpu_id" \
  "$vllm_bin" serve "$model" \
    --served-model-name "$model" \
    --host 0.0.0.0 \
    --port "$port" \
    --max-model-len "$max_model_len" \
    --gpu-memory-utilization "$gpu_memory_utilization" \
    --max-num-seqs "$max_seqs" \
    --max-num-batched-tokens "$max_batched_tokens" \
    --language-model-only \
    --enable-auto-tool-choice \
    --tool-call-parser mistral
