"""Native AsyncCodeBench task adapter.

The Commit0 task implementation remains the source materialization backend.
This adapter makes the AsyncCodeBench manifests, official task policy, and
dependency annotations the public task interface used by the v2 harness.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from .commit0 import Commit0Config, Commit0Task


@dataclass
class AsyncCodeBenchConfig:
    task_id: str = "asyncodebench:cachetools"
    release: str = "v0.3"
    docker_image_prefix: str = "docker.io/wentingzhao/"
    curated_config_path: str = ""
    enforce_official: bool = True


class AsyncCodeBenchTask(Commit0Task):
    """Materialize and evaluate one manifest-defined AsyncCodeBench task."""

    PUBLIC_NAMESPACE = "asyncodebench"
    PROVENANCE_NAMESPACE = "commit0"

    def __init__(self, config: AsyncCodeBenchConfig):
        self.asynccodebench_config = config
        if config.release != "v0.3":
            raise ValueError(
                f"Unsupported AsyncCodeBench release {config.release!r}; "
                "this harness currently supports v0.3"
            )
        source, repo_name = self._parse_task_id(config.task_id)
        if source not in {self.PUBLIC_NAMESPACE, self.PROVENANCE_NAMESPACE}:
            raise ValueError(
                f"Unsupported AsyncCodeBench task namespace {source!r}; "
                f"use {self.PUBLIC_NAMESPACE}:<repository>"
            )
        self.repository_name = repo_name
        self.public_task_id = f"{self.PUBLIC_NAMESPACE}:{repo_name}"

        self.release_root = self._repo_root() / "manifests" / "pilot" / config.release
        self.official_manifest = self._read_json(
            self._repo_root() / "configs" / "tasks" / "commit0_official_tasks.v0.3.json"
        )
        official_tasks = self.official_manifest.get("official_tasks", [])
        if config.enforce_official and repo_name not in official_tasks:
            raise ValueError(
                f"{config.task_id!r} is not an official AsyncCodeBench "
                f"{config.release} task"
            )

        normalized = repo_name.replace("-", "_")
        self.manifest_paths = {
            "task": self.release_root / "tasks" / f"commit0_{normalized}.json",
            "scenario": self.release_root / "scenarios" / f"commit0_{normalized}.json",
            "metrics": self.release_root
            / "metrics"
            / f"commit0_{normalized}_async_metrics.json",
            "quality": self.release_root / "quality" / f"commit0_{normalized}.json",
        }
        self.task_manifest = self._read_json(self.manifest_paths["task"])
        self.scenario_manifest = self._read_json(self.manifest_paths["scenario"])
        self.metrics_manifest = self._read_json(self.manifest_paths["metrics"])
        self.quality_manifest = self._read_json(self.manifest_paths["quality"])
        self.active_protocol = "single"
        self.last_assignment_rejections = []

        super().__init__(
            Commit0Config(
                repo_name=repo_name,
                docker_image_prefix=config.docker_image_prefix,
                curated_config_path=config.curated_config_path,
            )
        )
        if not self.curated_task:
            raise RuntimeError(
                f"Missing curated source record for official task {config.task_id}"
            )

    @staticmethod
    def _parse_task_id(task_id):
        source, separator, repo_name = str(task_id).partition(":")
        if not separator or not source or not repo_name:
            raise ValueError(
                "task_id must use the form 'asyncodebench:<repository>'"
            )
        return source, repo_name

    @staticmethod
    def _read_json(path):
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(
                f"Required AsyncCodeBench artifact is missing: {path}"
            )
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid JSON in AsyncCodeBench artifact {path}: {exc}"
            ) from exc

    @property
    def task_id(self):
        """Public benchmark identifier; source IDs remain provenance-only."""
        return self.public_task_id

    @property
    def source_task_id(self):
        """Original Commit0-derived identifier stored in release manifests."""
        return self.task_manifest["task_id"]

    @property
    def official_tasks(self):
        return list(self.official_manifest.get("official_tasks", []))

    def set_active_protocol(self, protocol):
        self.active_protocol = protocol

    def scenario_for(self, protocol=None):
        protocol = protocol or self.active_protocol
        execution_mode = {
            "single": "iterative_single",
            "caid_manager": "async_message",
        }.get(protocol, protocol)
        scenarios = self.scenario_manifest.get("scenarios", [])
        for scenario in scenarios:
            if scenario.get("execution_mode") == execution_mode:
                return scenario
        if protocol == "caid_manager":
            for scenario in scenarios:
                if scenario.get("execution_mode") == "async_private":
                    return scenario
        scenario_path = self.manifest_paths["scenario"]
        raise ValueError(f"No scenario for protocol={protocol!r} in {scenario_path}")

    def load_task_data(self):
        if self._curated_task_source_disabled():
            raise RuntimeError(
                "The native AsyncCodeBench harness requires curated task source; "
                "ASYNCCODEBENCH_DISABLE_CURATED_TASK_SOURCE must not be enabled"
            )
        data = super().load_task_data()
        if data.get("source") != "asynccodebench_curated_v0.3":
            source = data.get("source")
            raise RuntimeError(
                f"Native AsyncCodeBench task unexpectedly loaded source={source!r}"
            )
        return data

    def setup_workspace(self, workspace):
        super().setup_workspace(workspace)
        work_dir = self.get_work_dir()
        self._clean_transient_test_artifacts(workspace, work_dir)
        status = workspace.execute_command(
            f"cd {work_dir} && git status --porcelain", timeout=30
        )
        if status.exit_code != 0:
            raise RuntimeError(
                "Failed to validate native AsyncCodeBench workspace cleanliness: "
                f"{status.stderr or status.stdout}"
            )
        if status.stdout.strip():
            raise RuntimeError(
                "Native AsyncCodeBench workspace is dirty before model execution:\n"
                f"{status.stdout}"
            )
        print("[AsyncCodeBench] Verified clean pre-model integrated workspace")

    def dependency_summary(self, scenario=None):
        scenario = scenario or self.scenario_for()
        lines = []
        for dependency in scenario.get("dependency_annotations", []):
            lines.append(
                "- {producer} -> {consumer} [{kind}]: {description}".format(
                    producer=dependency.get("producer_subproblem", "unknown"),
                    consumer=dependency.get("consumer_subproblem", "unknown"),
                    kind=dependency.get("dependency_type", "dependency"),
                    description=dependency.get("description", ""),
                )
            )
        return "\n".join(lines) or "- No cross-assignment dependency is declared."

    def assignment_summary(self, scenario=None):
        scenario = scenario or self.scenario_for()
        lines = []
        for assignment in scenario.get("assignments", []):
            lines.append(
                "- {agent}: {subproblem}; writable={paths}; tests={tests}".format(
                    agent=assignment.get("agent_id", "agent"),
                    subproblem=assignment.get("subproblem_id", "unknown"),
                    paths=", ".join(assignment.get("writable_paths", [])) or "none",
                    tests=", ".join(assignment.get("primary_test_targets", []))
                    or "none",
                )
            )
        return "\n".join(lines)

    def build_manifest_delegation(self, protocol="caid_manager", max_agents=None):
        """Build an executable delegation directly from the active scenario."""

        scenario = self.scenario_for(protocol)
        assignments = scenario.get("assignments", [])
        if max_agents is not None and len(assignments) > int(max_agents):
            raise ValueError(
                f"Scenario {scenario.get('scenario_id')} requires "
                f"{len(assignments)} agents, but max_agents={max_agents}"
            )

        tasks = []
        for index, assignment in enumerate(assignments, start=1):
            subproblem_id = assignment.get("subproblem_id") or f"assignment_{index}"
            dependencies = []
            for dependency in scenario.get("dependency_annotations", []):
                if subproblem_id in {
                    dependency.get("producer_subproblem"),
                    dependency.get("consumer_subproblem"),
                }:
                    dependencies.append(
                        "- {producer} -> {consumer}: {description}".format(
                            producer=dependency.get("producer_subproblem", "unknown"),
                            consumer=dependency.get("consumer_subproblem", "unknown"),
                            description=dependency.get("description", ""),
                        )
                    )
            instruction = [
                f"Role: {assignment.get('role', subproblem_id)}.",
                f"Subproblem ID: {subproblem_id}.",
                "Only modify the manifest writable paths listed below.",
                "Writable paths:",
                *[f"- {path}" for path in assignment.get("writable_paths", [])],
                "Primary public tests:",
                *[
                    f"- {target}"
                    for target in assignment.get("primary_test_targets", [])
                ],
            ]
            if dependencies:
                instruction.extend(["Dependency contracts:", *dependencies])
            tasks.append(
                {
                    "engineer_id": assignment.get("agent_id") or f"engineer_{index}",
                    "task_id": subproblem_id,
                    "file_path": ", ".join(assignment.get("writable_paths", [])),
                    "functions_to_implement": ["manifest-assigned implementation"],
                    "instruction": "\n".join(instruction),
                    "context": "",
                    "estimated_complexity": "medium",
                }
            )

        return {
            "delegation_plan": {
                "first_round": {
                    "num_agents": len(tasks),
                    "reasoning": (
                        "AsyncCodeBench manifest fallback from active scenario "
                        f"{scenario.get('scenario_id')}."
                    ),
                    "tasks": tasks,
                },
                "remaining_tasks": [],
            },
            "asynccodebench": {
                "source": "active_scenario_manifest",
                "scenario_id": scenario.get("scenario_id"),
                "execution_mode": scenario.get("execution_mode"),
            },
        }

    @staticmethod
    def _assignment_paths(task_data):
        return {
            path.strip()
            for path in str(task_data.get("file_path", "")).split(",")
            if path.strip()
        }

    def manifest_assignment_for_task_data(self, task_data):
        scenario = self.scenario_for("caid_manager")
        task_id = str(task_data.get("task_id", ""))
        for assignment in scenario.get("assignments", []):
            subproblem_id = str(assignment.get("subproblem_id", ""))
            if task_id in {subproblem_id, f"fix-{subproblem_id}"}:
                return assignment

        task_paths = self._assignment_paths(task_data)
        matches = [
            assignment
            for assignment in scenario.get("assignments", [])
            if task_paths and task_paths == set(assignment.get("writable_paths", []))
        ]
        return matches[0] if len(matches) == 1 else None

    def extract_assignments(self, assign_data):
        candidates = super().extract_assignments(assign_data)
        accepted = []
        rejected = []
        for task_data in candidates:
            assignment = self.manifest_assignment_for_task_data(task_data)
            if assignment is None:
                rejected.append(
                    {
                        "task_id": task_data.get("task_id"),
                        "file_path": task_data.get("file_path"),
                        "reason": "not an active manifest assignment",
                    }
                )
                continue
            expected_paths = set(assignment.get("writable_paths", []))
            actual_paths = self._assignment_paths(task_data)
            if actual_paths != expected_paths:
                rejected.append(
                    {
                        "task_id": task_data.get("task_id"),
                        "file_path": task_data.get("file_path"),
                        "reason": "writable scope differs from active manifest",
                    }
                )
                continue
            normalized = dict(task_data)
            normalized["task_id"] = assignment.get("subproblem_id")
            normalized["file_path"] = ", ".join(assignment.get("writable_paths", []))
            accepted.append(normalized)
        self.last_assignment_rejections = rejected
        return accepted

    def get_assign_event_extras(self, engineer_id):
        del engineer_id
        return {
            "asynccodebench_scenario_id": self.scenario_for("caid_manager").get(
                "scenario_id"
            ),
            "manifest_assignment_rejections": self.last_assignment_rejections,
        }

    def get_prompt_format_args(self, config):
        args = super().get_prompt_format_args(config)
        scenario = self.scenario_for()
        args.update(
            {
                "task_id": self.task_id,
                "problem_statement": self.task_manifest.get("problem_statement", ""),
                "dependency_summary": self.dependency_summary(scenario),
                "assignment_summary": self.assignment_summary(scenario),
                "scenario_id": scenario.get("scenario_id", ""),
                "execution_mode": scenario.get("execution_mode", ""),
                "information_profile": scenario.get("information_profile", ""),
                "integration_policy": scenario.get("integration_policy", ""),
                "message_delivery_policy": scenario.get("message_delivery_policy", ""),
            }
        )
        return args

    def get_single_agent_info(self, workspace, config, prompts):
        header = f"AsyncCodeBench Single Agent - {self.task_id}"
        format_args = self.get_prompt_format_args(config)
        format_args["repo_path"] = self.get_work_dir()
        instruction = prompts.get("single_agent_instruction", "").format(**format_args)
        return (
            header,
            instruction,
            {
                "task_id": self.task_id,
                "repo_name": self.config.repo_name,
                "repo_path": self.get_work_dir(),
                "scenario_id": format_args["scenario_id"],
                "max_iterations": config.manager_max_iterations,
            },
        )
