#!/usr/bin/env bash
set -euo pipefail

RUNNER_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RUNNER_ROOT"

task_input="${1:?Usage: scripts/run_asyncodebench_all_protocols_env.sh <task-or-asyncodebench:task>}"
case "$task_input" in
  asyncodebench:*)
    task="${task_input#asyncodebench:}"
    ;;
  *:*)
    echo "Unsupported task namespace in '$task_input'. Use asyncodebench:<task>; legacy source-task IDs are provenance only." >&2
    exit 2
    ;;
  *)
    task="$task_input"
    ;;
esac
if [[ -z "$task" || "$task" == *:* ]]; then
  echo "Invalid task '$task_input'. Use a task name or asyncodebench:<task>." >&2
  exit 2
fi
task_id="asyncodebench:${task}"

# shellcheck source=scripts/env.sh
source scripts/env.sh

# Keep enough output headroom before the OpenHands history reaches the model's
# total context limit. The resolved value is recorded in run_metadata.json.
if [[ -z "${ASYNCODEBENCH_CONDENSER_MAX_TOKENS:-}" \
      && "${LLM_MAX_INPUT_TOKENS:-}" =~ ^[0-9]+$ \
      && "${LLM_MAX_OUTPUT_TOKENS:-}" =~ ^[0-9]+$ ]]; then
  available_input=$((LLM_MAX_INPUT_TOKENS - LLM_MAX_OUTPUT_TOKENS))
  condenser_budget=$((available_input * 9 / 10))
  if (( available_input <= 0 || condenser_budget <= 0 )); then
    condenser_budget=$((LLM_MAX_INPUT_TOKENS * 3 / 4))
  fi
  export ASYNCODEBENCH_CONDENSER_MAX_TOKENS="$condenser_budget"
fi

model_tag="${MODEL_TAG:?MODEL_TAG is required}"
run_version="${RUN_VERSION_OVERRIDE:-${RUN_VERSION:?RUN_VERSION is required}}"

single_iterations="${SINGLE_ITERATIONS:-100}"
specialist_iterations="${SPECIALIST_ITERATIONS:-100}"
caid_manager_iterations="${CAID_MANAGER_ITERATIONS:-100}"
caid_sub_iterations="${CAID_SUB_ITERATIONS:-100}"
rounds_of_chat="${ROUNDS_OF_CHAT:-2}"
run_single="${RUN_SINGLE:-1}"
run_serial="${RUN_SERIAL:-1}"
run_async_private="${RUN_ASYNC_PRIVATE:-1}"
run_caid="${RUN_CAID:-1}"
run_async_manager="${RUN_ASYNC_MANAGER:-1}"
dry_run="${DRY_RUN:-0}"
workspace_port_strategy="${WORKSPACE_PORT_STRATEGY:-auto}"
workspace_port_wait_seconds="${WORKSPACE_PORT_WAIT_SECONDS:-120}"
python_bin="${PYTHON_BIN:-$RUNNER_ROOT/.venv/bin/python}"

if [[ "$dry_run" == "1" ]]; then
  export LITELLM_LOCAL_MODEL_COST_MAP="${LITELLM_LOCAL_MODEL_COST_MAP:-True}"
fi

for value in "$model_tag" "$run_version"; do
  if [[ ! "$value" =~ ^[A-Za-z0-9_.-]+$ ]]; then
    echo "MODEL_TAG and RUN_VERSION may contain only letters, digits, '.', '_', and '-'." >&2
    exit 1
  fi
done

for flag_name in run_single run_serial run_async_private run_caid run_async_manager dry_run; do
  if [[ "${!flag_name}" != "0" && "${!flag_name}" != "1" ]]; then
    echo "${flag_name^^} must be 0 or 1" >&2
    exit 1
  fi
done

if [[ "$workspace_port_strategy" != "increment" && "$workspace_port_strategy" != "fixed" && "$workspace_port_strategy" != "auto" ]]; then
  echo "WORKSPACE_PORT_STRATEGY must be increment, fixed, or auto" >&2
  exit 1
fi

if [[ ! -x "$python_bin" ]]; then
  echo "Python environment not found at $python_bin; run 'uv sync' first." >&2
  exit 1
fi

if [[ "$dry_run" == "0" ]]; then
  echo "[AsynCodeBench] Verifying locked OpenHands client/server runtime"
  "$python_bin" \
    "$RUNNER_ROOT/../../scripts/check_openhands_runtime_consistency.py" \
    --require-clean
fi

unset ASYNCODEBENCH_DISABLE_CURATED_TASK_SOURCE
unset ASYNCODEBENCH_DISABLE_CURATED_TASK_CONFIG
unset ASYNCODEBENCH_DISABLE_MANIFEST_EVALUATOR

enabled_protocols=()
[[ "$run_single" == "1" ]] && enabled_protocols+=(single)
[[ "$run_serial" == "1" ]] && enabled_protocols+=(serial_specialists)
[[ "$run_async_private" == "1" ]] && enabled_protocols+=(async_private)
[[ "$run_caid" == "1" ]] && enabled_protocols+=(caid_manager)
[[ "$run_async_manager" == "1" ]] && enabled_protocols+=(async_manager)

if [[ "${#enabled_protocols[@]}" -eq 0 ]]; then
  echo "At least one RUN_* protocol flag must be enabled." >&2
  exit 1
fi

