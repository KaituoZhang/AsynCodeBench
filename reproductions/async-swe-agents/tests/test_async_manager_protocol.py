from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import core.subagent as subagent_module
import core.workspace as workspace_module
import pytest
from protocols.async_manager import LEGACY_POLICY, POLICY, PROTOCOL
from protocols.async_manager.campaign import trajectory_metrics
from protocols.async_manager.checkpoint_bridge import online_checkpoint_bridge
from protocols.async_manager.guard import guard_command
from protocols.async_manager.manager import OnlineManager, safe_production_path
from protocols.async_manager.terminal_guard import POLICY as TERMINAL_POLICY
from protocols.async_manager.terminal_guard import command as terminal_guard_command
from run_async_manager import (
    FROZEN_BASE_REVISION,
    assert_legacy_execution_unchanged,
    assert_protocol_sources_clean,
    async_manager_profile,
    prefer_worktree_python_for_pr_hard,
)


class CommandResult:
    def __init__(self, process):
        self.exit_code = process.returncode
        self.stdout = process.stdout
        self.stderr = process.stderr


class LocalWorkspace:
    def execute_command(self, command, timeout=60):
        process = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        return CommandResult(process)


class FakeTask:
    deny_agent_network = False

    @staticmethod
    def _clean_transient_test_artifacts(_workspace, _path):
        return None


def git(directory: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(directory), *arguments], text=True
    ).strip()


