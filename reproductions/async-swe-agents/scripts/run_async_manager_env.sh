#!/usr/bin/env bash
# Foreground-only launcher for the additive online Async-Manager protocol.
set -euo pipefail

task_id="${1:?Usage: ENV_FILE=... RUN_ID=... bash scripts/run_async_manager_env.sh TASK [--dry_run]}"
shift
runner_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$runner_root"

env_path="${ENV_FILE:?Set ENV_FILE to the model environment file}"
requested_run_id="${RUN_ID:-async_manager_v1_$(date -u +%Y%m%dT%H%M%S)_$$}"
requested_tag="${MODEL_TAG:-}"
set -a
source "$env_path"
set +a

if [[ "$task_id" != *:* ]]; then
  task_id="asyncodebench:$task_id"
fi

args=(
  "$runner_root/.venv/bin/python"
  "$runner_root/run_async_manager.py"
  --task_id "$task_id"
  --run_id "$requested_run_id"
  --model_tag "${requested_tag:-${MODEL_TAG:-${LLM_MODEL:?Set LLM_MODEL}}}"
)

if [[ "$task_id" == pr-hard:* ]]; then
  args+=(--runtime_backend "${RUNTIME_BACKEND:-container}")
  [[ -z "${RUNTIME_IMAGE:-}" ]] || args+=(--runtime_image "$RUNTIME_IMAGE")
  [[ -z "${PR_HARD_RUNTIME_ROOT:-}" ]] || args+=(--runtime_root "$PR_HARD_RUNTIME_ROOT")
  [[ -z "${PR_HARD_BUILD_CACHE_ROOT:-}" ]] || args+=(--build_cache_root "$PR_HARD_BUILD_CACHE_ROOT")
fi

exec "${args[@]}" "$@"
