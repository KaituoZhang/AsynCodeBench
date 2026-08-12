#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNNER="$ROOT/reproductions/async-swe-agents"
SDK_DIR="$ROOT/reproductions/software-agent-sdk"
SDK_LOCK="$ROOT/reproductions/software-agent-sdk.lock"
BENCHMARK_VENV="${ASYNCODEBENCH_BENCHMARK_VENV:-$ROOT/.venv-benchmark}"
cd "$ROOT"

for command in git uv docker; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Missing required command: $command" >&2
    exit 1
  fi
done

if [[ -n "${ASYNCODEBENCH_PYTHON:-}" ]]; then
  PYTHON_BIN="$ASYNCODEBENCH_PYTHON"
elif ! PYTHON_BIN="$(uv python find 3.12 2>/dev/null)"; then
  echo "Python 3.12 is required. Install it with: uv python install 3.12" >&2
  exit 1
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python interpreter is not executable: $PYTHON_BIN" >&2
  exit 1
fi

readarray -t sdk_values < <(
  "$PYTHON_BIN" - "$SDK_LOCK" <<'PY'
import json
import sys

lock = json.load(open(sys.argv[1], encoding="utf-8"))
print(lock["repository"])
print(lock["commit"])
PY
)
SDK_REPOSITORY="${sdk_values[0]}"
SDK_COMMIT="${sdk_values[1]}"

if [[ ! -d "$SDK_DIR/.git" ]]; then
  echo "[setup] Cloning pinned OpenHands SDK"
  git clone "$SDK_REPOSITORY" "$SDK_DIR"
  git -C "$SDK_DIR" checkout --detach "$SDK_COMMIT"
else
  actual_sdk_commit="$(git -C "$SDK_DIR" rev-parse HEAD)"
  if [[ "$actual_sdk_commit" != "$SDK_COMMIT" ]]; then
    echo "Existing SDK checkout does not match the validated revision." >&2
    echo "expected: $SDK_COMMIT" >&2
    echo "actual:   $actual_sdk_commit" >&2
    echo "Move the existing checkout aside and rerun this script." >&2
    exit 1
  fi
fi

echo "[setup] Creating benchmark validation environment"
"$PYTHON_BIN" -m venv "$BENCHMARK_VENV"
"$BENCHMARK_VENV/bin/python" -m pip install -U pip
"$BENCHMARK_VENV/bin/python" -m pip install -e "$ROOT[dev]"

echo "[setup] Creating agent runner environment"
uv sync --frozen --extra dev --project "$RUNNER"
"$RUNNER/.venv/bin/asyncodebench" tasks >/dev/null

echo "[setup] Checking Docker"
docker info >/dev/null

if [[ "${ASYNCODEBENCH_SETUP_SKIP_TESTS:-0}" != "1" ]]; then
  echo "[setup] Validating benchmark contracts"
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
    "$BENCHMARK_VENV/bin/python" -m pytest -q "$ROOT/tests/contracts"
  echo "[setup] Validating native harness"
  "$RUNNER/.venv/bin/python" -m pytest -q "$RUNNER/tests"
fi

if [[ ! -f "$RUNNER/.env" ]]; then
  cp "$RUNNER/.env.example" "$RUNNER/.env"
  echo "[setup] Created $RUNNER/.env; add your model endpoint and key."
fi

echo "[setup] Ready"
echo "  runner: $RUNNER"
echo "  SDK:    $SDK_DIR ($SDK_COMMIT)"