def initialize_repository(path: Path) -> str:
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    git(path, "config", "user.name", "test")
    git(path, "config", "user.email", "test@example.com")
    (path / "pkg").mkdir()
    (path / "pkg" / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    git(path, "add", ".")
    git(path, "commit", "-qm", "base")
    return git(path, "rev-parse", "HEAD")


def make_rebased_consumer_worktree(
    tmp_path: Path, consumer_changes: dict[str, str]
) -> tuple[Path, Path, str]:
    repository = tmp_path / "repository"
    initialize_repository(repository)
    producer = repository / "pkg" / "producer.py"
    producer.write_text("PRODUCER = 1\n", encoding="utf-8")
    git(repository, "add", "pkg/producer.py")
    git(repository, "commit", "-qm", "integrate producer")

    worktree = tmp_path / "consumer-worktree"
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "worktree",
            "add",
            "-b",
            "consumer",
            str(worktree),
            "HEAD",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    for relative_path, contents in consumer_changes.items():
        path = worktree / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
    git(worktree, "add", ".")
    git(worktree, "commit", "-qm", "consumer contribution")
    return repository, worktree, git(worktree, "rev-parse", "HEAD")


def run_hook(command: str, event: dict) -> dict:
    result = subprocess.run(
        command,
        shell=True,
        input=json.dumps(event),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def test_profile_is_official_and_pins_frozen_base():
    profile = async_manager_profile()
    assert profile["protocol"] == PROTOCOL
    assert profile["policy"] == POLICY
    assert profile["base_protocol"] == LEGACY_POLICY
    assert profile["official_five_protocol_aggregate"] is True
    assert len(FROZEN_BASE_REVISION) == 40


def test_prompt_templates_render_without_treating_json_as_format_fields():
    prompt_path = (
        Path(__file__).resolve().parents[1]
        / "protocols"
        / "async_manager"
        / "prompts.json"
    )
    prompts = json.loads(prompt_path.read_text(encoding="utf-8"))
    rendered = prompts["assign_task"].format(
        engineer_id="engineer_1",
        completed_round=1,
        max_rounds=2,
        task_status="success",
        completed_task_summary="artifact",
        running_agents_summary="none",
        idle_agents_summary="engineer_2",
        inactive_agents_summary="none",
        finished_agents_summary="engineer_1",
    )
    payload = json.loads(rendered.split("Return only:\n", 1)[1])
    assert payload == {
        "assign_task": {"reasoning": "decision rationale", "assignments": []}
    }


def test_campaign_trajectory_metrics_use_only_integrated_states():
    def checkpoint(step, passed, workspace_kind="integrated_workspace"):
        return {
            "logical_step": step,
            "workspace_kind": workspace_kind,
            "dependency_results": [
                {
                    "dependency_id": "edge",
                    "groups": {"integrated": {"passed": passed}},
                }
            ],
        }

    metrics = trajectory_metrics(
        [
            checkpoint(1, True, "agent_workspace"),
            checkpoint(2, False),
            checkpoint(3, True),
            checkpoint(4, False),
            checkpoint(5, True),
        ]
    )
    edge = metrics["dependencies"][0]
    assert metrics["checkpoint_count"] == 4
    assert metrics["ADPR"] == 1.0
    assert edge["DRS"] == 2
    assert edge["SCS"] == 4
    assert edge["RC"] == 1
    assert edge["RC_normalized"] == 1 / 3


def test_existing_protocol_implementation_paths_are_unchanged():
    root = Path(__file__).resolve().parents[3]
    assert_legacy_execution_unchanged(root)


def test_source_preflight_returns_auditable_clean_state(tmp_path, monkeypatch):
    repository = tmp_path / "repository"
    revision = initialize_repository(repository)
    source = repository / "pkg" / "module.py"
    monkeypatch.setattr("run_async_manager.protocol_sources", lambda: [source])

    state = assert_protocol_sources_clean(repository)

    assert state == {
        "schema_version": "async-manager-harness-source-state-v1",
        "clean": True,
        "verification": "runtime_preflight_v1",
        "revision": revision,
        "checked_paths": ["pkg/module.py"],
    }

    source.write_text("VALUE = 2\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="protocol source is uncommitted"):
        assert_protocol_sources_clean(repository)


def test_async_manager_scope_ignores_stale_inherited_producer_paths(tmp_path):
    repository, worktree, commit = make_rebased_consumer_worktree(
        tmp_path, {"pkg/consumer.py": "CONSUMER = 1\n"}
    )
    manager = OnlineManager.__new__(OnlineManager)
    manager.workspace = LocalWorkspace()
    manager.task = FakeTask()
    manager.repo_dir = str(repository)
    result = SimpleNamespace(
        branch_name="consumer",
        commit_hash=commit,
        worktree_path=str(worktree),
        # This cumulative adapter field is intentionally stale after rebase.
        files_modified=["pkg/producer.py", "pkg/consumer.py"],
    )

    assert manager.committed_and_uncommitted_paths(result) == ["pkg/consumer.py"]


def test_async_manager_scope_keeps_true_out_of_scope_consumer_edits(tmp_path):
    repository, worktree, commit = make_rebased_consumer_worktree(
        tmp_path,
        {
            "pkg/consumer.py": "CONSUMER = 1\n",
            "pkg/producer.py": "PRODUCER = 2\n",
        },
    )
    manager = OnlineManager.__new__(OnlineManager)
    manager.workspace = LocalWorkspace()
    manager.task = FakeTask()
    manager.repo_dir = str(repository)
    result = SimpleNamespace(
        branch_name="consumer",
        commit_hash=commit,
        worktree_path=str(worktree),
        files_modified=["pkg/producer.py", "pkg/consumer.py"],
    )

    assert manager.committed_and_uncommitted_paths(result) == [
        "pkg/consumer.py",
        "pkg/producer.py",
    ]


def test_async_manager_is_registered_as_a_public_protocol():
    from asyncodebench_harness.protocol_registry import (
        SUPPORTED_PROTOCOLS,
        load_protocol_registry,
    )
    from run_asyncodebench import SUPPORTED_PROTOCOLS as RUNNER_PROTOCOLS

    registry = load_protocol_registry()
    assert PROTOCOL in SUPPORTED_PROTOCOLS
    assert PROTOCOL in RUNNER_PROTOCOLS
    assert registry["protocols"][PROTOCOL]["official"] is True
    assert registry["protocols"][PROTOCOL]["scenario_source_protocol"] == "caid_manager"


def test_phase_guard_allows_only_scoped_intervention_edits(tmp_path):
    root = tmp_path / "manager"
    root.mkdir()
    (root / "pkg").mkdir()
    (root / "tests").mkdir()
    mode = tmp_path / "mode"
    mode.write_text("observe\n", encoding="utf-8")
    command = guard_command(str(root), str(mode), ["pkg"])
    event = {
        "tool_name": "file_editor",
        "tool_input": {"command": "create", "path": "pkg/new.py"},
    }
    denied = run_hook(command, event)
    assert denied["decision"] == "deny"
    assert "explicit intervention" in denied["reason"]

    mode.write_text("intervene\n", encoding="utf-8")
    assert run_hook(command, event)["decision"] == "allow"
    undo = dict(event)
    undo["tool_input"] = {"command": "undo_edit", "path": "pkg/new.py"}
    assert run_hook(command, undo)["decision"] == "allow"
    protected = run_hook(
        command,
        {
            "tool_name": "file_editor",
            "tool_input": {"command": "create", "path": "tests/test_new.py"},
        },
    )
    assert protected["decision"] == "deny"
    outside = run_hook(
        command,
        {
            "tool_name": "file_editor",
            "tool_input": {"command": "create", "path": "other/new.py"},
        },
    )
    assert outside["decision"] == "deny"


def test_terminal_denial_identifies_online_manager_policy():
    denied = run_hook(
        terminal_guard_command(),
        {"tool_name": "terminal", "tool_input": {"command": "touch pkg/new.py"}},
    )
    assert denied["decision"] == "deny"
    assert TERMINAL_POLICY in denied["reason"]
    assert "online-manager terminal policy" in denied["reason"]


def test_safe_production_path_rejects_control_plane_paths():
    scopes = ["pkg", "src/runtime"]
    assert safe_production_path("pkg/module.py", scopes)
    assert safe_production_path("src/runtime/engine.py", scopes)
    assert not safe_production_path("tests/test_module.py", scopes)
    assert not safe_production_path("../pkg/module.py", scopes)
    assert not safe_production_path("other/module.py", scopes)


def test_online_manager_uses_worktree_aware_python_for_pr_hard_runtime():
    class Workspace:
        def __init__(self):
            self.commands = []

        def execute_command(self, command, timeout=60):
            self.commands.append((command, timeout))
            return SimpleNamespace(exit_code=0, stdout="tvm.py\n", stderr="")

    class Task:
        def __init__(self):
            self.refresh_calls = []

        def refresh_source_build(self, workspace, path):
            self.refresh_calls.append((workspace, path))
            return {"status": "passed", "output_excerpt": ""}

    manager = OnlineManager.__new__(OnlineManager)
    manager.task = Task()
    manager.workspace = Workspace()
    manager.manager_worktree = "/workspace/async-manager-test"
    manager.log = lambda _message: None

    manager._prepare_manager_worktree_runtime()

    assert manager.task.refresh_calls == [(manager.workspace, manager.manager_worktree)]
    command, timeout = manager.workspace.commands[-1]
    assert "cd /workspace/async-manager-test" in command
    assert "/usr/local/bin/python -c" in command
    assert timeout == 120


def test_online_manager_stops_before_import_when_private_build_fails():
    class Task:
        @staticmethod
        def refresh_source_build(_workspace, _path):
            return {"status": "build_failed", "output_excerpt": "compiler error"}

    manager = OnlineManager.__new__(OnlineManager)
    manager.task = Task()
    manager.workspace = SimpleNamespace()
    manager.manager_worktree = "/workspace/async-manager-test"
    manager.log = lambda _message: None

    try:
        manager._prepare_manager_worktree_runtime()
    except RuntimeError as error:
        assert "private-worktree source build failed" in str(error)
        assert "compiler error" in str(error)
    else:
        raise AssertionError("expected manager runtime preparation to fail")


def test_async_manager_pr_hard_path_covers_all_container_python_calls():
    task = SimpleNamespace(environment_path=Path("/opt/asyncodebench/runtime/env"))
    assert "PATH" not in workspace_module.NONINTERACTIVE_PAGER_ENV

    with prefer_worktree_python_for_pr_hard(task):
        path = workspace_module.NONINTERACTIVE_PAGER_ENV["PATH"].split(":")
        assert path[0] == "/usr/local/bin"
        assert path[1] == "/opt/asyncodebench/runtime/env/bin"

    assert "PATH" not in workspace_module.NONINTERACTIVE_PAGER_ENV


def test_async_manager_core_task_does_not_change_container_path():
    before = dict(workspace_module.NONINTERACTIVE_PAGER_ENV)
    with prefer_worktree_python_for_pr_hard(SimpleNamespace()):
        assert before == workspace_module.NONINTERACTIVE_PAGER_ENV
    assert before == workspace_module.NONINTERACTIVE_PAGER_ENV


def test_terminal_session_recovery_preserves_logical_manager_accounting(monkeypatch):
    class Conversation:
        closed = False

        def close(self):
            self.closed = True

    previous = Conversation()
    manager = OnlineManager.__new__(OnlineManager)
    manager.conversation_needs_reset = True
    manager.conversation = previous
    manager.retired_conversations = []
    manager.conversation_mode = "multi_agent"
    manager.recovered_conversation_metrics = {
        "cost": 1.0,
        "prompt_tokens": 2,
        "completion_tokens": 3,
        "total_tokens": 5,
    }
    manager.log = lambda _message: None
    setup_modes = []
    manager.setup = lambda mode: setup_modes.append(mode)
    monkeypatch.setattr(
        "protocols.async_manager.manager.extract_conversation_metrics",
        lambda _conversation: {
            "cost": 0.5,
            "prompt_tokens": 10,
            "completion_tokens": 4,
            "total_tokens": 14,
        },
    )

    manager.ensure_usable_conversation()

    assert previous.closed is True
    assert manager.retired_conversations == [previous]
    assert setup_modes == ["multi_agent"]
    assert manager.recovered_conversation_metrics == {
        "cost": 1.5,
        "prompt_tokens": 12,
        "completion_tokens": 7,
        "total_tokens": 19,
    }


def test_checkpoint_bridge_preserves_order_and_adds_only_accepted_state(monkeypatch):
    calls = []

    def writer(**kwargs):
        calls.append(dict(kwargs))
        return {
            "checkpoint_id": kwargs["checkpoint_id"],
            "logical_step": kwargs["logical_step"],
        }

    monkeypatch.setattr(subagent_module, "write_dependency_probe_checkpoint", writer)

    class Manager:
        task = SimpleNamespace(refresh_source_build=None)
        workspace = object()
        repo_dir = "/workspace/repo"

        def consume_integration_event(self, checkpoint):
            assert checkpoint is None  # consumed before checkpoint I/O
            return {"specialist_checkpoint": checkpoint}

        def intervene(self, _event):
            return {
                "accepted": True,
                "sequence": 1,
                "manager_commit": "manager-commit",
            }

        def current_head(self):
            return "manager-commit"

        def finalize_intervention_record(self, record, checkpoint):
            self.record = record
            self.checkpoint = checkpoint

    manager = Manager()
    OnlineManager.active_instance = manager
    with online_checkpoint_bridge():
        subagent_module.write_dependency_probe_checkpoint(
            checkpoint_id="agent_artifact:engineer_1:round1",
            checkpoint_type="agent_artifact",
            logical_step=1,
            output_dir="/tmp/out",
            repo_name="repo",
            workspace=object(),
            workspace_path="/workspace/agent",
        )
        subagent_module.write_dependency_probe_checkpoint(
            checkpoint_id="integration_after_merge:engineer_1:round1",
            checkpoint_type="integration_after_merge",
            logical_step=2,
            output_dir="/tmp/out",
            repo_name="repo",
            workspace=object(),
            workspace_path="/workspace/repo",
            task_id="task",
            artifact_version="specialist-commit",
        )
        subagent_module.write_dependency_probe_checkpoint(
            checkpoint_id="agent_artifact:engineer_2:round1",
            checkpoint_type="agent_artifact",
            logical_step=3,
            output_dir="/tmp/out",
            repo_name="repo",
            workspace=object(),
            workspace_path="/workspace/agent2",
        )

    assert [call["logical_step"] for call in calls] == [1, 2, 3, 4]
    assert calls[2]["checkpoint_type"] == "integration_after_manager_intervention"
    assert calls[2]["workspace_kind"] == "integrated_workspace"
    assert (
        manager.checkpoint["checkpoint_id"]
        == "integration_after_manager_intervention:1"
    )
    assert subagent_module.write_dependency_probe_checkpoint is writer
    assert OnlineManager.active_instance is None


@pytest.mark.parametrize(
    ("validation_passed", "expected_status"),
    [(True, "accepted"), (False, "validation_rejected")],
)
def test_online_manager_gates_real_scoped_patch(
    tmp_path, monkeypatch, validation_passed, expected_status
):
    repository = tmp_path / "repo"
    base = initialize_repository(repository)
    manager_worktree = tmp_path / "manager-worktree"
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "worktree",
            "add",
            "--detach",
            str(manager_worktree),
            base,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    output = tmp_path / "output"
    output.mkdir()
    mode = tmp_path / "mode"
    mode.write_text("observe\n", encoding="utf-8")

    manager = OnlineManager.__new__(OnlineManager)
    manager.workspace = LocalWorkspace()
    manager.task = FakeTask()
    manager.config = SimpleNamespace(output_dir=str(output), manager_max_iterations=10)
    manager.output_logger = None
    manager.repo_dir = str(repository)
    manager.manager_worktree = str(manager_worktree)
    manager.manager_mode_file = str(mode)
    manager.manager_scopes = ["pkg"]
    manager.intervention_prompt = "Evidence:\n{event_json}"
    manager.intervention_sequence = 0
    manager.intervention_cost = 0.0
    manager.intervention_tokens = 0
    manager.intervention_duration = 0.0
    manager.accepted_interventions = 0
    manager.intervention_records = []
    manager.review_total_cost = 0.0
    manager.review_total_tokens = 0
    manager.review_total_time = 0.0
    manager.candidate_patch_validation = {"enabled": True}
    manager.conversation = SimpleNamespace(state=SimpleNamespace(events=[]))
    manager.ensure_usable_conversation = lambda: None
    manager.send_message = lambda _prompt: None

    def run_active():
        (manager_worktree / "pkg" / "module.py").write_text(
            "VALUE = 2\n", encoding="utf-8"
        )

    manager.run_active_conversation = run_active
    validation_calls = []

    def validate_candidate(**kwargs):
        validation_calls.append(kwargs)
        return {
            "required": True,
            "passed": validation_passed,
            "completion_signal": False,
        }

    manager._validate_candidate_patch = validate_candidate
    monkeypatch.setattr(
        "protocols.async_manager.manager.extract_conversation_metrics",
        lambda _conversation: {"cost": 0.0, "total_tokens": 0},
    )
    monkeypatch.setattr(
        "protocols.async_manager.manager.count_llm_iterations", lambda _events: 0
    )
    event = {
        "subagent_result": SimpleNamespace(
            engineer_id="engineer_1",
            task_id="producer",
            round_num=1,
            success=False,
            error="scope rejected",
            commit_hash=None,
            files_modified=["pkg/module.py"],
            git_diff="",
        ),
        "collect_result": {
            "merged": False,
            "merge_method": "scope_rejected",
            "merge_message": "rejected",
            "review_notes": "rejected",
            "conflict_files": [],
        },
        "specialist_checkpoint": {
            "checkpoint_id": "integration_after_merge:engineer_1:round1",
            "logical_step": 2,
            "dependency_results": [],
        },
    }
    record = manager.intervene(event)
    assert record["status"] == expected_status
    assert record["accepted"] is validation_passed
    assert record["candidate_validation"]["passed"] is validation_passed
    assert validation_calls[0]["changed"] == ["pkg/module.py"]
    expected_value = "VALUE = 2" if validation_passed else "VALUE = 1"
    assert git(repository, "show", "HEAD:pkg/module.py") == expected_value
    if validation_passed:
        assert git(repository, "rev-parse", "HEAD") != base
    else:
        assert git(repository, "rev-parse", "HEAD") == base
    assert not git(repository, "status", "--porcelain")
    assert (output / record["patch"]).is_file()
    assert mode.read_text(encoding="utf-8").strip() == "observe"


def test_iteration_limited_candidate_passes_without_finish_when_no_regression(
    tmp_path,
):
    output = tmp_path / "output"
    output.mkdir()
    metrics = tmp_path / "metrics.json"
    metrics.write_text(
        json.dumps(
            {
                "dependency_points": [
                    {
                        "dependency_id": "dep",
                        "producer_subproblem": "producer",
                        "consumer_subproblem": "consumer",
                        "producer_files": ["pkg/module.py"],
                        "consumer_files": ["pkg/consumer.py"],
                        "integrated_probe_tests": ["tests/test_pkg.py::test_dep"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    patch = "diff --git a/pkg/module.py b/pkg/module.py\n"
    manager = OnlineManager.__new__(OnlineManager)
    manager.config = SimpleNamespace(output_dir=str(output))
    manager.task = SimpleNamespace(
        manifest_paths={"metrics": metrics},
        refresh_source_build=None,
    )
    manager.manager_worktree = "/workspace/manager"
    manager.candidate_patch_validation = {
        "enabled": True,
        "mode": "affected_dependency_selectors_no_regression",
        "timeout_seconds": 60,
        "max_selectors": 40,
        "require_all_selectors_collected": True,
        "require_no_regression": True,
    }
    manager.active_scenario = lambda: {"assignments": []}
    manager._changed_paths = lambda: ["pkg/module.py"]
    manager._command = lambda _command, timeout=60: patch
    manager.workspace = SimpleNamespace(
        execute_command=lambda *a, **k: SimpleNamespace(exit_code=0)
    )
    manager._run_candidate_dependency_probes = lambda *_args: {
        "exit_code": 0,
        "timed_out": False,
        "selector_results": {
            "tests/test_pkg.py::test_dep": {"status": "passed", "passed": True}
        },
        "summary": {"total": 1, "passed": 1, "failed": 0, "not_collected": 0},
        "output_excerpt": "1 passed",
    }
    event = {
        "specialist_checkpoint": {
            "metrics_manifest": str(metrics),
            "probe_test_results": {
                "tests/test_pkg.py::test_dep": {
                    "status": "passed",
                    "passed": True,
                }
            },
        }
    }

    validation = manager._validate_candidate_patch(
        sequence=1,
        event=event,
        changed=["pkg/module.py"],
        head_before="base",
        patch_sha=hashlib.sha256(patch.encode()).hexdigest(),
        termination_reason="iteration_limit",
    )

    assert validation["passed"] is True
    assert validation["completion_signal"] is False
    assert validation["reason_codes"] == []
    assert (output / validation["artifact"]).is_file()


def test_candidate_validation_rejects_previously_passing_probe_regression(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    metrics = tmp_path / "metrics.json"
    selector = "tests/test_pkg.py::test_dep"
    metrics.write_text(
        json.dumps(
            {
                "dependency_points": [
                    {
                        "dependency_id": "dep",
                        "producer_files": ["pkg/module.py"],
                        "consumer_files": [],
                        "integrated_probe_tests": [selector],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    patch = "candidate patch"
    manager = OnlineManager.__new__(OnlineManager)
    manager.config = SimpleNamespace(output_dir=str(output))
    manager.task = SimpleNamespace(
        manifest_paths={"metrics": metrics},
        refresh_source_build=None,
    )
    manager.manager_worktree = "/workspace/manager"
    manager.candidate_patch_validation = {
        "enabled": True,
        "mode": "affected_dependency_selectors_no_regression",
        "timeout_seconds": 60,
        "max_selectors": 40,
        "require_all_selectors_collected": True,
        "require_no_regression": True,
    }
    manager.active_scenario = lambda: {"assignments": []}
    manager._changed_paths = lambda: ["pkg/module.py"]
    manager._command = lambda _command, timeout=60: patch
    manager._run_candidate_dependency_probes = lambda *_args: {
        "exit_code": 1,
        "timed_out": False,
        "selector_results": {selector: {"status": "failed", "passed": False}},
        "summary": {"total": 1, "passed": 0, "failed": 1, "not_collected": 0},
        "output_excerpt": "1 failed",
    }

    validation = manager._validate_candidate_patch(
        sequence=2,
        event={
            "specialist_checkpoint": {
                "metrics_manifest": str(metrics),
                "probe_test_results": {selector: {"status": "passed", "passed": True}},
            }
        },
        changed=["pkg/module.py"],
        head_before="base",
        patch_sha=hashlib.sha256(patch.encode()).hexdigest(),
        termination_reason="agent_finish",
    )

    assert validation["passed"] is False
    assert validation["completion_signal"] is True
    assert validation["regressions"] == [selector]
    assert "previously_passing_selector_regressed" in validation["reason_codes"]


def test_candidate_probe_parser_handles_parameters_and_missing_selectors():
    results = OnlineManager._probe_selector_results(
        {
            "tests": [
                {
                    "nodeid": "tests/test_pkg.py::test_dep[value]",
                    "outcome": "passed",
                }
            ]
        },
        ["tests/test_pkg.py::test_dep", "tests/test_pkg.py::test_missing"],
    )

    assert results["tests/test_pkg.py::test_dep"] == {
        "status": "passed",
        "passed": True,
    }
    assert results["tests/test_pkg.py::test_missing"] == {
        "status": "not_collected",
        "passed": False,
    }


def test_online_manager_emits_progress_heartbeat_without_touching_execution(
    monkeypatch,
):
    manager = OnlineManager.__new__(OnlineManager)
    messages = []
    calls = []
    manager.log = messages.append
    manager.send_message = lambda prompt: calls.append(("send", prompt))

    def run_active():
        calls.append(("run", None))
        time.sleep(0.045)

    manager.run_active_conversation = run_active
    monkeypatch.setenv("ASYNCODEBENCH_MANAGER_HEARTBEAT_SECONDS", "0.01")
    evidence = {
        "specialist": {"agent_id": "engineer_2", "round": 1},
        "dependency_checkpoint": {
            "checkpoint_id": "integration_after_merge:engineer_2:round1"
        },
    }

    manager._run_intervention_turn_with_heartbeat(3, evidence, "repair")

    assert calls == [("send", "repair"), ("run", None)]
    assert any("Online intervention #3 starting" in item for item in messages)
    assert any("Online intervention #3 still running" in item for item in messages)
    assert any("conversation returned" in item for item in messages)
    assert any("completed results are consumed after" in item for item in messages)


def test_online_manager_does_not_integrate_partial_patch_after_fatal_error(
    tmp_path, monkeypatch
):
    repository = tmp_path / "repo"
    base = initialize_repository(repository)
    manager_worktree = tmp_path / "manager-worktree"
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "worktree",
            "add",
            "--detach",
            str(manager_worktree),
            base,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    output = tmp_path / "output"
    output.mkdir()
    mode = tmp_path / "mode"
    mode.write_text("observe\n", encoding="utf-8")

    manager = OnlineManager.__new__(OnlineManager)
    manager.workspace = LocalWorkspace()
    manager.task = FakeTask()
    manager.config = SimpleNamespace(output_dir=str(output), manager_max_iterations=10)
    manager.output_logger = None
    manager.repo_dir = str(repository)
    manager.manager_worktree = str(manager_worktree)
    manager.manager_mode_file = str(mode)
    manager.manager_scopes = ["pkg"]
    manager.intervention_prompt = "Evidence:\n{event_json}"
    manager.intervention_sequence = 0
    manager.intervention_cost = 0.0
    manager.intervention_tokens = 0
    manager.intervention_duration = 0.0
    manager.accepted_interventions = 0
    manager.intervention_records = []
    manager.review_total_cost = 0.0
    manager.review_total_tokens = 0
    manager.review_total_time = 0.0
    manager.conversation = SimpleNamespace(state=SimpleNamespace(events=[]))
    manager.ensure_usable_conversation = lambda: None
    manager.send_message = lambda _prompt: None

    def fail_after_partial_edit():
        (manager_worktree / "pkg" / "module.py").write_text(
            "VALUE = 999\n", encoding="utf-8"
        )
        manager.last_termination_reason = "provider_or_transport_error"
        raise ConnectionError("provider unavailable")

    manager.run_active_conversation = fail_after_partial_edit
    monkeypatch.setattr(
        "protocols.async_manager.manager.extract_conversation_metrics",
        lambda _conversation: {"cost": 0.0, "total_tokens": 0},
    )
    monkeypatch.setattr(
        "protocols.async_manager.manager.count_llm_iterations", lambda _events: 0
    )
    event = {
        "subagent_result": SimpleNamespace(
            engineer_id="engineer_1",
            task_id="producer",
            round_num=1,
            success=False,
            error="failed",
            commit_hash=None,
            files_modified=[],
            git_diff="",
        ),
        "collect_result": {
            "merged": False,
            "merge_method": "none",
            "merge_message": "failed",
            "review_notes": "failed",
            "conflict_files": [],
        },
        "specialist_checkpoint": {
            "checkpoint_id": "integration_after_merge:engineer_1:round1",
            "logical_step": 2,
            "dependency_results": [],
        },
    }

    record = manager.intervene(event)

    assert record["status"] == "execution_error"
    assert record["accepted"] is False
    assert git(repository, "rev-parse", "HEAD") == base
    assert git(repository, "show", "HEAD:pkg/module.py") == "VALUE = 1"
    assert (output / record["patch"]).is_file()
