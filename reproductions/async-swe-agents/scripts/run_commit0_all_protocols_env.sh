#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# shellcheck source=scripts/env.sh
source scripts/env.sh

repo="${1:?Usage: scripts/run_commit0_all_protocols_env.sh <repo>}"
model_tag="${MODEL_TAG:?MODEL_TAG is required}"
run_version="${RUN_VERSION:?RUN_VERSION is required}"
max_subagents="${MAX_SUBAGENTS:?MAX_SUBAGENTS is required}"

single_iterations="${SINGLE_ITERATIONS:-30}"
specialist_iterations="${SPECIALIST_ITERATIONS:-30}"
caid_manager_iterations="${CAID_MANAGER_ITERATIONS:-30}"
caid_sub_iterations="${CAID_SUB_ITERATIONS:-30}"
rounds_of_chat="${ROUNDS_OF_CHAT:-2}"
run_single="${RUN_SINGLE:-1}"
run_serial="${RUN_SERIAL:-1}"
run_async_private="${RUN_ASYNC_PRIVATE:-1}"
run_caid="${RUN_CAID:-1}"
workspace_port_wait_seconds="${WORKSPACE_PORT_WAIT_SECONDS:-120}"
workspace_port_strategy="${WORKSPACE_PORT_STRATEGY:-increment}"

for flag_name in run_single run_serial run_async_private run_caid; do
  if [[ "${!flag_name}" != "0" && "${!flag_name}" != "1" ]]; then
    echo "${flag_name^^} must be 0 or 1" >&2
    exit 1
  fi
done

if [[ "$workspace_port_strategy" != "increment" && "$workspace_port_strategy" != "fixed" && "$workspace_port_strategy" != "auto" ]]; then
  echo "WORKSPACE_PORT_STRATEGY must be increment, fixed, or auto" >&2
  exit 1
fi

unset ASYNCODEBENCH_DISABLE_CURATED_TASK_SOURCE
unset ASYNCODEBENCH_DISABLE_CURATED_TASK_CONFIG
unset ASYNCODEBENCH_DISABLE_MANIFEST_EVALUATOR

base_out="${BASE_OUTPUT_DIR:-outputs/repro_commit0/${repo}}"
single_out="${base_out}/${model_tag}_single_i${single_iterations}_${run_version}"
serial_out="${base_out}/${model_tag}_serial_${max_subagents}agents_s${specialist_iterations}_${run_version}"
async_out="${base_out}/${model_tag}_async_private_${max_subagents}agents_s${specialist_iterations}_${run_version}"
caid_out="${base_out}/${model_tag}_caid_multi_${max_subagents}agents_m${caid_manager_iterations}_s${caid_sub_iterations}_${run_version}"

enabled_outputs=()
[[ "$run_single" == "1" ]] && enabled_outputs+=("$single_out")
[[ "$run_serial" == "1" ]] && enabled_outputs+=("$serial_out")
[[ "$run_async_private" == "1" ]] && enabled_outputs+=("$async_out")
[[ "$run_caid" == "1" ]] && enabled_outputs+=("$caid_out")

if [[ "${#enabled_outputs[@]}" -eq 0 ]]; then
  echo "At least one RUN_* protocol flag must be enabled." >&2
  exit 1
fi

for output_dir in "${enabled_outputs[@]}"; do
  if [[ -e "$output_dir" ]]; then
    echo "Refusing to reuse existing output directory: $output_dir" >&2
    echo "Choose a new RUN_VERSION; interrupted directories must remain immutable." >&2
    exit 1
  fi
done

workspace_base_port="${ASYNCODEBENCH_WORKSPACE_HOST_PORT:-}"
if [[ "$workspace_port_strategy" == "auto" ]]; then
  workspace_base_port="$(
    "$REPO_ROOT/.venv/bin/python" scripts/find_free_port_block.py \
      --start "${WORKSPACE_PORT_SCAN_START:-20000}" \
      --end "${WORKSPACE_PORT_SCAN_END:-60000}" \
      --count 4
  )"
  echo "[AllProtocols] Auto-selected workspace ports ${workspace_base_port}-$((workspace_base_port + 3))"
elif [[ -z "$workspace_base_port" && "${ASYNCODEBENCH_WORKSPACE_DOCKER_NETWORK:-}" == "host" ]]; then
  workspace_base_port=8000
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
  "$REPO_ROOT/.venv/bin/python" - "$port" <<'PY' >/dev/null 2>&1
import socket
import sys

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    sock.bind(("0.0.0.0", int(sys.argv[1])))
finally:
    sock.close()
