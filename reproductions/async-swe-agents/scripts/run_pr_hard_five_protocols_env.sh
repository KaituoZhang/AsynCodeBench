#!/usr/bin/env bash
# Foreground launcher for all five official protocols on one TVM task.
set -euo pipefail

runner_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
benchmark_root="$(cd "$runner_root/../.." && pwd)"
cd "$runner_root"

task_input="${1:?Usage: ENV_FILE=... RUN_ID=... scripts/run_pr_hard_five_protocols_env.sh apache-tvm-20xxx}"
case "$task_input" in
  pr-hard:apache-tvm-*) task_id="$task_input" ;;
  apache-tvm-*) task_id="pr-hard:$task_input" ;;
  *) echo "Expected apache-tvm-20018, -20073, -20107, or -20153" >&2; exit 2 ;;
esac
case "$task_id" in
  pr-hard:apache-tvm-20018|pr-hard:apache-tvm-20073|pr-hard:apache-tvm-20107|pr-hard:apache-tvm-20153) ;;
  *) echo "Unsupported official TVM task: $task_id" >&2; exit 2 ;;
esac

# shellcheck source=scripts/env.sh
source scripts/env.sh

task_name="${task_id#pr-hard:}"
run_id="${RUN_ID:-${task_name}-five-$(date -u +%Y%m%dT%H%M%SZ)}"
model="${LLM_MODEL:?LLM_MODEL is required}"
subagent_model="${LLM_SUBAGENT_MODEL:-$model}"
python_bin="${PYTHON_BIN:-$runner_root/.venv/bin/python}"
runtime_root="${PR_HARD_RUNTIME_ROOT:-$benchmark_root/.cache/pr_hard_runtime/v0.4/$task_name}"
build_cache_root="${PR_HARD_BUILD_CACHE_ROOT:-$benchmark_root/.cache/pr_hard_builds/v0.4}"
runtime_backend="${PR_HARD_RUNTIME_BACKEND:-container}"
runtime_image="${PR_HARD_RUNTIME_IMAGE:-}"
dry_run="${DRY_RUN:-0}"

for flag in RUN_SINGLE RUN_SERIAL RUN_ASYNC_PRIVATE RUN_CAID RUN_ASYNC_MANAGER; do
  value="${!flag:-1}"
  if [[ "$value" != "0" && "$value" != "1" ]]; then
    echo "$flag must be 0 or 1" >&2
    exit 2
  fi
done
if [[ ! -x "$python_bin" ]]; then
  echo "Runner environment is missing: $python_bin" >&2
  exit 2
fi
if [[ "$runtime_backend" == "local" ]]; then
  "$benchmark_root/.venv-benchmark/bin/python" \
    "$benchmark_root/scripts/prepare_pr_hard_runtime.py" \
    --task-id "$task_id" --runtime-root "$runtime_root" --check
elif [[ "$runtime_backend" != "container" ]]; then
  echo "PR_HARD_RUNTIME_BACKEND must be container or local" >&2
  exit 2
fi

if [[ "$task_id" == "pr-hard:apache-tvm-20018" && "$dry_run" != "1" ]]; then
  "$python_bin" -c '
import json, os
config = json.loads(os.environ.get("ASYNCODEBENCH_VLLM_CONFIG_JSON", "{}"))
if int(config.get("max_num_seqs", 0)) < 3:
    raise SystemExit("apache-tvm-20018 requires max_num_seqs >= 3")
'
fi
if [[ "$dry_run" != "1" ]]; then
  "$python_bin" "$benchmark_root/scripts/check_openhands_runtime_consistency.py" --require-clean
fi

unset ASYNCODEBENCH_WORKSPACE_HOST_PORT
protocols=()
[[ "${RUN_SINGLE:-1}" == "1" ]] && protocols+=(single)
[[ "${RUN_SERIAL:-1}" == "1" ]] && protocols+=(serial_specialists)
[[ "${RUN_ASYNC_PRIVATE:-1}" == "1" ]] && protocols+=(async_private)
[[ "${RUN_CAID:-1}" == "1" ]] && protocols+=(caid_manager)
[[ "${RUN_ASYNC_MANAGER:-1}" == "1" ]] && protocols+=(async_manager)
if [[ "${#protocols[@]}" -eq 0 ]]; then
  echo "At least one RUN_* protocol must be enabled" >&2
  exit 2
fi

for protocol in "${protocols[@]}"; do
  args=(
    "$python_bin" run_pr_hard.py
    --task_id "$task_id"
    --protocol "$protocol"
    --model "$model"
    --subagent_model "$subagent_model"
    --runtime_root "$runtime_root"
    --build_cache_root "$build_cache_root"
    --runtime_backend "$runtime_backend"
    --run_id "$run_id"
  )
  [[ -z "$runtime_image" ]] || args+=(--runtime_image "$runtime_image")
  [[ "$dry_run" == "1" ]] && args+=(--dry_run True)
  echo "[AsynCodeBench TVM] task=$task_id protocol=$protocol run_id=$run_id"
  "${args[@]}"
done
