#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# shellcheck source=scripts/env.sh
source scripts/env.sh

repo="${1:-cachetools}"
max_subagents="${MAX_SUBAGENTS:-4}"
sub_iterations="${SUB_ITERATIONS:-50}"
output_dir="${OUTPUT_DIR:-outputs/repro_commit0/${repo}/serial_specialists_${max_subagents}agents}"

optional_flags=()
if [[ -n "${LLM_SUBAGENT_MODEL:-}" ]]; then
  optional_flags+=(--subagent_model "$LLM_SUBAGENT_MODEL")
fi

uv run python run_static_protocol.py \
  --task commit0 \
  --protocol serial_specialists \
  --repo "$repo" \
  --model "$LLM_MODEL" \
  "${optional_flags[@]}" \
  --max_subagents "$max_subagents" \
  --sub_iterations "$sub_iterations" \
  --dataset_path "$COMMIT0_DATASET_PATH" \
  --output_dir "$output_dir"
