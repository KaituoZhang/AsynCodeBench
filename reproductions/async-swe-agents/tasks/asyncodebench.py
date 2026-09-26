"""Native AsynCodeBench task adapter.

The Commit0 task implementation remains the source materialization backend.
This adapter makes the AsynCodeBench manifests, official task policy, and
dependency annotations the public task interface used by the v2 harness.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from .commit0 import Commit0Config, Commit0Task
from .task_images import image_record, immutable_image_reference


@dataclass
class AsynCodeBenchConfig:
    task_id: str = "asyncodebench:cachetools"
    release: str = "v0.3"
    docker_image_prefix: str = "docker.io/wentingzhao/"
    curated_config_path: str = ""
    enforce_official: bool = True


class AsynCodeBenchTask(Commit0Task):
    """Materialize and evaluate one manifest-defined AsynCodeBench task."""

    PUBLIC_NAMESPACE = "asyncodebench"
    # Under CAID, the manager is the coordination/control plane. Production
    # changes must arrive only as scope-validated specialist artifacts.
    manager_must_be_read_only = True

    def __init__(self, config: AsynCodeBenchConfig):
        self.asyncodebench_config = config
        if config.release != "v0.3":
            raise ValueError(
                f"Unsupported AsynCodeBench release {config.release!r}; "
                "this harness currently supports v0.3"
            )
        source, repo_name = self._parse_task_id(config.task_id)
        if source != self.PUBLIC_NAMESPACE:
            raise ValueError(
                "Native AsynCodeBench task IDs must use the "
                f"{self.PUBLIC_NAMESPACE!r} namespace; received {config.task_id!r}. "
                "Legacy source-task IDs are provenance only."
            )
        self.repository_name = repo_name
        self.public_task_id = f"{self.PUBLIC_NAMESPACE}:{repo_name}"

        self.release_root = self._repo_root() / "manifests" / "pilot" / config.release
        self.official_manifest = self._read_json(
            self._repo_root() / "manifests" / "release" / "v0.4" / "official_tasks.json"
        )
        official_task_ids = set(self.official_manifest.get("official_task_ids", []))
        if config.enforce_official and self.public_task_id not in official_task_ids:
            raise ValueError(
                f"{config.task_id!r} is not an official AsynCodeBench "
                "v0.4.1 task"
            )
        self._official_source_tasks = []
        for task_id in self.official_manifest.get("official_task_ids", []):
            if not task_id.startswith(f"{self.PUBLIC_NAMESPACE}:"):
                continue
            official_repo_name = task_id.split(":", 1)[1]
            source_manifest = (
                self.release_root
                / "tasks"
                / f"commit0_{official_repo_name.replace('-', '_')}.json"
            )
            if source_manifest.is_file():
                self._official_source_tasks.append(official_repo_name)

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
        parts = str(task_id).split(":")
        if len(parts) != 2 or not all(parts):
            raise ValueError("task_id must use the form 'asyncodebench:<repository>'")
        return parts

    @staticmethod
    def _read_json(path):
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(
                f"Required AsynCodeBench artifact is missing: {path}"
            )
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid JSON in AsynCodeBench artifact {path}: {exc}"
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
        """Return official tasks backed by the v0.3 source-manifest adapter."""

        return list(self._official_source_tasks)

    def get_docker_image(self):
        """Use the immutable v0.4 distribution reference for official runs."""

        record = image_record(self._repo_root(), self.public_task_id)
        return immutable_image_reference(record)

    def runtime_distribution(self):
        record = image_record(self._repo_root(), self.public_task_id)
        return {
            "backend": "container_image",
            "official_image": immutable_image_reference(record),
            "registry_task_id": record["task_id"],
            "digest_pinned": True,
        }

    def set_active_protocol(self, protocol):
        self.active_protocol = protocol

    def scenario_for(self, protocol=None):
        protocol = protocol or self.active_protocol
        # Async-Manager is a distinct execution protocol over the exact same
        # released specialist decomposition as Async-RO-Manager. Keeping this
        # alias centralized avoids duplicating or mutating the task manifests.
        if protocol == "async_manager":
            protocol = "caid_manager"
        execution_mode = {
            "single": "iterative_single",
            "caid_manager": "async_message",
        }.get(protocol, protocol)
        scenarios = self.scenario_manifest.get("scenarios", [])
        for scenario in scenarios:
            if scenario.get("execution_mode") == execution_mode:
                return scenario
        scenario_path = self.manifest_paths["scenario"]
        raise ValueError(f"No scenario for protocol={protocol!r} in {scenario_path}")

    def public_scenario_id(self, protocol=None):
        """Return the public scenario ID while retaining source IDs in manifests."""

        source_id = str(self.scenario_for(protocol).get("scenario_id", ""))
        if source_id.startswith("commit0-"):
            return "asyncodebench-" + source_id.removeprefix("commit0-")
        return source_id

    def load_task_data(self):
        if self._curated_task_source_disabled():
            raise RuntimeError(
                "The native AsynCodeBench harness requires curated task source; "
                "ASYNCODEBENCH_DISABLE_CURATED_TASK_SOURCE must not be enabled"
            )
        data = super().load_task_data()
        if data.get("source") != "asyncodebench_curated_v0.3":
            source = data.get("source")
            raise RuntimeError(
                f"Native AsynCodeBench task unexpectedly loaded source={source!r}"
            )
        return data

    def setup_workspace(self, workspace):
        super().setup_workspace(workspace)
        work_dir = self.get_work_dir()
        self._install_transient_test_artifact_excludes(workspace, work_dir)
        self._clean_transient_test_artifacts(workspace, work_dir)
        if self.config.repo_name == "filesystem_spec":
            # pip install -e rewrites the overlay-provided version module.
            # Restore only this setup artifact before the model starts; later
            # scope checks must preserve any actual agent edit to the file.
            workspace.execute_command(
                f"cd {work_dir} && git restore --source=HEAD -- fsspec/_version.py",
                timeout=60,
            )
        status = workspace.execute_command(
            f"cd {work_dir} && git status --porcelain", timeout=30
        )
        if status.exit_code != 0:
            raise RuntimeError(
                "Failed to validate native AsynCodeBench workspace cleanliness: "
                f"{status.stderr or status.stdout}"
            )
        if status.stdout.strip():
            raise RuntimeError(
                "Native AsynCodeBench workspace is dirty before model execution:\n"
                f"{status.stdout}"
            )
        print("[AsynCodeBench] Verified clean pre-model integrated workspace")

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
                        "AsynCodeBench manifest fallback from active scenario "
                        f"{scenario.get('scenario_id')}."
                    ),
                    "tasks": tasks,
                },
                "remaining_tasks": [],
            },
            "asyncodebench": {
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
            "asyncodebench_scenario_id": self.scenario_for("caid_manager").get(
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
        header = f"AsynCodeBench Single Agent - {self.task_id}"
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
