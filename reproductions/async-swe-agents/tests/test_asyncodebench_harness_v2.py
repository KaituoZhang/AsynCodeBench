import base64
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from config import SubAgentResult, WorkflowConfig
from core.asyncodebench_manager import AsynCodeBenchManager
from core.utils import build_delegation_plan, generate_patch
from core.workspace_isolation import (
    build_workspace_guard_hook,
    private_remote_workspace,
    uses_task_specific_workspace_isolation,
    workspace_guard_command,
)
from protocols.asyncodebench.metadata import (
    build_run_metadata,
    write_contract_snapshots,
)
from protocols.asyncodebench.ordering import path_in_scope, topological_assignments
from protocols.asyncodebench.runner import AsynCodeBenchProtocolRunner
from run_asyncodebench import main as run_asyncodebench
from tasks.asyncodebench import AsynCodeBenchConfig, AsynCodeBenchTask
from tasks.commit0 import Commit0Task


def make_task(task_id="asyncodebench:cachetools"):
    return AsynCodeBenchTask(AsynCodeBenchConfig(task_id=task_id))


def test_workspace_isolation_repair_is_scoped_to_20018():
    assert uses_task_specific_workspace_isolation(
        SimpleNamespace(
            task_id="pr-hard:apache-tvm-20018", active_protocol="caid_manager"
        )
    )
    assert not uses_task_specific_workspace_isolation(
        SimpleNamespace(
            task_id="pr-hard:apache-tvm-20018", active_protocol="async_private"
        )
    )
    assert not uses_task_specific_workspace_isolation(
        SimpleNamespace(
            task_id="pr-hard:apache-tvm-20073", active_protocol="caid_manager"
        )
    )
    assert not uses_task_specific_workspace_isolation(
        SimpleNamespace(
            task_id="asyncodebench:cachetools", active_protocol="caid_manager"
        )
    )


