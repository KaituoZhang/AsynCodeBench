#!/usr/bin/env bash
# Compatibility alias retained for older automation. The official suite now
# contains 19 tasks because Graphene is preserved only as a historical task.
set -euo pipefail

echo "[Deprecated] run_async_manager_20tasks_env.sh now runs the official 19-task suite." >&2
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/run_async_manager_19tasks_env.sh" "$@"
