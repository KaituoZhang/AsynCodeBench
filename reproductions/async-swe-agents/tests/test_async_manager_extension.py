from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import core.subagent as subagent_module
from async_manager_extension import POLICY, PROTOCOL
from async_manager_extension.campaign import trajectory_metrics
from async_manager_extension.checkpoint_bridge import online_checkpoint_bridge
from async_manager_extension.guard import guard_command
from async_manager_extension.manager import OnlineManager, safe_production_path
from async_manager_extension.terminal_guard import POLICY as TERMINAL_POLICY
from async_manager_extension.terminal_guard import command as terminal_guard_command
from run_async_manager import (
    FROZEN_BASE_REVISION,
    assert_frozen_base_unchanged,
    async_manager_profile,
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


def test_profile_is_additive_and_pins_frozen_base():
    profile = async_manager_profile()
    assert profile["protocol"] == PROTOCOL
    assert profile["policy"] == POLICY
    assert profile["base_protocol"] == "caid_manager"
    assert profile["official_four_protocol_aggregate"] is False
    assert len(FROZEN_BASE_REVISION) == 40


def test_prompt_templates_render_without_treating_json_as_format_fields():
    prompt_path = (
        Path(__file__).resolve().parents[1] / "async_manager_extension" / "prompts.json"
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
    assert_frozen_base_unchanged(root)


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
        "async_manager_extension.manager.extract_conversation_metrics",
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
            assert (
                checkpoint["checkpoint_id"]
                == "integration_after_merge:engineer_1:round1"
            )
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


def test_online_manager_integrates_real_scoped_patch(tmp_path, monkeypatch):
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

    def run_active():
        (manager_worktree / "pkg" / "module.py").write_text(
            "VALUE = 2\n", encoding="utf-8"
        )

    manager.run_active_conversation = run_active
    monkeypatch.setattr(
        "async_manager_extension.manager.extract_conversation_metrics",
        lambda _conversation: {"cost": 0.0, "total_tokens": 0},
    )
    monkeypatch.setattr(
        "async_manager_extension.manager.count_llm_iterations", lambda _events: 0
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
    assert record["status"] == "accepted"
    assert record["accepted"] is True
    assert git(repository, "show", "HEAD:pkg/module.py") == "VALUE = 2"
    assert git(repository, "rev-parse", "HEAD") != base
    assert not git(repository, "status", "--porcelain")
    assert (output / record["patch"]).is_file()
    assert mode.read_text(encoding="utf-8").strip() == "observe"


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
        "async_manager_extension.manager.extract_conversation_metrics",
        lambda _conversation: {"cost": 0.0, "total_tokens": 0},
    )
    monkeypatch.setattr(
        "async_manager_extension.manager.count_llm_iterations", lambda _events: 0
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
