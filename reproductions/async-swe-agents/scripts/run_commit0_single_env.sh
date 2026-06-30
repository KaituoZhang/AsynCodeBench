#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# shellcheck source=scripts/env.sh
source scripts/env.sh

repo="${1:-minitorch}"
max_iterations="${MAX_ITERATIONS:-50}"
output_dir="${OUTPUT_DIR:-outputs/repro_commit0/${repo}/haiku45_single}"

uv run python run_infer.py \
  --task commit0 \
  --repo "$repo" \
  --model "$LLM_MODEL" \
  --max_iterations "$max_iterations" \
  --nomulti_agent \
  --dataset_path "$COMMIT0_DATASET_PATH" \
  --output_dir "$output_dir"

