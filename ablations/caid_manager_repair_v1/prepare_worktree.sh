#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 <task-name> <destination>" >&2
  echo "Example: $0 portalocker ../AsyncCodeBench-caid-repair-portalocker" >&2
}

if [[ $# -ne 2 ]]; then
  usage
  exit 2
fi

task_name="$1"
destination="$2"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(git -C "$script_dir" rev-parse --show-toplevel)"

case "$task_name" in
  cachetools)
    revision="ddebb7d7b18c12eba63275df4c8b7350af392c69"
    ;;
  deprecated|portalocker|tinydb|wcwidth|requests|simpy|parsel|filesystem_spec|graphene|imapclient|pexpect|python-rsa|cookiecutter)
    revision="3d110b25df70adfe71b8ce06c259336691866377"
    ;;
  marshmallow|flask|apache-tvm-20073|apache-tvm-20107|apache-tvm-20153|apache-tvm-20018)
    revision="6d2d1af74d09acd1376ca68d9df376c4fe5c0416"
    ;;
  *)
    echo "Unknown frozen-ablation task: $task_name" >&2
    usage
    exit 2
    ;;
esac

if [[ -e "$destination" ]]; then
  echo "Destination already exists; refusing to overwrite: $destination" >&2
  exit 1
fi

git -C "$repo_root" cat-file -e "${revision}^{commit}"
git -C "$repo_root" worktree add --detach "$destination" "$revision"

resolved_destination="$(cd "$destination" && pwd)"
checked_out_revision="$(git -C "$resolved_destination" rev-parse HEAD)"

if [[ "$checked_out_revision" != "$revision" ]]; then
  echo "Worktree revision mismatch: expected $revision, got $checked_out_revision" >&2
  exit 1
fi

echo "Prepared historical CAID+Repair harness"
echo "Task: $task_name"
echo "Revision: $revision"
echo "Worktree: $resolved_destination"

if [[ "$task_name" == "apache-tvm-20018" ]]; then
  echo "Policy note: this frozen task already used the read-only manager guard."
else
  echo "Policy note: this frozen task allowed manager-authored repair."
fi

echo "Use the runbook in the detached worktree and select a new RUN_VERSION."
