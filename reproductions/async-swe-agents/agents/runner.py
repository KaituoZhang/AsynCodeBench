"""Harness lifecycle wrapper for a third-party AgentAdapter."""

import json
from datetime import datetime
from pathlib import Path

from core.subagent import SubAgentRunner

from .base import AgentRunRequest, AgentRunResponse


def _assignment_contract(task_module, protocol, subagent):
    scenario = task_module.scenario_for(protocol)
    assignments = scenario.get("assignments", [])
    assignment = next(
        (
            item
            for item in assignments
            if item.get("agent_id") == subagent.engineer_id
            or item.get("subproblem_id") == subagent.task_id
        ),
        {},
    )
    if protocol == "single":
        writable_paths = task_module.task_manifest.get(
            "publicly_implicated_modules", []
        )
        primary_tests = task_module.task_manifest.get("test_targets", [])
    else:
        writable_paths = assignment.get("writable_paths", [])
        primary_tests = assignment.get("primary_test_targets", [])
    subproblem = assignment.get("subproblem_id") or subagent.task_id
    dependencies = [
        item
        for item in scenario.get("dependency_annotations", [])
        if protocol == "single"
        or subproblem
        in {
            item.get("producer_subproblem"),
            item.get("consumer_subproblem"),
        }
    ]
    return scenario, writable_paths, primary_tests, dependencies


class AdapterSubAgentRunner(SubAgentRunner):
    """Make the public adapter contract compatible with harness orchestration."""

    def __init__(self, adapter, protocol, **kwargs):
        super().__init__(**kwargs)
        self.adapter = adapter
        self.protocol = protocol

    def setup(self):
        self.instruction_time = datetime.now()
        self.conversation_round = self.subagent.current_round
        self.log(f"Adapter ready: {self.adapter.name}")

    def ensure_usable_conversation_for_round(self):
        return None

    def clone_for_subagent(self, subagent):
        runner = type(self)(
            adapter=self.adapter,
            protocol=self.protocol,
            llm=self.llm,
            workspace=self.workspace,
            subagent=subagent,
            prompts=self.prompts,
            task_module=self.task_module,
            max_iterations=self.max_iterations,
            max_rounds_chat=self.max_rounds_chat,
            output_dir=self.output_dir,
            output_logger=self.output_logger,
        )
        runner.setup()
        return runner

    def _request(self, prompt):
        scenario, paths, tests, dependencies = _assignment_contract(
            self.task_module, self.protocol, self.subagent
        )
        return AgentRunRequest(
            schema_version="0.1",
            benchmark_task_id=self.task_module.task_id,
            source_task_id=self.task_module.source_task_id,
            protocol=self.protocol,
            scenario_id=self.task_module.public_scenario_id(self.protocol),
            agent_id=self.subagent.engineer_id,
            assignment_id=self.subagent.task_id,
            round_num=self.subagent.current_round,
            instruction=prompt,
            workspace_path=(
                self.subagent.worktree_path or self.subagent.submission_path or ""
            ),
            writable_paths=tuple(paths),
            primary_test_targets=tuple(tests),
            dependency_annotations=tuple(dependencies),
            model=getattr(self.llm, "model", None),
            max_iterations=self.max_iterations,
            output_dir=str(self.output_dir or ""),
            workspace=self.workspace,
            llm=self.llm,
        )

    def _write_adapter_record(self, request, response, start_time, end_time):
        if not self.output_dir:
            return
        path = Path(self.output_dir) / "agent_adapter_executions.jsonl"
        payload = {
            "request": request.public_metadata(),
            "adapter": self.adapter.public_metadata(),
            "response": {
                "error": response.error,
                "cost": response.cost,
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
                "iterations": response.iterations,
                "metadata": response.metadata,
            },
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        }
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, sort_keys=True, default=str) + "\n")

    def run(self):
        result = self.create_result()
        start_time = datetime.now()
        result.start_time = start_time.isoformat()
        self.log("Starting adapter execution...")
        response = AgentRunResponse()

        try:
            if self.protocol == "single" and self.subagent.current_round == 1:
                prompt = self.subagent.instruction
            else:
                prompt = (
                    self.build_first_round_prompt()
                    if self.subagent.current_round == 1
                    else self.build_followup_prompt()
                )
            request = self._request(prompt)
            response = AgentRunResponse.coerce(self.adapter.execute(request))
            if response.error:
                result.success = False
                result.error = response.error
            else:
                commit_info = self.get_commit_info()
                current_hash = commit_info.get("hash", "")
                base_short = (self.subagent.base_commit or "")[:8]
                if not current_hash:
                    result.success = False
                    result.error = (
                        "The harness could not read the agent workspace HEAD."
                    )
                    self.task_module.populate_no_commit_result(result)
                    result.files_modified = []
                elif base_short and current_hash == base_short:
                    result.success = False
                    result.error = (
                        "No new commit was made. The harness may recover allowed "
                        "uncommitted changes during integration."
                    )
                    self.task_module.populate_no_commit_result(result)
                    result.files_modified = []
                else:
                    self.task_module.populate_success_result(result, self, commit_info)
        except Exception as exc:
            result.success = False
            result.error = str(exc)
            request = locals().get("request")

        end_time = datetime.now()
        result.end_time = end_time.isoformat()
        result.duration_seconds = (end_time - start_time).total_seconds()
        result.cost = float(response.cost or 0.0)
        result.prompt_tokens = int(response.prompt_tokens or 0)
        result.completion_tokens = int(response.completion_tokens or 0)
        result.total_tokens = result.prompt_tokens + result.completion_tokens
        result.actual_iterations = int(response.iterations or 0)
        result.max_iterations = self.max_iterations

        if self.output_logger:
            for event in response.events:
                payload = dict(event)
                payload.setdefault("engineer_id", self.subagent.engineer_id)
                payload.setdefault("task_id", self.subagent.task_id)
                payload.setdefault("round_num", self.subagent.current_round)
                self.output_logger.log_agent_event(
                    self.subagent.engineer_id, payload
                )
        if request is not None:
            self._write_adapter_record(request, response, start_time, end_time)

        self.completed_rounds += 1
        self.last_result = result
        self.log(
            f"Adapter completed: success={result.success}, "
            f"iterations={result.actual_iterations}/{result.max_iterations}"
        )
        return result

    def cleanup(self):
        return None