def test_20018_patch_export_preserves_final_context_prefix(tmp_path):
    diff = """diff --git a/example.txt b/example.txt
index 422c2b7..0f7bc76 100644
--- a/example.txt
+++ b/example.txt
@@ -1,2 +1,2 @@
-old
+new
 context
"""
    workspace = SimpleNamespace(
        execute_command=lambda *args, **kwargs: SimpleNamespace(
            exit_code=0, stdout=diff, stderr=""
        )
    )

    patch, _ = generate_patch(
        workspace,
        "/workspace/apache-tvm-repo",
        "base",
        [],
        preserve_diff_whitespace=True,
    )
    patch_path = tmp_path / "patch.diff"
    patch_path.write_text(patch, encoding="utf-8")

    parsed = subprocess.run(
        ["git", "apply", "--numstat", str(patch_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert parsed.returncode == 0, parsed.stderr
    assert patch.endswith(" context\n")


def test_benchmark_root_can_be_explicitly_configured(monkeypatch, tmp_path):
    (tmp_path / "manifests").mkdir()
    monkeypatch.setenv("ASYNCODEBENCH_ROOT", str(tmp_path))

    assert Commit0Task._repo_root() == tmp_path


class LocalWorkspace:
    def execute_command(self, command, timeout=30):
        del timeout
        result = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True,
            check=False,
        )
        return SimpleNamespace(
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )


class RecordingWorkspace:
    def __init__(self):
        self.commands = []

    def execute_command(self, command, timeout=30):
        del timeout
        self.commands.append(command)
        return SimpleNamespace(
            exit_code=0,
            stdout="",
            stderr="",
        )


class ChunkedDownloadWorkspace:
    def __init__(self, content):
        self.content = content
        self.commands = []

    def execute_command(self, command, timeout=30):
        del timeout
        self.commands.append(command)
        if command.startswith("stat -c%s"):
            return SimpleNamespace(
                exit_code=0,
                stdout=str(len(self.content)),
                stderr="",
            )
        if command.startswith("dd if="):
            return SimpleNamespace(
                exit_code=0,
                stdout=base64.b64encode(self.content).decode("ascii"),
                stderr="",
            )
        raise AssertionError(f"Unexpected command: {command}")


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def make_git_worktree(tmp_path, changed_paths):
    repo = tmp_path / "main"
    worktree = tmp_path / "agent"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", repo], check=True)
    git(repo, "config", "user.name", "AsynCodeBench Test")
    git(repo, "config", "user.email", "test@example.com")
    for path in ("src/cachetools/keys.py", "src/cachetools/func.py"):
        destination = repo / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("VALUE = 0\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "base")
    base_head = git(repo, "rev-parse", "HEAD")
    git(repo, "branch", "agent_key")
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", str(worktree), "agent_key"],
        check=True,
        capture_output=True,
        text=True,
    )
    for path in changed_paths:
        destination = worktree / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("VALUE = 1\n", encoding="utf-8")
    git(worktree, "add", ".")
    git(worktree, "commit", "-m", "agent artifact")
    return repo, worktree, base_head, git(worktree, "rev-parse", "HEAD")


def make_manager(task, workspace, output_dir, repo_dir):
    config = WorkflowConfig(
        model="test/model",
        max_subagents=2,
        output_dir=str(output_dir),
    )
    manager = AsynCodeBenchManager(
        llm=None,
        workspace=workspace,
        task=task,
        config=config,
        output_logger=None,
        prompts={},
    )
    manager.repo_dir = str(repo_dir)
    return manager


def test_native_task_loads_required_manifests_and_curated_source():
    task = make_task()

    assert task.task_id == "asyncodebench:cachetools"
    assert task.source_task_id == "commit0:cachetools"
    assert len(task.official_tasks) == 16
    assert task.curated_task["base_sha"] == task.task_manifest["upstream_version"]
    assert task.metrics_manifest["task_id"] == task.source_task_id
    assert task.scenario_for("single")["execution_mode"] == "iterative_single"
    assert task.scenario_for("caid_manager")["execution_mode"] == "async_message"


def test_caid_scenario_does_not_fall_back_to_async_private():
    task = make_task()
    task.scenario_manifest["scenarios"] = [
        scenario
        for scenario in task.scenario_manifest["scenarios"]
        if scenario.get("execution_mode") != "async_message"
    ]

    with pytest.raises(ValueError, match="No scenario for protocol='caid_manager'"):
        task.scenario_for("caid_manager")


def test_native_task_rejects_non_official_task():
    with pytest.raises(ValueError, match="not an official"):
        make_task("asyncodebench:fastapi")


def test_native_task_rejects_commit0_namespace():
    with pytest.raises(ValueError, match="Legacy source-task IDs are provenance only"):
        make_task("commit0:cachetools")


def test_native_task_rejects_nested_namespace():
    with pytest.raises(ValueError, match="asyncodebench:<repository>"):
        make_task("asyncodebench:commit0:cachetools")


def test_all_official_tasks_have_native_v2_contracts():
    official_tasks = make_task().official_tasks

    assert len(official_tasks) == 16
    assert "dulwich" not in official_tasks
    for repository in official_tasks:
        task = make_task(f"asyncodebench:{repository}")
        assert task.curated_task.get("base_sha")
        assert task.task_manifest.get("problem_statement")
        assert task.metrics_manifest.get("dependency_points")
        assert task.quality_manifest.get("task_id") == task.source_task_id
        assert {
            scenario.get("execution_mode")
            for scenario in task.scenario_manifest.get("scenarios", [])
        } >= {
            "iterative_single",
            "serial_specialists",
            "async_private",
            "async_message",
        }


def test_native_task_never_falls_back_to_raw_dataset(monkeypatch):
    monkeypatch.setenv("ASYNCODEBENCH_DISABLE_CURATED_TASK_SOURCE", "1")
    task = make_task()

    with pytest.raises(RuntimeError, match="requires curated task source"):
        task.load_task_data()


def test_transient_cleanup_removes_python_bytecode_artifacts():
    task = make_task()
    workspace = RecordingWorkspace()

    task._clean_transient_test_artifacts(workspace, task.get_work_dir())

    assert any("-name __pycache__" in command for command in workspace.commands)
    assert any("-name '*.pyc'" in command for command in workspace.commands)
    assert any("-name '.coverage'" in command for command in workspace.commands)
    assert any("-name .pytest_cache" in command for command in workspace.commands)
    assert any("-name htmlcov" in command for command in workspace.commands)


def test_transient_excludes_apply_to_linked_worktrees(tmp_path):
    repo, worktree, _, _ = make_git_worktree(
        tmp_path, ["src/cachetools/keys.py"]
    )
    task = make_task()
    task._install_transient_test_artifact_excludes(LocalWorkspace(), str(repo))

    generated_paths = [
        worktree / ".coverage",
        worktree / ".pytest_cache" / "state",
        worktree / "htmlcov" / "index.html",
        worktree / "src" / "cachetools" / "__pycache__" / "keys.pyc",
    ]
    for path in generated_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("generated\n", encoding="utf-8")

    assert git(worktree, "status", "--porcelain") == ""


def test_workspace_file_reader_uses_chunked_base64_transfer():
    task = make_task()
    workspace = ChunkedDownloadWorkspace(b'{"summary": {}}')

    assert task._read_workspace_text(workspace, "/workspace/report.json") == '{"summary": {}}'
    assert any(command.startswith("stat -c%s") for command in workspace.commands)
    assert any(command.startswith("dd if=") for command in workspace.commands)
    assert not any(command.startswith("cat ") for command in workspace.commands)


def test_filesystem_spec_restores_generated_version_before_clean_gate(
    monkeypatch,
):
    task = make_task("asyncodebench:filesystem_spec")
    workspace = RecordingWorkspace()
    monkeypatch.setattr(
        Commit0Task,
        "setup_workspace",
        lambda self, active_workspace: None,
    )

    task.setup_workspace(workspace)

    restore_index = next(
        index
        for index, command in enumerate(workspace.commands)
        if "git restore --source=HEAD -- fsspec/_version.py" in command
    )
    status_index = next(
        index
        for index, command in enumerate(workspace.commands)
        if "git status --porcelain" in command
    )
    assert restore_index < status_index


def test_caid_fallback_uses_active_async_message_scenario(tmp_path):
    task = make_task()
    manager = make_manager(task, None, tmp_path, tmp_path)

    fallback = manager.build_commit0_scenario_fallback_delegation()

    assert fallback["asyncodebench"]["execution_mode"] == "async_message"
    assert (
        fallback["asyncodebench"]["scenario_id"]
        == "commit0-cachetools.async-message.v0.3"
    )
    assert {
        item["task_id"] for item in fallback["delegation_plan"]["first_round"]["tasks"]
    } == {"key_construction", "decorator_factories"}


def test_caid_invalid_delegation_is_replaced_by_manifest(tmp_path):
    task = make_task()
    manager = make_manager(task, None, tmp_path, tmp_path)
    manager.delegation_plan = build_delegation_plan(
        {
            "delegation_plan": {
                "first_round": {
                    "num_agents": 1,
                    "reasoning": "invalid",
                    "tasks": [
                        {
                            "engineer_id": "engineer_1",
                            "task_id": "invented_task",
                            "file_path": "tests/test_keys.py",
                            "functions_to_implement": ["anything"],
                            "instruction": "edit tests",
                            "complexity": "medium",
                        }
                    ],
                },
                "remaining_tasks": [],
            }
        }
    )

    validation = manager.enforce_manifest_delegation()

    assert validation["passed"] is False
    assert validation["fallback_applied"] is True
    assert {task.task_id for task in manager.delegation_plan.first_round_tasks} == {
        "key_construction",
        "decorator_factories",
    }
    saved = json.loads((tmp_path / "delegations.json").read_text())
    assert saved["asyncodebench"]["execution_mode"] == "async_message"


def test_caid_followup_assignment_rejects_non_manifest_scope():
    task = make_task()

    assignments = task.extract_assignments(
        {
            "assignments": [
                {
                    "engineer_id": "key_agent",
                    "task_id": "fix-key_construction",
                    "file_path": "src/cachetools/keys.py, tests/test_keys.py",
                }
            ]
        }
    )

    assert assignments == []
    assert task.last_assignment_rejections[0]["reason"] == (
        "writable scope differs from active manifest"
    )


def test_caid_followup_assignment_normalizes_valid_manifest_scope():
    task = make_task()

    assignments = task.extract_assignments(
        {
            "assignments": [
                {
                    "engineer_id": "key_agent",
                    "task_id": "fix-key_construction",
                    "file_path": "src/cachetools/keys.py",
                }
            ]
        }
    )

    assert assignments[0]["task_id"] == "key_construction"
    assert assignments[0]["file_path"] == "src/cachetools/keys.py"


def test_topological_assignments_are_stable_and_dependency_ordered():
    assignments = [
        {"subproblem_id": "consumer"},
        {"subproblem_id": "independent"},
        {"subproblem_id": "producer"},
    ]
    dependencies = [
        {"producer_subproblem": "producer", "consumer_subproblem": "consumer"}
    ]

    ordered, cycles = topological_assignments(assignments, dependencies)

    assert [item["subproblem_id"] for item in ordered] == [
        "independent",
        "producer",
        "consumer",
    ]
    assert cycles == []


def test_scope_matching_accepts_owned_descendants_only():
    assert path_in_scope("src/pkg/module.py", ["src/pkg/module.py"])
    assert path_in_scope("src/pkg/generated/item.py", ["src/pkg/generated"])
    assert not path_in_scope("tests/test_module.py", ["src/pkg/module.py"])
    assert not path_in_scope("src/pkg_extra/item.py", ["src/pkg"])


def test_private_worktree_change_is_invisible_before_integration(tmp_path):
    repo, worktree, base_head, _ = make_git_worktree(
        tmp_path, ["src/cachetools/keys.py"]
    )

    assert git(repo, "rev-parse", "HEAD") == base_head
    assert (repo / "src/cachetools/keys.py").read_text() == "VALUE = 0\n"
    assert (worktree / "src/cachetools/keys.py").read_text() == "VALUE = 1\n"


def test_caid_rejects_out_of_scope_committed_patch_before_merge(tmp_path):
    repo, worktree, base_head, commit = make_git_worktree(
        tmp_path,
        ["src/cachetools/keys.py", "tests/test_keys.py"],
    )
    task = make_task()
    manager = make_manager(task, LocalWorkspace(), tmp_path / "output", repo)
    Path(manager.config.output_dir).mkdir()
    result = SubAgentResult(
        engineer_id="key_agent",
        task_id="key_construction",
        branch_name="agent_key",
        worktree_path=str(worktree),
        success=True,
        commit_hash=commit,
        round_num=1,
    )

    review = manager.collect_and_merge(result)

    assert review["merged"] is False
    assert review["merge_method"] == "scope_rejected"
    assert git(repo, "rev-parse", "HEAD") == base_head
    assert not (repo / "tests/test_keys.py").exists()
    scope = json.loads(
        (Path(manager.config.output_dir) / "scope_validation.jsonl")
        .read_text()
        .splitlines()[0]
    )
    assert scope["violations"] == ["tests/test_keys.py"]
    assert scope["main_workspace_status_before_merge"] == []


def test_caid_merges_in_scope_committed_patch(tmp_path):
    repo, worktree, base_head, commit = make_git_worktree(
        tmp_path, ["src/cachetools/keys.py"]
    )
    task = make_task()
    manager = make_manager(task, LocalWorkspace(), tmp_path / "output", repo)
    Path(manager.config.output_dir).mkdir()
    result = SubAgentResult(
        engineer_id="key_agent",
        task_id="key_construction",
        branch_name="agent_key",
        worktree_path=str(worktree),
        success=True,
        commit_hash=commit,
        files_modified=["src/cachetools/keys.py"],
        round_num=1,
    )

    review = manager.collect_and_merge(result)

    assert review["merged"] is True
    assert git(repo, "rev-parse", "HEAD") != base_head
    assert (repo / "src/cachetools/keys.py").read_text() == "VALUE = 1\n"


def test_caid_cleans_untracked_test_artifacts_before_scope_gate(tmp_path):
    repo, worktree, _, commit = make_git_worktree(
        tmp_path, ["src/cachetools/keys.py"]
    )
    (repo / ".coverage").write_text("generated\n", encoding="utf-8")
    generated = [
        worktree / ".coverage",
        worktree / ".pytest_cache" / "state",
        worktree / "htmlcov" / "index.html",
        worktree / "src" / "cachetools" / "__pycache__" / "keys.pyc",
    ]
    for path in generated:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("generated\n", encoding="utf-8")

    task = make_task()
    manager = make_manager(task, LocalWorkspace(), tmp_path / "output", repo)
    Path(manager.config.output_dir).mkdir()
    result = SubAgentResult(
        engineer_id="key_agent",
        task_id="key_construction",
        branch_name="agent_key",
        worktree_path=str(worktree),
        success=True,
        commit_hash=commit,
        files_modified=["src/cachetools/keys.py"],
        round_num=1,
    )

    review = manager.collect_and_merge(result)

    assert review["merged"] is True
    assert not (repo / ".coverage").exists()
    assert all(not path.exists() for path in generated)
    scope = json.loads(
        (Path(manager.config.output_dir) / "scope_validation.jsonl")
        .read_text()
        .splitlines()[0]
    )
    assert scope["violations"] == []
    assert scope["main_workspace_status_before_merge"] == []


def test_caid_still_rejects_committed_test_artifacts(tmp_path):
    repo, worktree, base_head, commit = make_git_worktree(
        tmp_path,
        [
            "src/cachetools/keys.py",
            ".coverage",
            "src/cachetools/__pycache__/keys.pyc",
        ],
    )
    task = make_task()
    manager = make_manager(task, LocalWorkspace(), tmp_path / "output", repo)
    Path(manager.config.output_dir).mkdir()
    result = SubAgentResult(
        engineer_id="key_agent",
        task_id="key_construction",
        branch_name="agent_key",
        worktree_path=str(worktree),
        success=True,
        commit_hash=commit,
        round_num=1,
    )

    review = manager.collect_and_merge(result)

    assert review["merged"] is False
    assert review["merge_method"] == "scope_rejected"
    assert git(repo, "rev-parse", "HEAD") == base_head
    scope = json.loads(
        (Path(manager.config.output_dir) / "scope_validation.jsonl")
        .read_text()
        .splitlines()[0]
    )
    assert ".coverage" in scope["violations"]
    assert "src/cachetools/__pycache__/keys.pyc" in scope["violations"]


def test_caid_merges_committed_patch_after_iteration_limit(tmp_path):
    repo, worktree, base_head, commit = make_git_worktree(
        tmp_path, ["src/cachetools/keys.py"]
    )
    task = make_task()
    manager = make_manager(task, LocalWorkspace(), tmp_path / "output", repo)
    Path(manager.config.output_dir).mkdir()
    result = SubAgentResult(
        engineer_id="key_agent",
        task_id="key_construction",
        branch_name="agent_key",
        worktree_path=str(worktree),
        success=False,
        error="MaxIterationsReached",
        round_num=1,
    )

    review = manager.collect_and_merge(result)

    assert review["merged"] is True
    assert result.commit_hash == commit
    assert git(repo, "rev-parse", "HEAD") != base_head
    assert (repo / "src/cachetools/keys.py").read_text() == "VALUE = 1\n"


def test_caid_rejects_merge_when_main_workspace_is_dirty(tmp_path):
    repo, worktree, base_head, commit = make_git_worktree(
        tmp_path, ["src/cachetools/keys.py"]
    )
    (repo / "src/cachetools/func.py").write_text("DIRTY = 1\n", encoding="utf-8")
    task = make_task()
    manager = make_manager(task, LocalWorkspace(), tmp_path / "output", repo)
    Path(manager.config.output_dir).mkdir()
    result = SubAgentResult(
        engineer_id="key_agent",
        task_id="key_construction",
        branch_name="agent_key",
        worktree_path=str(worktree),
        success=True,
        commit_hash=commit,
        round_num=1,
    )

    review = manager.collect_and_merge(result)

    assert review["merged"] is False
    assert "main workspace dirty before merge" in review["merge_message"]
    assert git(repo, "rev-parse", "HEAD") == base_head


def test_caid_rejects_and_restores_manager_final_review_writes(tmp_path):
    repo, _, base_head, _ = make_git_worktree(
        tmp_path, ["src/cachetools/keys.py"]
    )
    task = make_task()
    manager = make_manager(task, LocalWorkspace(), tmp_path / "output", repo)
    Path(manager.config.output_dir).mkdir()
    (repo / "src/cachetools/keys.py").write_text("MANAGER = 1\n", encoding="utf-8")
    (repo / "manager-created.txt").write_text("unauthorized\n", encoding="utf-8")

    record = manager.reject_final_review_writes(base_head)

    assert record["passed"] is False
    assert record["remediated"] is True
    assert record["rejected_paths"] == [
        "manager-created.txt",
        "src/cachetools/keys.py",
    ]
    assert git(repo, "rev-parse", "HEAD") == base_head
    assert (repo / "src/cachetools/keys.py").read_text() == "VALUE = 0\n"
    assert not (repo / "manager-created.txt").exists()
    assert git(repo, "status", "--porcelain") == ""
    assert (Path(manager.config.output_dir) / "rejected_manager_final_review.patch").is_file()


def run_workspace_guard(tool_name, tool_input):
    command = workspace_guard_command(
        "/workspace/apache-tvm-worktree-engineer-3",
        "/workspace/apache-tvm-repo",
    )
    event = {
        "event_type": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": tool_input,
        "working_dir": "/workspace/apache-tvm-worktree-engineer-3",
    }
    result = subprocess.run(
        command,
        shell=True,
        input=json.dumps(event),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize(
    ("tool_name", "tool_input"),
    [
        ("terminal", {"command": "git status --short"}),
        (
            "terminal",
            {
                "command": (
                    "cd /workspace/apache-tvm-worktree-engineer-3 && "
                    "python -m pytest tests/python/tirx"
                )
            },
        ),
        ("file_editor", {"command": "view", "path": "src/tirx/ir/stmt.cc"}),
    ],
)
def test_specialist_workspace_guard_allows_private_worktree_access(
    tool_name,
    tool_input,
):
    decision = run_workspace_guard(tool_name, tool_input)

    assert decision["decision"] == "allow"


@pytest.mark.parametrize(
    ("tool_name", "tool_input"),
    [
        (
            "terminal",
            {"command": "cd /workspace/apache-tvm-repo && git status"},
        ),
        (
            "terminal",
            {
                "command": (
                    "cd /workspace/apache-tvm-worktree-engineer-2 && git status"
                )
            },
        ),
        ("terminal", {"command": "cd .. && ls"}),
        (
            "file_editor",
            {"command": "str_replace", "path": "../apache-tvm-repo/src/a.cc"},
        ),
    ],
)
def test_specialist_workspace_guard_blocks_integrated_or_sibling_access(
    tool_name,
    tool_input,
):
    decision = run_workspace_guard(tool_name, tool_input)

    assert decision["decision"] == "deny"
    assert "Benchmark isolation violation" in decision["reason"]


def test_specialist_conversation_uses_private_remote_workspace_and_hook():
    shared = SimpleNamespace(
        host="http://127.0.0.1:8123/",
        api_key="test-key",
        read_timeout=123.0,
        max_connections=7,
    )
    worktree = "/workspace/apache-tvm-worktree-engineer-3"
    integrated = "/workspace/apache-tvm-repo"

    private = private_remote_workspace(shared, worktree)
    hook = build_workspace_guard_hook(worktree, integrated)

    assert private.host == "http://127.0.0.1:8123"
    assert private.api_key == "test-key"
    assert private.working_dir == worktree
    assert private.read_timeout == 123.0
    assert private.max_connections == 7
    assert hook.pre_tool_use[0].matcher == "*"
    assert hook.pre_tool_use[0].hooks[0].async_ is False
    assert integrated in hook.pre_tool_use[0].hooks[0].command


def test_integrated_workspace_error_does_not_guess_the_actor(tmp_path):
    repo, _, _, _ = make_git_worktree(tmp_path, ["src/cachetools/keys.py"])
    (repo / "src/cachetools/func.py").write_text("DIRTY = 1\n", encoding="utf-8")
    task = make_task()
    manager = make_manager(task, LocalWorkspace(), tmp_path / "output", repo)
    Path(manager.config.output_dir).mkdir()

    with pytest.raises(RuntimeError, match="out-of-band write") as exc_info:
        manager.assert_manager_workspace_clean("before_final_review")

    assert "does not infer the actor" in str(exc_info.value)
    record = json.loads(
        (Path(manager.config.output_dir) / "manager_workspace_validation.jsonl")
        .read_text()
        .splitlines()[0]
    )
    assert record["passed"] is False
    assert record["attribution"].startswith("unknown_at_detection")


def test_static_runner_uses_manifest_dependency_order(tmp_path):
    task = make_task()
    task.set_active_protocol("serial_specialists")
    config = WorkflowConfig(
        model="test/model",
        max_subagents=2,
        subagent_max_iterations=2,
        output_dir=str(tmp_path),
    )
    runner = AsynCodeBenchProtocolRunner(
        task_module=task,
        workflow_config=config,
        protocol="serial_specialists",
    )

    scenario = runner.load_scenario()

    assert scenario["scenario_id"] == "commit0-cachetools.serial-specialists.v0.3"
    assert runner.integration_order == ["key_agent", "decorator_agent"]
    assert runner.dependency_cycle_nodes == []
    assert runner.shared_writable_paths == {}


def test_static_runner_preserves_public_and_source_task_identity(tmp_path):
    task = make_task()
    task.set_active_protocol("serial_specialists")
    config = WorkflowConfig(model="test/model", output_dir=str(tmp_path))
    runner = AsynCodeBenchProtocolRunner(
        task_module=task,
        workflow_config=config,
        protocol="serial_specialists",
    )
    runner.load_scenario()

    runner.write_protocol_files([])

    protocol = json.loads((tmp_path / "protocol.json").read_text())
    assert protocol["harness"] == "asyncodebench-harness-v2.0"
    assert protocol["task_id"] == "asyncodebench:cachetools"
    assert protocol["source_task_id"] == "commit0:cachetools"


def test_existing_shared_scope_and_cycle_are_reported_not_hidden(tmp_path):
    task = make_task("asyncodebench:marshmallow")
    task.set_active_protocol("serial_specialists")
    config = WorkflowConfig(
        model="test/model",
        max_subagents=3,
        output_dir=str(tmp_path),
    )
    runner = AsynCodeBenchProtocolRunner(
        task_module=task,
        workflow_config=config,
        protocol="serial_specialists",
    )

    runner.load_scenario()

    assert runner.dependency_cycle_nodes == [
        "field_validation_layer",
        "schema_processing_layer",
    ]
    assert runner.shared_writable_paths == {
        "src/marshmallow/schema.py": ["registry_agent", "schema_agent"]
    }


def test_serial_downstream_instruction_contains_structured_upstream_handoff(
    tmp_path,
):
    task = make_task()
    task.set_active_protocol("serial_specialists")
    config = WorkflowConfig(
        model="test/model",
        max_subagents=2,
        output_dir=str(tmp_path),
    )
    runner = AsynCodeBenchProtocolRunner(
        task_module=task,
        workflow_config=config,
        protocol="serial_specialists",
    )
    runner.load_scenario()
    upstream = SubAgentResult(
        engineer_id="key_agent",
        task_id="key_construction",
        success=True,
        commit_hash="abc123",
        files_modified=["src/cachetools/keys.py"],
        merged=True,
        merge_method="branch_merge",
    )
    runner.record_handoff(
        upstream,
        runner.scenario["assignments"][0],
        {"status": "passed", "targets": ["tests/test_keys.py"]},
        {
            "checkpoint_id": "integration_after_merge:key_agent:round1",
            "logical_step": 2,
            "pytest_summary": {"passed": 5, "total": 5},
            "dependency_results": [],
        },
    )

    context = runner.build_completed_context([upstream])
    instruction = runner.build_instruction(
        runner.scenario["assignments"][1],
        pass_functions={},
        completed_context=context,
        test_cmd="python -m pytest",
        test_dir="tests",
    )

    assert '"commit": "abc123"' in instruction
    assert '"status": "passed"' in instruction
    assert "integration_after_merge:key_agent:round1" in instruction


def test_run_metadata_excludes_api_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "must-not-leak")
    monkeypatch.setenv(
        "LLM_BASE_URL", "https://user:secret@example.com/v1?api_key=must-not-leak"
    )
    monkeypatch.setenv(
        "LLM_EXTRA_BODY_JSON",
        '{"chat_template_kwargs":{"enable_thinking":true},'
        '"nested":{"api_key":"must-not-leak","token":"must-not-leak"}}',
    )
    task = make_task()
    task.set_active_protocol("single")
    config = WorkflowConfig(model="test/model", output_dir=str(tmp_path))
    prompt_path = (
        Path(__file__).resolve().parents[1] / "prompts" / "asyncodebench.yaml"
    )

    metadata = build_run_metadata(task, config, "single", prompt_path)
    encoded = json.dumps(metadata)

    assert metadata["harness_version"] == "asyncodebench-harness-v2.0"
    assert metadata["task_id"] == "asyncodebench:cachetools"
    assert metadata["source_task_id"] == "commit0:cachetools"
    assert metadata["scenario_id"].startswith("asyncodebench-")
    assert metadata["source_scenario_id"].startswith("commit0-")
    assert metadata["agent_adapter"]["name"] == "openhands"
    assert metadata["subagent_model"] == "test/model"
    assert metadata["source"]["base_sha"]
    assert "must-not-leak" not in encoded
    assert "LLM_API_KEY" not in metadata["environment"]
    assert metadata["model_server"]["base_url"] == "https://example.com/v1"
    assert "hardware" in metadata
    assert metadata["generation_configuration"]["LLM_EXTRA_BODY_JSON"] == {
        "chat_template_kwargs": {"enable_thinking": True},
        "nested": {"api_key": "[REDACTED]", "token": "[REDACTED]"},
    }
    assert metadata["generation_configuration"]["parameters"][
        "LLM_EXTRA_BODY_JSON"
    ]["source"] == "environment"
    assert metadata["generation_configuration"]["parameters"][
        "LLM_MAX_OUTPUT_TOKENS"
    ] == {"value": None, "source": "sdk_or_provider_default"}
    assert metadata["generation_configuration"]["chat_template"]["source"] == (
        "model_server_default"
    )


def test_run_metadata_records_explicit_subagent_model(tmp_path):
    task = make_task()
    task.set_active_protocol("caid_manager")
    config = WorkflowConfig(
        model="test/manager",
        subagent_model="test/worker",
        output_dir=str(tmp_path),
    )
    prompt_path = (
        Path(__file__).resolve().parents[1] / "prompts" / "asyncodebench.yaml"
    )

    metadata = build_run_metadata(
        task,
        config,
        "caid_manager",
        prompt_path,
    )

    assert metadata["model"] == "test/manager"
    assert metadata["subagent_model"] == "test/worker"


def test_contract_snapshots_freeze_active_inputs(tmp_path):
    task = make_task()

    paths = write_contract_snapshots(tmp_path, task, "caid_manager")

    assert set(paths) == {
        "task_snapshot.json",
        "scenario_snapshot.json",
        "scenario_manifest_snapshot.json",
        "metrics_snapshot.json",
        "quality_snapshot.json",
        "execution_profile_snapshot.json",
        "protocol.json",
    }
    scenario = json.loads((tmp_path / "scenario_snapshot.json").read_text())
    protocol = json.loads((tmp_path / "protocol.json").read_text())
    profile = json.loads((tmp_path / "execution_profile_snapshot.json").read_text())
    assert scenario["execution_mode"] == "async_message"
    assert protocol["scenario_id"] == task.public_scenario_id("caid_manager")
    assert protocol["source_task_id"] == task.source_task_id
    assert protocol["source_scenario_id"] == scenario["scenario_id"]
    assert protocol["scope_policy"] == "reject_artifact_before_merge"
    assert profile["profile_id"] == "asyncodebench-v0.3-standard-100"


def test_dry_run_does_not_create_output_directory_or_print_source_brand(
    tmp_path, capsys
):
    output_dir = tmp_path / "dry-run-output"

    run_asyncodebench(
        task_id="asyncodebench:cachetools",
        protocol="serial_specialists",
        model="test/model",
        output_dir=str(output_dir),
        dry_run=True,
    )

    assert not output_dir.exists()
    assert "commit0" not in capsys.readouterr().out.lower()


def test_public_all_protocol_wrapper_uses_native_harness_only():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "run_asyncodebench_all_protocols_env.sh"
    ).read_text(encoding="utf-8")

    assert "run_asyncodebench.py" in script
    assert "run_commit0_" not in script
    assert "MAX_SUBAGENTS" not in script
    for protocol in (
        "single",
        "serial_specialists",
        "async_private",
        "caid_manager",
    ):
        assert protocol in script


def test_public_all_protocol_wrapper_rejects_commit0_namespace():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "run_asyncodebench_all_protocols_env.sh"
    )

    result = subprocess.run(
        [str(script), "commit0:cachetools"],
        cwd=script.parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "legacy source-task IDs are provenance only" in result.stderr
