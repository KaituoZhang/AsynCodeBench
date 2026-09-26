#!/usr/bin/env bash
set -euo pipefail

RUNNER_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BENCHMARK_ROOT="$(cd "$RUNNER_ROOT/../.." && pwd)"
cd "$RUNNER_ROOT"

# shellcheck source=scripts/env.sh
source scripts/env.sh

RUN_ID="${RUN_ID:-pr-hard-20073-$(date -u +%Y%m%dT%H%M%SZ)}"
MODEL="${LLM_MODEL:?LLM_MODEL is required}"
SUBAGENT_MODEL="${LLM_SUBAGENT_MODEL:-$MODEL}"
PYTHON_BIN="${PYTHON_BIN:-$RUNNER_ROOT/.venv/bin/python}"
RUNTIME_ROOT="${PR_HARD_RUNTIME_ROOT:-$BENCHMARK_ROOT/.cache/pr_hard_runtime/v0.4/apache-tvm-20073}"
RUNTIME_BACKEND="${PR_HARD_RUNTIME_BACKEND:-container}"
RUNTIME_IMAGE="${PR_HARD_RUNTIME_IMAGE:-}"
DRY_RUN="${DRY_RUN:-0}"

for flag in RUN_SINGLE RUN_SERIAL RUN_ASYNC_PRIVATE RUN_CAID; do
  value="${!flag:-1}"
  if [[ "$value" != "0" && "$value" != "1" ]]; then
    echo "$flag must be 0 or 1" >&2
    exit 2
  fi
done

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Runner environment is missing: $PYTHON_BIN" >&2
  echo "Run: bash scripts/setup_evaluation.sh (from the benchmark root)" >&2
  exit 2
fi

"$PYTHON_BIN" -c '
import json, os
raw = os.environ.get("ASYNCODEBENCH_VLLM_CONFIG_JSON", "")
if not raw:
    raise SystemExit("ASYNCODEBENCH_VLLM_CONFIG_JSON is required for PR-hard 20073")
config = json.loads(raw)
slots = int(config.get("max_num_seqs", 0))
if slots < 3:
    raise SystemExit(
        f"PR-hard 20073 has three concurrent specialists; max_num_seqs={slots} "
        "is smoke-only. Use at least 3 for a formal four-protocol run."
    )
'

if [[ "$RUNTIME_BACKEND" == "local" ]]; then
  "$BENCHMARK_ROOT/.venv-benchmark/bin/python" \
    "$BENCHMARK_ROOT/scripts/prepare_pr_hard_runtime.py" \
    --task-id pr-hard:apache-tvm-20073 \
    --runtime-root "$RUNTIME_ROOT" \
    --check
elif [[ "$RUNTIME_BACKEND" != "container" ]]; then
  echo "PR_HARD_RUNTIME_BACKEND must be container or local" >&2
  exit 2
fi

if [[ "$DRY_RUN" != "1" ]]; then
  "$PYTHON_BIN" \
    "$BENCHMARK_ROOT/scripts/check_openhands_runtime_consistency.py" \
    --require-clean
fi

unset ASYNCODEBENCH_WORKSPACE_HOST_PORT

protocols=()
[[ "${RUN_SINGLE:-1}" == "1" ]] && protocols+=(single)
[[ "${RUN_SERIAL:-1}" == "1" ]] && protocols+=(serial_specialists)
[[ "${RUN_ASYNC_PRIVATE:-1}" == "1" ]] && protocols+=(async_private)
[[ "${RUN_CAID:-1}" == "1" ]] && protocols+=(caid_manager)
if [[ "${#protocols[@]}" -eq 0 ]]; then
  echo "At least one RUN_* protocol must be enabled" >&2
  exit 2
fi

for protocol in "${protocols[@]}"; do
  args=(
    "$PYTHON_BIN" run_pr_hard.py
    --task_id pr-hard:apache-tvm-20073
    --protocol "$protocol"
    --model "$MODEL"
    --subagent_model "$SUBAGENT_MODEL"
    --runtime_root "$RUNTIME_ROOT"
    --runtime_backend "$RUNTIME_BACKEND"
    --run_id "$RUN_ID"
  )
  [[ -n "$RUNTIME_IMAGE" ]] && args+=(--runtime_image "$RUNTIME_IMAGE")
  [[ "$DRY_RUN" == "1" ]] && args+=(--dry_run True)
  echo "[PR-hard 20073] protocol=$protocol run_id=$RUN_ID model=$MODEL"
  "${args[@]}"
done
