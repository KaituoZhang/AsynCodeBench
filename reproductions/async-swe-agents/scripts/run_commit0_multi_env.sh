#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# shellcheck source=scripts/env.sh
source scripts/env.sh

repo="${1:-minitorch}"
max_iterations="${MAX_ITERATIONS:-30}"
max_subagents="${MAX_SUBAGENTS:-2}"
sub_iterations="${SUB_ITERATIONS:-50}"
rounds_of_chat="${ROUNDS_OF_CHAT:-2}"
output_dir="${OUTPUT_DIR:-outputs/repro_commit0/${repo}/haiku45_multi_${max_subagents}agents}"

optional_flags=()
if [[ -n "${LLM_SUBAGENT_MODEL:-}" ]]; then
  optional_flags+=(--subagent_model "$LLM_SUBAGENT_MODEL")
fi

uv run python run_infer.py \
  --task commit0 \
  --repo "$repo" \
  --model "$LLM_MODEL" \
  "${optional_flags[@]}" \
  --max_iterations "$max_iterations" \
  --max_subagents "$max_subagents" \
  --sub_iterations "$sub_iterations" \
  --rounds_of_chat "$rounds_of_chat" \
  --dataset_path "$COMMIT0_DATASET_PATH" \
  --output_dir "$output_dir"

