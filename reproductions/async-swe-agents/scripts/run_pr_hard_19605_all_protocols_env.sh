#!/usr/bin/env bash
set -euo pipefail

echo "pr-hard:apache-tvm-19605 is blocked with qualification_status=needs_revision." >&2
echo "Its public evidence does not satisfy role-local observability or integration necessity." >&2
echo "Use run_pr_hard_20153_all_protocols_env.sh for the qualified candidate." >&2
exit 2
