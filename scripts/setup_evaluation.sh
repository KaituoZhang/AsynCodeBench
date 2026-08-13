#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNNER="$ROOT/reproductions/async-swe-agents"
SDK_DIR="$ROOT/reproductions/software-agent-sdk"
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

if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 12))'; then
  echo "The native runner requires Python 3.12 exactly: $PYTHON_BIN" >&2
  exit 1
fi

echo "[setup] Materializing the locked OpenHands runtime source"
"$PYTHON_BIN" "$ROOT/scripts/materialize_openhands_sdk.py" --require-clean

echo "[setup] Creating benchmark validation environment"
"$PYTHON_BIN" -m venv "$BENCHMARK_VENV"
"$BENCHMARK_VENV/bin/python" -m pip install -U pip
"$BENCHMARK_VENV/bin/python" -m pip install -e "$ROOT[dev]"

echo "[setup] Creating agent runner environment"
uv sync --frozen --extra dev --python "$PYTHON_BIN" --project "$RUNNER"
"$RUNNER/.venv/bin/python" \
  "$ROOT/scripts/check_openhands_runtime_consistency.py" --require-clean
"$RUNNER/.venv/bin/python" \
  "$ROOT/scripts/smoke_openhands_event_roundtrip.py"
"$RUNNER/.venv/bin/asyncodebench" tasks >/dev/null

echo "[setup] Checking Docker"
docker info >/dev/null

if [[ "${ASYNCODEBENCH_SETUP_SKIP_TESTS:-0}" != "1" ]]; then
  echo "[setup] Materializing pinned contract-test repositories"
  "$BENCHMARK_VENV/bin/python" \
    "$ROOT/scripts/materialize_contract_test_repositories.py"
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
echo "  SDK:    $SDK_DIR"
