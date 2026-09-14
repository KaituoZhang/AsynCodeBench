#!/usr/bin/env bash
# Sequential, restart-safe-by-version launcher for the unified 20-task suite.
set -euo pipefail

runner_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$runner_root"

: "${ENV_FILE:?Set ENV_FILE to the model environment file}"
: "${RUN_ID:?Set one new immutable RUN_ID for this campaign}"

core_tasks=(
  cachetools deprecated portalocker tinydb wcwidth requests simpy parsel
  filesystem_spec marshmallow graphene imapclient pexpect flask python-rsa
  cookiecutter
)
tvm_tasks=(
  pr-hard:apache-tvm-20018
  pr-hard:apache-tvm-20073
  pr-hard:apache-tvm-20107
  pr-hard:apache-tvm-20153
)

case "${TASK_GROUP:-all}" in
  core) tasks=("${core_tasks[@]}") ;;
  tvm) tasks=("${tvm_tasks[@]}") ;;
  all) tasks=("${core_tasks[@]}" "${tvm_tasks[@]}") ;;
  *) echo "TASK_GROUP must be one of: core, tvm, all" >&2; exit 2 ;;
esac

shard_count="${SHARD_COUNT:-1}"
shard_index="${SHARD_INDEX:-0}"
if ! [[ "$shard_count" =~ ^[1-9][0-9]*$ ]]; then
  echo "SHARD_COUNT must be a positive integer" >&2
  exit 2
fi
if ! [[ "$shard_index" =~ ^[0-9]+$ ]] || ((shard_index >= shard_count)); then
  echo "SHARD_INDEX must be an integer in [0, SHARD_COUNT)" >&2
  exit 2
fi

selected_tasks=()
for index in "${!tasks[@]}"; do
  if ((index % shard_count == shard_index)); then
    selected_tasks+=("${tasks[$index]}")
  fi
done
tasks=("${selected_tasks[@]}")
echo "Async-Manager shard $((shard_index + 1))/${shard_count}: ${#tasks[@]} task(s)"

failures=()
for task in "${tasks[@]}"; do
  echo "========== Async-Manager: ${task} =========="
  if ! RUN_ID="$RUN_ID" ENV_FILE="$ENV_FILE" MODEL_TAG="${MODEL_TAG:-}" \
    bash scripts/run_async_manager_env.sh "$task"
  then
    failures+=("$task")
    if [[ "${CONTINUE_ON_ERROR:-1}" != "1" ]]; then
      exit 1
    fi
  fi
done

if ((${#failures[@]})); then
  printf 'Async-Manager failures:' >&2
  printf ' %s' "${failures[@]}" >&2
  printf '\n' >&2
  exit 1
fi
