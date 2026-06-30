#!/usr/bin/env bash
# Safe to source from an interactive shell.
#
# Do not enable `set -e` here. This file is intentionally sourced by wrapper
# scripts and sometimes by users in an interactive terminal. If a sourced file
# enables `set -e`, a later failed command can close the user's shell.

_env_script_is_sourced=0
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  _env_script_is_sourced=1
fi

_env_fail() {
  echo "$1" >&2
  if [[ "$_env_script_is_sourced" == "1" ]]; then
    return 1
  fi
  exit 1
}

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE" >&2
  echo "Create it with:" >&2
  echo "  cp .env.example .env" >&2
  echo "Then edit .env with your API settings." >&2
  _env_fail "Environment setup failed."
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

if [[ -z "${LLM_BASE_URL:-}" ]]; then
  _env_fail "LLM_BASE_URL is required in $ENV_FILE"
fi
if [[ -z "${LLM_API_KEY:-}" ]]; then
  _env_fail "LLM_API_KEY is required in $ENV_FILE"
fi
if [[ -z "${LLM_MODEL:-}" ]]; then
  _env_fail "LLM_MODEL is required in $ENV_FILE"
fi

export COMMIT0_DATASET_PATH="${COMMIT0_DATASET_PATH:-data/commit0/commit0_combined}"
export BUILDKIT_PROGRESS="${BUILDKIT_PROGRESS:-plain}"
