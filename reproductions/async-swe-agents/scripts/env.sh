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

_env_file_identity="$(readlink -f "$ENV_FILE" 2>/dev/null || printf '%s' "$ENV_FILE")"
if [[ "${ASYNCODEBENCH_ENV_LOADED_FILE:-}" != "$_env_file_identity" \
      || "${ASYNCODEBENCH_FORCE_ENV_RELOAD:-0}" == "1" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  export ASYNCODEBENCH_ENV_LOADED_FILE="$_env_file_identity"
fi
unset _env_file_identity

# Keep existing private env files usable after the project rename. New examples
# and all runtime code use ASYNCODEBENCH_*; the old prefix is read-only
# compatibility and should not be used in new configurations.
_legacy_asyncodebench_vars=( $(compgen -A variable ASYNCCODEBENCH_ || true) )
if [[ "${#_legacy_asyncodebench_vars[@]}" -gt 0 ]]; then
  for _legacy_name in "${_legacy_asyncodebench_vars[@]}"; do
    _canonical_name="ASYNCODEBENCH_${_legacy_name#ASYNCCODEBENCH_}"
    if [[ -z "${!_canonical_name+x}" ]]; then
      printf -v "$_canonical_name" '%s' "${!_legacy_name}"
      export "$_canonical_name"
    fi
  done
  echo "Warning: $ENV_FILE uses legacy ASYNCCODEBENCH_* variables; rename them to ASYNCODEBENCH_*." >&2
fi
unset _legacy_asyncodebench_vars _legacy_name _canonical_name

export ASYNCODEBENCH_ROOT="${ASYNCODEBENCH_ROOT:-$(cd "$REPO_ROOT/../.." && pwd)}"

if [[ -z "${LLM_BASE_URL:-}" ]]; then
  _env_fail "LLM_BASE_URL is required in $ENV_FILE"
fi
if [[ -z "${LLM_API_KEY:-}" ]]; then
  _env_fail "LLM_API_KEY is required in $ENV_FILE"
fi
if [[ -z "${LLM_MODEL:-}" ]]; then
  _env_fail "LLM_MODEL is required in $ENV_FILE"
fi

export BUILDKIT_PROGRESS="${BUILDKIT_PROGRESS:-plain}"
