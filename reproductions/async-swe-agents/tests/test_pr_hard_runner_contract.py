import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from core.dependency_probes import write_dependency_probe_checkpoint
from protocols.asyncodebench.runner import AsynCodeBenchProtocolRunner
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
    assert candidate["qualification_status"] == "qualified"
    assert qualification["automated_status"] == "passed"
    assert qualification["remaining_gates"] == []
    assert qualification["human_review"]["status"] == "complete_pass"
    assert profile["profile_id"] == "asyncodebench-v0.3-standard-100"
    assert protocol["manager_max_iterations"] == 100
    assert protocol["subagent_max_iterations"] == 100


def test_20107_fanout_candidate_passes_preflight() -> None:
    candidate, qualification, failures = _candidate_preflight(
        "pr-hard:apache-tvm-20107", "async_private"
    )
    assert failures == []
    assert candidate["qualification_status"] == "qualified"
    assert qualification["automated_status"] == "passed"
    assert qualification["remaining_gates"] == []
    assert candidate["execution_eligibility"] == [
        "iterative_single",
        "serial_specialists",
        "async_private",
        "async_message",
    ]


def test_20073_join_candidate_passes_preflight() -> None:
    candidate, qualification, failures = _candidate_preflight(
        "pr-hard:apache-tvm-20073", "async_private"
    )
    assert failures == []
    assert candidate["qualification_status"] == "qualified"
    assert qualification["automated_status"] == "passed"
    assert qualification["remaining_gates"] == []
    assert candidate["execution_eligibility"] == [
        "iterative_single",
        "serial_specialists",
        "async_private",
        "async_message",
    ]


def test_20018_return_chain_candidate_passes_preflight() -> None:
    candidate, qualification, failures = _candidate_preflight(
        "pr-hard:apache-tvm-20018", "async_private"
    )
    assert failures == []
    assert candidate["qualification_status"] == "qualified"
    assert qualification["automated_status"] == "passed"
    assert qualification["remaining_gates"] == []
    assert candidate["execution_eligibility"] == [
        "iterative_single",
        "serial_specialists",
        "async_private",
        "async_message",
    ]


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