PY
}

wait_for_workspace_port() {
  local workspace_host_port="$1"
  [[ -n "$workspace_host_port" ]] || return 0

  local waited=0
  until workspace_port_is_available "$workspace_host_port"; do
    if (( waited >= workspace_port_wait_seconds )); then
      echo "Workspace port ${workspace_host_port} remained occupied for ${workspace_port_wait_seconds}s." >&2
      echo "Inspect the owning process/container before retrying; do not reuse the output directory." >&2
      return 1
    fi
    if (( waited == 0 )); then
      echo "[AllProtocols] Waiting for workspace port ${workspace_host_port} to be released..."
    fi
    sleep 2
    waited=$((waited + 2))
  done

  if (( waited > 0 )); then
    echo "[AllProtocols] Workspace port ${workspace_host_port} released after ${waited}s."
  fi
}

echo "[AllProtocols] repo=$repo"
echo "[AllProtocols] model=$LLM_MODEL"
echo "[AllProtocols] model_tag=$model_tag"
echo "[AllProtocols] max_subagents=$max_subagents"
echo "[AllProtocols] run_version=$run_version"
echo "[AllProtocols] single_iterations=$single_iterations"
echo "[AllProtocols] specialist_iterations=$specialist_iterations"
echo "[AllProtocols] caid_manager_iterations=$caid_manager_iterations"
echo "[AllProtocols] caid_sub_iterations=$caid_sub_iterations"
echo "[AllProtocols] enabled=single:${run_single},serial:${run_serial},async_private:${run_async_private},caid:${run_caid}"
echo "[AllProtocols] workspace_port_strategy=$workspace_port_strategy"

if [[ "$run_single" == "1" ]]; then
  protocol_workspace_port="$(workspace_port_for_protocol 0)"
  wait_for_workspace_port "$protocol_workspace_port"
  echo "============================================================"
  echo "Single agent (workspace port ${protocol_workspace_port:-dynamic})"
  echo "============================================================"
  ASYNCODEBENCH_WORKSPACE_HOST_PORT="$protocol_workspace_port" \
  MAX_ITERATIONS="$single_iterations" \
  OUTPUT_DIR="$single_out" \
  scripts/run_commit0_single_env.sh "$repo"
fi

if [[ "$run_serial" == "1" ]]; then
  protocol_workspace_port="$(workspace_port_for_protocol 1)"
  wait_for_workspace_port "$protocol_workspace_port"
  echo "============================================================"
  echo "Serial specialists (workspace port ${protocol_workspace_port:-dynamic})"
  echo "============================================================"
  ASYNCODEBENCH_WORKSPACE_HOST_PORT="$protocol_workspace_port" \
  MAX_SUBAGENTS="$max_subagents" \
  SUB_ITERATIONS="$specialist_iterations" \
  OUTPUT_DIR="$serial_out" \
  scripts/run_commit0_serial_env.sh "$repo"
fi

if [[ "$run_async_private" == "1" ]]; then
  protocol_workspace_port="$(workspace_port_for_protocol 2)"
  wait_for_workspace_port "$protocol_workspace_port"
  echo "============================================================"
  echo "Async private (workspace port ${protocol_workspace_port:-dynamic})"
  echo "============================================================"
  ASYNCODEBENCH_WORKSPACE_HOST_PORT="$protocol_workspace_port" \
  MAX_SUBAGENTS="$max_subagents" \
  SUB_ITERATIONS="$specialist_iterations" \
  OUTPUT_DIR="$async_out" \
  scripts/run_commit0_async_private_env.sh "$repo"
fi

if [[ "$run_caid" == "1" ]]; then
  protocol_workspace_port="$(workspace_port_for_protocol 3)"
  wait_for_workspace_port "$protocol_workspace_port"
  echo "============================================================"
  echo "CAID multi-agent (workspace port ${protocol_workspace_port:-dynamic})"
  echo "============================================================"
  ASYNCODEBENCH_WORKSPACE_HOST_PORT="$protocol_workspace_port" \
  MAX_ITERATIONS="$caid_manager_iterations" \
  MAX_SUBAGENTS="$max_subagents" \
  SUB_ITERATIONS="$caid_sub_iterations" \
  ROUNDS_OF_CHAT="$rounds_of_chat" \
  OUTPUT_DIR="$caid_out" \
  scripts/run_commit0_multi_env.sh "$repo"
fi

echo "============================================================"
echo "All selected protocols completed"
echo "============================================================"
printf '%s\n' "${enabled_outputs[@]}"