base_output="${BASE_OUTPUT_DIR:-outputs/asyncodebench/v0.3/${model_tag}/${task}}"
for protocol in "${enabled_protocols[@]}"; do
  output_dir="${base_output}/${protocol}/${run_version}"
  if [[ "$dry_run" == "0" && -e "$output_dir" ]]; then
    echo "Refusing to reuse existing output directory: $output_dir" >&2
    echo "Choose a new RUN_VERSION; interrupted run directories are immutable." >&2
    exit 1
  fi
done

workspace_base_port="${ASYNCODEBENCH_WORKSPACE_HOST_PORT:-}"
if [[ "$dry_run" == "0" && "$workspace_port_strategy" == "auto" ]]; then
  workspace_base_port="$($python_bin scripts/find_free_port_block.py \
    --start "${WORKSPACE_PORT_SCAN_START:-20000}" \
    --end "${WORKSPACE_PORT_SCAN_END:-60000}" \
    --count 5)"
  echo "[AsynCodeBench] Auto-selected workspace ports ${workspace_base_port}-$((workspace_base_port + 4))"
elif [[ "$dry_run" == "0" && -z "$workspace_base_port" && "${ASYNCODEBENCH_WORKSPACE_DOCKER_NETWORK:-}" == "host" ]]; then
  echo "ASYNCODEBENCH_WORKSPACE_HOST_PORT is required when WORKSPACE_PORT_STRATEGY is not auto and Docker networking is host." >&2
  exit 1
fi

workspace_port_for_protocol() {
  local offset="$1"
  [[ -n "$workspace_base_port" ]] || return 0
  if [[ "$workspace_port_strategy" == "increment" || "$workspace_port_strategy" == "auto" ]]; then
    echo $((workspace_base_port + offset))
  else
    echo "$workspace_base_port"
  fi
}

workspace_port_is_available() {
  local port="$1"
  [[ -n "$port" ]] || return 0
  "$python_bin" -c \
    'import socket, sys; s=socket.socket(); s.bind(("0.0.0.0", int(sys.argv[1]))); s.close()' \
    "$port" >/dev/null 2>&1
}

wait_for_workspace_port() {
  local port="$1"
  [[ -n "$port" ]] || return 0
  local waited=0
  until workspace_port_is_available "$port"; do
    if (( waited >= workspace_port_wait_seconds )); then
      echo "Workspace port ${port} remained occupied for ${workspace_port_wait_seconds}s." >&2
      return 1
    fi
    if (( waited == 0 )); then
      echo "[AsynCodeBench] Waiting for workspace port ${port} to be released..."
    fi
    sleep 2
    waited=$((waited + 2))
  done
}

run_protocol() {
  local protocol="$1"
  local offset="$2"
  local max_iterations="$3"
  local sub_iterations="$4"
  local workspace_port
  workspace_port="$(workspace_port_for_protocol "$offset")"
  [[ "$dry_run" == "1" ]] || wait_for_workspace_port "$workspace_port"

  args=(
    "$python_bin" run_asyncodebench.py
    --task_id "$task_id"
    --protocol "$protocol"
    --model "$LLM_MODEL"
    --max_iterations "$max_iterations"
    --sub_iterations "$sub_iterations"
    --rounds_of_chat "$rounds_of_chat"
    --output_dir "${base_output}/${protocol}/${run_version}"
  )
  if [[ -n "${LLM_SUBAGENT_MODEL:-}" ]]; then
    args+=(--subagent_model "$LLM_SUBAGENT_MODEL")
  fi
  if [[ -n "${ASYNCODEBENCH_AGENT:-}" ]]; then
    args+=(--agent "$ASYNCODEBENCH_AGENT")
  fi
  if [[ -n "${ASYNCODEBENCH_AGENT_IMPORT_PATH:-}" ]]; then
    args+=(--agent_import_path "$ASYNCODEBENCH_AGENT_IMPORT_PATH")
  fi
  if [[ -n "${ASYNCODEBENCH_AGENT_CONFIG_JSON:-}" ]]; then
    args+=(--agent_config_json "$ASYNCODEBENCH_AGENT_CONFIG_JSON")
  fi
  [[ "$dry_run" == "1" ]] && args+=(--dry_run)

  echo "============================================================"
  echo "AsynCodeBench protocol=$protocol task=$task_id workspace_port=${workspace_port:-dynamic}"
  echo "============================================================"
  ASYNCODEBENCH_WORKSPACE_HOST_PORT="$workspace_port" "${args[@]}"
}

echo "[AsynCodeBench] task_id=$task_id"
echo "[AsynCodeBench] model=$LLM_MODEL"
echo "[AsynCodeBench] model_tag=$model_tag"
echo "[AsynCodeBench] run_version=$run_version"
echo "[AsynCodeBench] protocols=${enabled_protocols[*]}"
echo "[AsynCodeBench] Agent counts are loaded from the release scenario manifest."

[[ "$run_single" == "1" ]] && run_protocol single 0 "$single_iterations" "$specialist_iterations"
[[ "$run_serial" == "1" ]] && run_protocol serial_specialists 1 "$specialist_iterations" "$specialist_iterations"
[[ "$run_async_private" == "1" ]] && run_protocol async_private 2 "$specialist_iterations" "$specialist_iterations"
[[ "$run_caid" == "1" ]] && run_protocol caid_manager 3 "$caid_manager_iterations" "$caid_sub_iterations"
[[ "$run_async_manager" == "1" ]] && run_protocol async_manager 4 "$caid_manager_iterations" "$caid_sub_iterations"

echo "[AsynCodeBench] All selected protocols completed."