def test_20107_runtime_exposes_one_public_overlay_and_three_roles(tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    (runtime_root / "seed").mkdir(parents=True)
    (runtime_root / "env").mkdir()
    task = PrHardTask(
        PrHardConfig(
            task_id="pr-hard:apache-tvm-20107",
            runtime_root=str(runtime_root),
        )
    )
    task_data = task.load_task_data()
    scenario = next(
        item
        for item in task.scenario_manifest["scenarios"]
        if item["execution_mode"] == "async_private"
    )
    assert len(task_data["overlays"]) == 1
    assert task_data["overlays"] == task.curated_task["overlays"]
    assert task.task_manifest["official_result_eligible"] is True
    assert scenario["official_result_eligible"] is True
    assert {item["subproblem_id"] for item in scenario["assignments"]} == {
        "shared_script_signature_core",
        "relax_dependent_signature",
        "tirx_dependent_signature",
    }


def test_20073_runtime_exposes_one_public_overlay_and_three_join_roles(tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    (runtime_root / "seed").mkdir(parents=True)
    (runtime_root / "env").mkdir()
    task = PrHardTask(
        PrHardConfig(
            task_id="pr-hard:apache-tvm-20073",
            runtime_root=str(runtime_root),
        )
    )
    task_data = task.load_task_data()
    scenario = next(
        item
        for item in task.scenario_manifest["scenarios"]
        if item["execution_mode"] == "async_private"
    )
    assert len(task_data["overlays"]) == 1
    assert task_data["overlays"] == task.curated_task["overlays"]
    assert task.task_manifest["official_result_eligible"] is True
    assert scenario["official_result_eligible"] is True
    assert {item["subproblem_id"] for item in scenario["assignments"]} == {
        "irbuilder_active_span_state",
        "source_coordinate_mapping",
        "parser_and_evaluator_span_propagation",
    }


def test_20018_runtime_exposes_one_public_overlay_and_three_chain_roles(tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    (runtime_root / "seed").mkdir(parents=True)
    (runtime_root / "env").mkdir()
    task = PrHardTask(
        PrHardConfig(
            task_id="pr-hard:apache-tvm-20018",
            runtime_root=str(runtime_root),
        )
    )
    task_data = task.load_task_data()
    scenario = next(
        item
        for item in task.scenario_manifest["scenarios"]
        if item["execution_mode"] == "async_private"
    )
    assert len(task_data["overlays"]) == 1
    assert task_data["overlays"] == task.curated_task["overlays"]
    assert task.task_manifest["official_result_eligible"] is True
    assert scenario["official_result_eligible"] is True
    assert {item["subproblem_id"] for item in scenario["assignments"]} == {
        "return_ir_core",
        "return_script_surface",
        "return_lowering_codegen_integration",
    }


def test_20107_qwen_profile_has_one_sequence_slot_per_specialist() -> None:
    profile = (
        Path(__file__).resolve().parents[1]
        / "configs/model_profiles/qwen36-27b.env.example"
    ).read_text(encoding="utf-8")
    prefix = "ASYNCODEBENCH_VLLM_CONFIG_JSON='"
    line = next(item for item in profile.splitlines() if item.startswith(prefix))
    config = json.loads(line.removeprefix(prefix).removesuffix("'"))
    assert config["max_num_seqs"] >= 3


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


class _RecordingWorkspace:
    def __init__(self, exit_codes=None):
        self.commands = []
        self.exit_codes = list(exit_codes or [])

    def execute_command(self, command, timeout):
        self.commands.append((command, timeout))
        exit_code = self.exit_codes.pop(0) if self.exit_codes else 0
        return SimpleNamespace(exit_code=exit_code, stdout="ok", stderr="")


def _pr_hard_task(tmp_path) -> PrHardTask:
    runtime_root = tmp_path / "runtime"
    (runtime_root / "seed").mkdir(parents=True)
    (runtime_root / "env").mkdir()
    return PrHardTask(
        PrHardConfig(
            task_id="pr-hard:apache-tvm-20018",
            runtime_root=str(runtime_root),
            build_cache_root=str(tmp_path / "build-cache"),
        )
    )


def test_pr_hard_build_cache_is_host_backed_and_run_isolated(tmp_path) -> None:
    task = _pr_hard_task(tmp_path)

    config = task.get_workspace_config()

    cache_mount = config["volumes"][-1]
    host_path, container_path, mode = cache_mount.rsplit(":", 2)
    host_root = Path(host_path)
    assert host_root.is_dir()
    assert host_root.parent == tmp_path / "build-cache" / "apache-tvm-20018"
    assert container_path == "/workspace/.asyncodebench-pr-hard-build-cache"
    assert mode == "rw"
    assert host_root.stat().st_mode & 0o777 == 0o777
    assert task.cleanup_build_cache() is True
    assert not host_root.exists()


def test_pr_hard_worktree_is_built_before_runtime_import(tmp_path) -> None:
    task = _pr_hard_task(tmp_path)
    workspace = _RecordingWorkspace()

    result = task.prepare_worktree_runtime(workspace, "/workspace/agent")

    assert result["status"] == "passed"
    assert len(workspace.commands) == 3
    assert "cmake -S . -B build -G Ninja" in workspace.commands[0][0]
    assert "ln -s /workspace/.asyncodebench-pr-hard-build-cache/" in workspace.commands[0][0]
    assert "cmake --build build --parallel" in workspace.commands[1][0]
    assert "python -c" in workspace.commands[2][0]
    assert all("cd /workspace/agent" in command for command, _ in workspace.commands)


def test_pr_hard_worktree_build_failure_prevents_stale_import(tmp_path) -> None:
    task = _pr_hard_task(tmp_path)
    workspace = _RecordingWorkspace(exit_codes=[0, 1])

    with pytest.raises(RuntimeError, match="worktree source build failed"):
        task.prepare_worktree_runtime(workspace, "/workspace/agent")

    assert len(workspace.commands) == 2
    assert "cmake --build build --parallel" in workspace.commands[1][0]


def test_dependency_probe_does_not_run_against_stale_library_after_build_failure(
    tmp_path,
) -> None:
    metrics = tmp_path / "metrics.json"
    metrics.write_text(
        json.dumps(
            {
                "task_id": "pr-hard:apache-tvm-20018",
                "metric_annotation_id": "test",
                "dependency_points": [
                    {
                        "dependency_id": "return-ir-to-script-surface",
                        "producer_agent": "return_core_agent",
                        "consumer_agent": "return_script_agent",
                        "upstream_probe_tests": ["tests/test_return.py::test_core"],
                        "downstream_probe_tests": [],
                        "integrated_probe_tests": ["tests/test_return.py::test_core"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    class _NoCommandWorkspace:
        def execute_command(self, command, timeout):
            raise AssertionError(f"probe unexpectedly executed: {command}")

    checkpoint = write_dependency_probe_checkpoint(
        workspace=_NoCommandWorkspace(),
        output_dir=tmp_path / "output",
        repo_name="apache-tvm-20018",
        workspace_path="/workspace/agent",
        checkpoint_id="agent_artifact:return_core_agent:round1",
        checkpoint_type="agent_artifact",
        logical_step=1,
        metrics_path=metrics,
        source_build={
            "status": "build_failed",
            "exit_code": 1,
            "output_excerpt": "compiler error",
        },
    )

    assert checkpoint["pytest_summary"] == {
        "total": 1,
        "passed": 0,
        "failed": 0,
        "not_collected": 1,
        "timed_out": 0,
    }
    assert checkpoint["source_build"]["status"] == "build_failed"


def test_worktree_prebuild_time_is_excluded_and_recorded(tmp_path) -> None:
    runner = object.__new__(AsynCodeBenchProtocolRunner)
    runner.worktree_preparation_seconds = 12.5
    runner.workflow_config = SimpleNamespace(output_dir=str(tmp_path))

    assert runner.measured_runtime_seconds(100.0) == 87.5
    timing = json.loads(
        (tmp_path / "infrastructure_timing.json").read_text(encoding="utf-8")
    )
    assert timing == {
        "schema_version": "0.1",
        "raw_protocol_seconds": 100.0,
        "worktree_preparation_seconds": 12.5,
        "reported_protocol_seconds": 87.5,
        "policy": "exclude_deterministic_worktree_source_build_preparation",
    }
