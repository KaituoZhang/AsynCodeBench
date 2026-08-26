from pathlib import Path
import subprocess

import pytest

from run_pr_hard import _candidate_preflight, _execution_profile
from tasks.pr_hard import (
    PrHardConfig,
    PrHardTask,
    build_python_wrapper,
    validate_container_mount_root,
)


def test_needs_revision_candidate_is_blocked_before_execution() -> None:
    with pytest.raises(RuntimeError, match="qualification preflight refused"):
        _candidate_preflight("pr-hard:apache-tvm-19605", "async_private")


def test_qualified_candidate_and_standard_100_profile_are_selected() -> None:
    candidate, qualification, failures = _candidate_preflight(
        "pr-hard:apache-tvm-20153", "async_private"
    )
    profile, protocol = _execution_profile("async_private")
    assert failures == []
    assert candidate["qualification_status"] == "pending_human_review"
    assert qualification["remaining_gates"] == ["human_review"]
    assert profile["profile_id"] == "asyncodebench-v0.3-standard-100"
    assert protocol["manager_max_iterations"] == 100
    assert protocol["subagent_max_iterations"] == 100


def test_20153_runtime_exposes_both_public_overlays(tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    (runtime_root / "seed").mkdir(parents=True)
    (runtime_root / "env").mkdir()
    task = PrHardTask(
        PrHardConfig(
            task_id="pr-hard:apache-tvm-20153",
            runtime_root=str(runtime_root),
        )
    )
    task_data = task.load_task_data()
    assert len(task_data["overlays"]) == 2
    assert task_data["overlays"] == task.curated_task["overlays"]


def test_runtime_mount_root_must_be_readable_by_container_user(tmp_path) -> None:
    seed = tmp_path / "seed"
    seed.mkdir(mode=0o700)
    with pytest.raises(PermissionError, match="chmod 0755"):
        validate_container_mount_root(seed)

    seed.chmod(0o755)
    validate_container_mount_root(seed)


def test_python_wrapper_resolves_python_from_active_worktree() -> None:
    wrapper = build_python_wrapper("/workspace/base_repo", Path("/runtime/env"))
    assert 'git -C "$PWD" rev-parse --show-toplevel' in wrapper
    assert 'PYTHONPATH="$repo_root/python' in wrapper
    assert 'library_root=/workspace/base_repo/build/lib' in wrapper
    assert "PYTHONPATH=/workspace/base_repo/python" not in wrapper


def test_python_wrapper_uses_worktree_python_and_base_build_lib(tmp_path) -> None:
    base = tmp_path / "base_repo"
    (base / "build" / "lib").mkdir(parents=True)
    worktree = tmp_path / "agent_worktree"
    worktree.mkdir()
    subprocess.run(
        ["git", "init", "-q", str(worktree)], check=True, capture_output=True
    )
    environment = tmp_path / "environment"
    python = environment / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$PYTHONPATH\" \"$TVM_LIBRARY_PATH\" "
        "\"$LD_LIBRARY_PATH\"\n",
        encoding="utf-8",
    )
    python.chmod(0o755)
    launcher = tmp_path / "python-wrapper"
    launcher.write_text(build_python_wrapper(str(base), environment), encoding="utf-8")
    launcher.chmod(0o755)

    result = subprocess.run(
        [str(launcher)], cwd=worktree, check=True, capture_output=True, text=True
    )
    lines = result.stdout.splitlines()
    assert lines[0].split(":", 1)[0] == str(worktree / "python")
    assert lines[1] == str(base / "build" / "lib")
    assert lines[2].split(":", 1)[0] == str(base / "build" / "lib")
