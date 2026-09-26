#!/usr/bin/env bash
set -euo pipefail

runner_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
gpu_id="${1:?Usage: scripts/serve_gemma4_26b_a4b.sh <gpu-id> <port> <max-seqs>}"
port="${2:?Usage: scripts/serve_gemma4_26b_a4b.sh <gpu-id> <port> <max-seqs>}"
max_seqs="${3:?Usage: scripts/serve_gemma4_26b_a4b.sh <gpu-id> <port> <max-seqs>}"
max_model_len="${GEMMA_MAX_MODEL_LEN:-163840}"

vllm_bin="${VLLM_BIN:-$runner_root/.venv-vllm-gemma4/bin/vllm}"
vllm_python="${VLLM_PYTHON:-$(dirname "$vllm_bin")/python}"
model="${GEMMA_MODEL:-google/gemma-4-26B-A4B-it}"
served_model_name="${GEMMA_SERVED_MODEL_NAME:-google/gemma-4-26B-A4B-it}"
template="$runner_root/configs/chat_templates/tool_chat_template_gemma4.jinja"
# Pinned from google/gemma-4-26B-A4B-it revision
# 4d7ae4984b7db7de8f8457170b3f1a419ee76d52 (SHA-256 ae53464b...).

[[ -x "$vllm_bin" ]] || { echo "vLLM executable not found: $vllm_bin" >&2; exit 1; }
[[ -x "$vllm_python" ]] || { echo "vLLM Python not found: $vllm_python" >&2; exit 1; }
[[ -f "$template" ]] || { echo "Gemma template not found: $template" >&2; exit 1; }
[[ "$max_seqs" =~ ^[1-9][0-9]*$ ]] || { echo "max-seqs must be positive" >&2; exit 1; }

vllm_version="$($vllm_python -c 'import importlib.metadata as m; print(m.version("vllm"))')"
if ! "$vllm_python" -c 'import re, sys; parts = [int(item) for item in re.findall(r"\d+", sys.argv[1])[:3]]; sys.exit(0 if tuple((parts + [0, 0, 0])[:3]) >= (0, 24, 0) else 1)' "$vllm_version"; then
  if [[ "${GEMMA_ALLOW_LEGACY_VLLM:-0}" != "1" ]]; then
    echo "Gemma 4 formal runs require vLLM >= 0.24.0; found $vllm_version" >&2
    echo "vLLM 0.24 introduced the unified Gemma parser needed after tool responses." >&2
    echo "Use a separate current Gemma vLLM environment and set VLLM_BIN, or set" >&2
    echo "GEMMA_ALLOW_LEGACY_VLLM=1 only to reproduce old diagnostic runs." >&2
    exit 1
  fi
  echo "[Gemma4] WARNING: allowing legacy vLLM $vllm_version for diagnostics only" >&2
fi

echo "[Gemma4] vllm=$vllm_version gpu=$gpu_id port=$port max_seqs=$max_seqs max_model_len=$max_model_len model=$model served_model_name=$served_model_name"

if [[ -n "${CUDA_HOME:-}" ]]; then
  echo "[Gemma4] ignoring inherited CUDA_HOME=$CUDA_HOME"
fi
echo "[Gemma4] FlashInfer sampler disabled; no local nvcc is required"

exec env \
  -u CUDA_HOME \
  PYTHONNOUSERSITE=1 \
  PATH="$(dirname "$vllm_bin"):$PATH" \
  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  TRANSFORMERS_NO_TF=1 \
  USE_TF=0 \
  VLLM_USE_FLASHINFER_SAMPLER=0 \
  CUDA_VISIBLE_DEVICES="$gpu_id" \
  "$vllm_bin" serve "$model" \
    --served-model-name "$served_model_name" \
    --trust-remote-code \
    --host 0.0.0.0 \
    --port "$port" \
    --max-model-len "$max_model_len" \
    --gpu-memory-utilization 0.90 \
    --max-num-seqs "$max_seqs" \
    --max-num-batched-tokens 32768 \
    --limit-mm-per-prompt '{"image":0,"audio":0}' \
    --enable-auto-tool-choice \
    --tool-call-parser gemma4 \
    --reasoning-parser gemma4 \
    --chat-template "$template" \
    --default-chat-template-kwargs '{"enable_thinking":true}'
