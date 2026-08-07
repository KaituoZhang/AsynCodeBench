#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

: "${LLM_MODEL:?Load scripts/env.sh or set LLM_MODEL first}"

TASK_ID="${ASYNCCODEBENCH_SMOKE_TASK_ID:-commit0:cachetools}"
RUN_ID="${ASYNCCODEBENCH_SMOKE_RUN_ID:-smoke_v2_$(date -u +%Y%m%dT%H%M%SZ)}"
WORKSPACE_BASE_HOST_PORT="${ASYNCCODEBENCH_SMOKE_BASE_HOST_PORT:-${ASYNCCODEBENCH_WORKSPACE_HOST_PORT:-}}"

unset ASYNCCODEBENCH_DISABLE_CURATED_TASK_SOURCE
unset ASYNCCODEBENCH_DISABLE_CURATED_TASK_CONFIG
unset ASYNCCODEBENCH_DISABLE_MANIFEST_EVALUATOR
unset ASYNCCODEBENCH_DISABLE_AUTO_METRICS

for protocol in single serial_specialists async_private caid_manager; do
  .venv/bin/python run_asynccodebench.py \
    --task_id "$TASK_ID" \
    --protocol "$protocol" \
    --model "$LLM_MODEL" \
    --max_iterations 2 \
    --sub_iterations 2 \
    --rounds_of_chat 1 \
    --run_id "$RUN_ID" \
    --dry_run
done

protocol_index=0
for protocol in single serial_specialists async_private caid_manager; do
  if [[ -n "$WORKSPACE_BASE_HOST_PORT" ]]; then
    export ASYNCCODEBENCH_WORKSPACE_HOST_PORT=$((WORKSPACE_BASE_HOST_PORT + protocol_index))
    echo "[Smoke] Workspace port: $ASYNCCODEBENCH_WORKSPACE_HOST_PORT"
  fi
  echo "[Smoke] Running $TASK_ID / $protocol"
  .venv/bin/python run_asynccodebench.py \
    --task_id "$TASK_ID" \
    --protocol "$protocol" \
    --model "$LLM_MODEL" \
    --max_iterations 2 \
    --sub_iterations 2 \
    --rounds_of_chat 1 \
    --run_id "$RUN_ID"
  protocol_index=$((protocol_index + 1))
done

echo "[Smoke] Completed all four protocols with run_id=$RUN_ID"
