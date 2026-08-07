#!/usr/bin/env bash
set -euo pipefail

runner_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$runner_root"
all_protocols_runner="$runner_root/scripts/run_commit0_all_protocols_env.sh"

[[ -x "$all_protocols_runner" ]] || {
  echo "Missing executable protocol runner: $all_protocols_runner" >&2
  exit 1
}

task="${1:?Usage: ENV_FILE=.env.gemma4-... scripts/run_gemma4_task_env.sh <task>}"

case "$task" in
  cachetools|deprecated|portalocker|tinydb|wcwidth) max_subagents=2 ;;
  requests|parsel|filesystem_spec|marshmallow|graphene|imapclient) max_subagents=3 ;;
  simpy|dulwich|pexpect|flask|python-rsa|cookiecutter) max_subagents=4 ;;
  *) echo "Not an official AsyncCodeBench v0.3 task: $task" >&2; exit 1 ;;
esac

# shellcheck source=scripts/env.sh
source scripts/env.sh

# Per-port .env files are often copied before timeout defaults change. Apply the
# Gemma local-serving policy here so a stale env cannot silently restore the
# legacy one-hour CAID deadline.
export ASYNCCODEBENCH_CONVERSATION_RUN_TIMEOUT="${ASYNCCODEBENCH_CONVERSATION_RUN_TIMEOUT:-43200}"
export ASYNCCODEBENCH_REMOTE_TRIGGER_TIMEOUT="${ASYNCCODEBENCH_REMOTE_TRIGGER_TIMEOUT:-30}"
export ASYNCCODEBENCH_REMOTE_POLL_TIMEOUT="${ASYNCCODEBENCH_REMOTE_POLL_TIMEOUT:-3600}"
export ASYNCCODEBENCH_REMOTE_MESSAGE_TIMEOUT="${ASYNCCODEBENCH_REMOTE_MESSAGE_TIMEOUT:-3600}"
export ASYNCCODEBENCH_REMOTE_POLL_INTERVAL="${ASYNCCODEBENCH_REMOTE_POLL_INTERVAL:-5}"
export ASYNCCODEBENCH_REMOTE_START_GRACE_SECONDS="${ASYNCCODEBENCH_REMOTE_START_GRACE_SECONDS:-30}"
export ASYNCCODEBENCH_REMOTE_TERMINAL_CONFIRM_SECONDS="${ASYNCCODEBENCH_REMOTE_TERMINAL_CONFIRM_SECONDS:-30}"

expected_model="openai/google/gemma-4-26B-A4B-it"
[[ "$LLM_MODEL" == "$expected_model" ]] || {
  echo "Expected LLM_MODEL=$expected_model, found $LLM_MODEL" >&2
  exit 1
}
[[ "${LLM_MAX_INPUT_TOKENS:-}" == "131072" ]] || {
  echo "Gemma v2 requires LLM_MAX_INPUT_TOKENS=131072 (OpenHands total context window)" >&2
  exit 1
}
[[ "${LLM_MAX_OUTPUT_TOKENS:-}" == "32768" ]] || {
  echo "Gemma v2 requires LLM_MAX_OUTPUT_TOKENS=32768" >&2
  exit 1
}

uv run python scripts/check_gemma4_server.py \
  --base-url "$LLM_BASE_URL" \
  --model "${expected_model#openai/}" \
  --minimum-version 0.24.0 \
  --minimum-context 163840

model_tag="${MODEL_TAG:-gemma4-26b-a4b-v2}"
run_version="${RUN_VERSION:-officialtmpl_131072_o32768_v05}"

echo "[Gemma4] task=$task agents=$max_subagents endpoint=$LLM_BASE_URL"
echo "[Gemma4] conversation_timeout=${ASYNCCODEBENCH_CONVERSATION_RUN_TIMEOUT}s poll_timeout=${ASYNCCODEBENCH_REMOTE_POLL_TIMEOUT}s"

MODEL_TAG="$model_tag" \
MAX_SUBAGENTS="$max_subagents" \
RUN_VERSION="$run_version" \
SINGLE_ITERATIONS=30 \
SPECIALIST_ITERATIONS=30 \
CAID_MANAGER_ITERATIONS=30 \
CAID_SUB_ITERATIONS=30 \
ROUNDS_OF_CHAT=2 \
"$all_protocols_runner" "$task"
