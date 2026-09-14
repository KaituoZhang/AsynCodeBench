from types import SimpleNamespace

import pytest
from agents import (
    AgentAdapter,
    AgentRunResponse,
    OpenHandsAgentAdapter,
    create_agent_runner,
)
from agents.loader import load_agent_adapter
from config import SubAgent, SubAgentResult


class RecordingAdapter(AgentAdapter):
    name = "recording-test-agent"

    def __init__(self, config=None):
        super().__init__(config=config)
        self.requests = []

    def execute(self, request):
        self.requests.append(request)
        return AgentRunResponse(
            prompt_tokens=11,
            completion_tokens=7,
            iterations=2,
            metadata={"test": True},
        )


class NotAnAdapter:
    def __init__(self, config=None):
        self.config = config


class FakeWorkspace:
    def execute_command(self, command, timeout=30):
        del timeout
        if "git log -1" in command:
            return SimpleNamespace(
                exit_code=0,
                stdout="deadbeef|implement contract|Test Agent\n",
                stderr="",
            )
        if "git diff --name-only" in command:
            return SimpleNamespace(
                exit_code=0, stdout="src/example.py\n", stderr=""
            )
        if "git diff" in command:
            return SimpleNamespace(
                exit_code=0,
                stdout="diff --git a/src/example.py b/src/example.py",
                stderr="",
            )
        return SimpleNamespace(exit_code=0, stdout="", stderr="")


class FakeTask:
    task_id = "asyncodebench:example"
    source_task_id = "commit0:example"
    task_manifest = {
        "publicly_implicated_modules": ["src/example.py"],
        "test_targets": ["tests/test_example.py"],
    }

    def scenario_for(self, protocol):
        return {
            "scenario_id": f"asyncodebench-example.{protocol}.v0.3",
            "assignments": [
                {
                    "agent_id": "worker",
                    "subproblem_id": "implementation",
                    "writable_paths": ["src/example.py"],
                    "primary_test_targets": ["tests/test_example.py"],
                }
            ],
            "dependency_annotations": [
                {
                    "producer_subproblem": "implementation",
                    "consumer_subproblem": "integration",
                    "dependency_type": "api_contract",
                }
            ],
        }

    def public_scenario_id(self, protocol):
        return self.scenario_for(protocol)["scenario_id"]

    def create_subagent_result(self, subagent):
        return SubAgentResult(
            engineer_id=subagent.engineer_id,
            task_id=subagent.task_id,
            branch_name=subagent.branch_name,
            worktree_path=subagent.worktree_path,
            round_num=subagent.current_round,
        )

    def populate_no_commit_result(self, result):
        result.git_diff = ""

    def populate_success_result(self, result, runner, commit_info):
        result.success = True
        result.commit_hash = commit_info["hash"]
        result.commit_message = commit_info["message"]
        result.git_diff = runner.get_git_diff()
        result.files_modified = runner.get_modified_files()


def make_runner(adapter, tmp_path):
    subagent = SubAgent(
        engineer_id="worker",
        task_id="implementation",
        instruction="Implement the assigned contract.",
        worktree_path="/workspace/example_repo",
        branch_name="worker",
        base_commit="cafebabecafebabe",
        status="ready",
    )
    return adapter.create_runner(
        protocol="async_private",
        llm=SimpleNamespace(model="provider/model"),
        workspace=FakeWorkspace(),
        subagent=subagent,
        prompts={"subagent_prompt": "{instruction}"},
        task_module=FakeTask(),
        max_iterations=30,
        max_rounds_chat=2,
        output_dir=str(tmp_path),
        output_logger=None,
    )


def test_loader_returns_builtin_openhands_adapter():
    adapter = load_agent_adapter()

    assert isinstance(adapter, OpenHandsAgentAdapter)
    assert adapter.public_metadata()["name"] == "openhands"
    assert adapter.public_metadata()["package_version"] == "0.1.0"


def test_loader_imports_public_adapter_contract():
    adapter = load_agent_adapter(
        agent_import_path="test_agent_adapter_contract:RecordingAdapter",
        agent_config_json='{"endpoint":"local"}',
    )

    assert isinstance(adapter, RecordingAdapter)
    assert adapter.config == {"endpoint": "local"}


def test_adapter_metadata_records_redacted_config_and_checksum():
    adapter = RecordingAdapter(
        config={
            "endpoint": "local",
            "api_key": "do-not-record",
            "nested": {"access_token": "also-secret", "mode": "strict"},
        }
    )

    metadata = adapter.public_metadata()

    assert metadata["config"] == {
        "endpoint": "local",
        "api_key": "[REDACTED]",
        "nested": {"access_token": "[REDACTED]", "mode": "strict"},
    }
    assert len(metadata["config_sha256"]) == 64
    assert "do-not-record" not in str(metadata)
    assert "also-secret" not in str(metadata)


def test_loader_rejects_objects_outside_adapter_contract():
    with pytest.raises(TypeError, match="agents.AgentAdapter"):
        load_agent_adapter(
            agent_import_path="test_agent_adapter_contract:NotAnAdapter"
        )


def test_custom_adapter_receives_manifest_controlled_request(tmp_path):
    adapter = RecordingAdapter()
    runner = make_runner(adapter, tmp_path)
    runner.setup()

    result = runner.run()

    assert result.success is True
    assert result.commit_hash == "deadbeef"
    assert result.files_modified == ["src/example.py"]
    assert result.total_tokens == 18
    assert result.actual_iterations == 2
    request = adapter.requests[0]
    assert request.benchmark_task_id == "asyncodebench:example"
    assert request.protocol == "async_private"
    assert request.workspace_path == "/workspace/example_repo"
    assert request.writable_paths == ("src/example.py",)
    assert request.primary_test_targets == ("tests/test_example.py",)
    assert len(request.dependency_annotations) == 1
    assert (tmp_path / "agent_adapter_executions.jsonl").exists()


def test_custom_adapter_survives_dynamic_runner_cloning(tmp_path):
    adapter = RecordingAdapter()
    runner = make_runner(adapter, tmp_path)
    next_subagent = SubAgent(
        engineer_id="worker_2",
        task_id="implementation",
        instruction="Continue.",
        worktree_path="/workspace/example_repo_2",
        branch_name="worker_2",
        base_commit="cafebabecafebabe",
        status="ready",
    )

    cloned = runner.clone_for_subagent(next_subagent)

    assert cloned.adapter is adapter
    assert cloned.protocol == "async_private"


@pytest.mark.parametrize(
    "protocol",
    (
        "single",
        "serial_specialists",
        "async_private",
        "caid_manager",
        "async_manager",
    ),
)
def test_all_protocols_route_through_selected_adapter(protocol, tmp_path):
    adapter = RecordingAdapter()
    runner = make_runner(adapter, tmp_path)
    runner = create_agent_runner(
        adapter,
        protocol=protocol,
        llm=runner.llm,
        workspace=runner.workspace,
        subagent=runner.subagent,
        prompts=runner.prompts,
        task_module=runner.task_module,
        max_iterations=runner.max_iterations,
        max_rounds_chat=runner.max_rounds_chat,
        output_dir=runner.output_dir,
        output_logger=runner.output_logger,
    )

    assert runner.adapter is adapter
    assert runner.protocol == protocol
