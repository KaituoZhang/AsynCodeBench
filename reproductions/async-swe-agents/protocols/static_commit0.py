import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

import litellm
from agents import create_agent_runner
from openhands.sdk import LLM

import core.patches
from config import SubAgent
from core.manager import Manager
from core.dependency_probes import write_dependency_probe_checkpoint
from core.subagent import run_subagents_parallel
from core.workspace import (
    AsynCodeBenchDockerDevWorkspace,
    AsynCodeBenchDockerWorkspace,
)
from core.utils import (
    OutputLogger,
    TeeLogger,
    build_llm_kwargs,
    cleanup_stale_containers,
    detect_platform,
    download_file_via_base64,
    generate_patch,
    load_prompts,
    save_all_costs,
)
from tasks.commit0 import Commit0Task


SUPPORTED_PROTOCOLS = {"serial_specialists", "async_private"}


class StaticCommit0ProtocolRunner:
    """Run manifest-defined Commit0 specialist protocols without manager delegation."""

    def __init__(
        self,
        task_module,
        workflow_config,
        protocol,
        scenario_path=None,
        task_name="commit0",
        agent_adapter=None,
    ):
        if not isinstance(task_module, Commit0Task):
            raise TypeError("StaticCommit0ProtocolRunner currently supports Commit0Task only")
        if protocol not in SUPPORTED_PROTOCOLS:
            raise ValueError(
                f"Unsupported protocol: {protocol}. "
                f"Available: {', '.join(sorted(SUPPORTED_PROTOCOLS))}"
            )

        self.task_module = task_module
        self.workflow_config = workflow_config
        self.protocol = protocol
        self.task_name = task_name
        self.repo_name = task_module.config.repo_name
        self.scenario_path = Path(scenario_path) if scenario_path else self.default_scenario_path()
        self.agent_adapter = agent_adapter

        self.scenario = None
        self.output_logger = OutputLogger(workflow_config.output_dir)
        self.prompts = load_prompts(task_name)
        self.probe_logical_step = 0

    def default_scenario_path(self):
        repo_root = Path(__file__).resolve().parents[3]
        scenario_dir = repo_root / "manifests" / "pilot" / "v0.3" / "scenarios"
        direct_path = scenario_dir / f"commit0_{self.repo_name}.json"
        if direct_path.exists():
            return direct_path
        normalized_name = self.repo_name.replace("-", "_")
        return scenario_dir / f"commit0_{normalized_name}.json"

    def load_scenario(self):
        with open(self.scenario_path, "r") as f:
            data = json.load(f)

        for scenario in data.get("scenarios", []):
            if scenario.get("execution_mode") == self.protocol:
                self.scenario = scenario
                return scenario

        raise ValueError(
            f"No scenario with execution_mode={self.protocol!r} in {self.scenario_path}"
        )

    def build_workspace_context(self):
        workspace_config = self.task_module.get_workspace_config()
        sdk_source_dir = os.getenv(
            "SDK_SOURCE_DIR",
            str(Path(__file__).resolve().parents[1].parent / "software-agent-sdk"),
        )

        original_cwd = os.getcwd()
        os.chdir(sdk_source_dir)
        try:
            workspace_network = (
                os.getenv("ASYNCODEBENCH_WORKSPACE_DOCKER_NETWORK") or None
            )
            workspace_host_port_env = os.getenv("ASYNCODEBENCH_WORKSPACE_HOST_PORT")
            workspace_host_port = (
                int(workspace_host_port_env)
                if workspace_host_port_env
                else None
            )
            if workspace_config.get("base_image"):
                return AsynCodeBenchDockerDevWorkspace(
                    base_image=workspace_config["base_image"],
                    server_image=None,
                    target=workspace_config.get("target", "source-minimal"),
                    host_port=workspace_host_port,
                    platform="linux/amd64",
                    detach_logs=False,
                    network=workspace_network,
                    volumes=workspace_config.get("volumes", []),
                )
            return AsynCodeBenchDockerWorkspace(
                server_image=workspace_config["server_image"],
                host_port=workspace_host_port,
                platform=detect_platform(),
                detach_logs=False,
                network=workspace_network,
                volumes=workspace_config.get("volumes", []),
            )
        finally:
            os.chdir(original_cwd)

    def load_llm(self):
        llm_kwargs = build_llm_kwargs(self.workflow_config.model)
        manager_llm = LLM(**llm_kwargs)
        if self.workflow_config.subagent_model:
            subagent_llm_kwargs = build_llm_kwargs(self.workflow_config.subagent_model)
            return manager_llm, LLM(**subagent_llm_kwargs)
        return manager_llm, manager_llm

    def extract_pass_functions(self, workspace, repo_dir, paths):
        script = r'''
import ast, json, pathlib, sys
repo = pathlib.Path(sys.argv[1])
paths = sys.argv[2:]
out = {}
for rel in paths:
    path = repo / rel
    names = []
    try:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if any(isinstance(stmt, ast.Pass) for stmt in node.body):
                    names.append(node.name)
    except Exception:
        pass
    out[rel] = names
print(json.dumps(out))
'''
        quoted_paths = " ".join(json.dumps(p) for p in paths)
        cmd = (
            "python -c "
            + json.dumps(script)
            + " "
            + json.dumps(repo_dir)
            + (" " + quoted_paths if quoted_paths else "")
        )
        result = workspace.execute_command(cmd, timeout=60)
        if result.exit_code != 0:
            return {}
        try:
            return json.loads(result.stdout.strip() or "{}")
        except json.JSONDecodeError:
            return {}

    def build_instruction(self, assignment, pass_functions, completed_context="", test_cmd="", test_dir=""):
        writable_paths = assignment.get("writable_paths", [])
        primary_tests = assignment.get("primary_test_targets", [])

        dependency_lines = []
        for dep in self.scenario.get("dependency_annotations", []):
            producer = dep.get("producer_subproblem")
            consumer = dep.get("consumer_subproblem")
            subproblem_id = assignment.get("subproblem_id")
            if subproblem_id in {producer, consumer}:
                dependency_lines.append(
                    f"- {producer} -> {consumer}: {dep.get('description', '')}"
                )

        functions_lines = []
        for rel_path in writable_paths:
            funcs = pass_functions.get(rel_path) or []
            if funcs:
                functions_lines.append(f"- {rel_path}: {', '.join(funcs)}")
            else:
                functions_lines.append(f"- {rel_path}: implement assigned missing logic")

        parts = [
            f"Role: {assignment.get('role', assignment.get('subproblem_id', 'specialist'))}.",
            f"Subproblem ID: {assignment.get('subproblem_id', '')}.",
            "",
            "You are running in a controlled AsynCodeBench specialist protocol. "
            "Only modify your assigned writable paths. Do not edit files outside this scope.",
            "",
            "Assigned writable paths:",
            *[f"- {p}" for p in writable_paths],
            "",
            "Pass-stub targets detected in your writable paths:",
            *functions_lines,
        ]

        if primary_tests:
            parts.extend(["", "Primary test targets for this role:", *[f"- {t}" for t in primary_tests]])

        if dependency_lines:
            parts.extend(["", "Relevant dependency annotations:", *dependency_lines])

        if completed_context:
            parts.extend(["", "Completed upstream handoff context:", completed_context])

        if test_cmd:
            test_line = f"{test_cmd} {test_dir}".strip()
            parts.extend(["", "Recommended validation command:", f"- {test_line}"])

        parts.extend([
            "",
            "Implementation constraints:",
            "- Preserve public names and existing test-facing behavior.",
            "- Do not comment out tests or existing code.",
            "- Commit your changes locally before finishing.",
        ])
        return "\n".join(parts)

    def build_subagents(self, workspace, repo_dir, base_commit, completed_context=""):
        assignments = self.scenario.get("assignments", [])
        prompt_args = self.task_module.get_prompt_format_args(self.workflow_config)
        test_cmd = prompt_args.get("test_cmd", "python -m pytest")
        test_dir = prompt_args.get("test_dir", "tests/")
        if not test_cmd.startswith("PYTHONPATH="):
            test_cmd = f"PYTHONPATH=src:. {test_cmd}"
        all_paths = []
        for assignment in assignments:
            all_paths.extend(assignment.get("writable_paths", []))
        pass_map = self.extract_pass_functions(workspace, repo_dir, sorted(set(all_paths)))

        subagents = []
        for index, assignment in enumerate(assignments, start=1):
            writable_paths = assignment.get("writable_paths", [])
            engineer_id = assignment.get("agent_id") or f"engineer_{index}"
            branch_name = f"{self.protocol}_{engineer_id}"
            worktree_name = f"{self.repo_name}_{self.protocol}_{engineer_id}"
            functions = []
            for rel_path in writable_paths:
                functions.extend(pass_map.get(rel_path) or [])
            if not functions:
                functions = ["assigned writable paths"]

            subagent = SubAgent(
                engineer_id=engineer_id,
                task_id=assignment.get("subproblem_id") or f"{self.protocol}_{index}",
                file_path=", ".join(writable_paths),
                functions_to_implement=functions,
                instruction=self.build_instruction(
                    assignment,
                    pass_map,
                    completed_context,
                    test_cmd=test_cmd,
                    test_dir=test_dir,
                ),
                estimated_complexity="medium",
                branch_name=branch_name,
                worktree_path=f"/workspace/{worktree_name}",
                base_commit=base_commit,
                status="pending",
                current_round=1,
            )
            subagent.test_cmd = test_cmd
            subagent.test_dir = test_dir
            subagents.append(subagent)
        return subagents

    def create_worktree(self, workspace, repo_dir, subagent, base_commit):
        subagent.base_commit = base_commit
        branch_cmd = (
            f"cd {repo_dir} && "
            f"git branch {subagent.branch_name} {base_commit} 2>/dev/null || true"
        )
        workspace.execute_command(branch_cmd, timeout=30)

        worktree_cmd = (
            f"cd {repo_dir} && "
            f"git worktree add {subagent.worktree_path} {subagent.branch_name}"
        )
        result = workspace.execute_command(worktree_cmd, timeout=60)
        if result.exit_code != 0:
            subagent.status = "failed"
            raise RuntimeError(
                f"Failed to create worktree for {subagent.engineer_id}: {result.stderr}"
            )
        subagent.status = "ready"

    def setup_runner(self, subagent_llm, workspace, subagent):
        runner_kwargs = {
            "llm": subagent_llm,
            "workspace": workspace,
            "subagent": subagent,
            "prompts": self.prompts,
            "task_module": self.task_module,
            "max_iterations": self.workflow_config.subagent_max_iterations,
            "max_rounds_chat": 1,
            "output_dir": self.workflow_config.output_dir,
            "output_logger": self.output_logger,
        }
        runner = create_agent_runner(
            self.agent_adapter,
            protocol=self.protocol,
            **runner_kwargs,
        )
        runner.setup()

        self.output_logger.log_manager_instruction(
            engineer_id=subagent.engineer_id,
            task_id=subagent.task_id,
            file_path=subagent.file_path,
            functions_to_implement=subagent.functions_to_implement,
            instruction=subagent.instruction,
        )
        return runner

    def write_protocol_files(self, subagents):
        output_dir = Path(self.workflow_config.output_dir)
        payload = {
            "protocol": self.protocol,
            "scenario_id": self.scenario.get("scenario_id"),
            "scenario_path": str(self.scenario_path),
            "repo": self.repo_name,
            "assignments": [s.to_dict() for s in subagents],
            "concurrent_execution": self.scenario.get("concurrent_execution"),
            "communication_condition": self.scenario.get("communication_condition"),
            "integration_policy": self.scenario.get("integration_policy"),
            "message_delivery_policy": self.scenario.get("message_delivery_policy"),
        }
        with open(output_dir / "protocol.json", "w") as f:
            json.dump(payload, f, indent=2)

        delegation = {
            "delegation_plan": {
                "first_round": {
                    "num_agents": len(subagents),
                    "reasoning": (
                        "Static AsynCodeBench manifest-defined specialist assignment; "
                        "no manager scan or dynamic delegation was used."
                    ),
                    "tasks": [
                        {
                            "engineer_id": s.engineer_id,
                            "task_id": s.task_id,
                            "file_path": s.file_path,
                            "functions_to_implement": s.functions_to_implement,
                            "complexity": s.estimated_complexity,
                            "instruction": s.instruction,
                        }
                        for s in subagents
                    ],
                },
                "remaining_tasks": [],
            }
        }
        with open(output_dir / "delegations.json", "w") as f:
            json.dump(delegation, f, indent=2)

    def merge_result(self, manager, result):
        review = manager.collect_and_merge(result, self.output_logger)
        result.merged = review.get("merged", False)
        result.merge_method = review.get("merge_method", "")
        result.conflict_files = review.get("conflict_files", [])
        if not result.merged and review.get("merge_message"):
            result.error = result.error or review["merge_message"]
        return review

    def next_probe_step(self):
        self.probe_logical_step += 1
        return self.probe_logical_step

    def read_head(self, workspace, path):
        result = workspace.execute_command(
            f"cd {path} && git rev-parse --short HEAD",
            timeout=30,
        )
        return result.stdout.strip() if result.exit_code == 0 else None

    def write_probe_checkpoint(
        self,
        workspace,
        workspace_path,
        checkpoint_id,
        checkpoint_type,
        agent_id=None,
        task_id=None,
        workspace_kind="agent_workspace",
        artifact_version=None,
        visible_upstream_artifact_version=None,
        integrated_workspace_version=None,
    ):
        return write_dependency_probe_checkpoint(
            workspace=workspace,
            output_dir=self.workflow_config.output_dir,
            repo_name=self.repo_name,
            workspace_path=workspace_path,
            checkpoint_id=checkpoint_id,
            checkpoint_type=checkpoint_type,
            logical_step=self.next_probe_step(),
            agent_id=agent_id,
            task_id=task_id,
            workspace_kind=workspace_kind,
            artifact_version=artifact_version,
            visible_upstream_artifact_version=visible_upstream_artifact_version,
            integrated_workspace_version=integrated_workspace_version,
            metrics_path=self.task_module.manifest_paths.get("metrics")
            if hasattr(self.task_module, "manifest_paths")
            else None,
        )

    def save_final_artifacts(self, workspace, repo_dir, base_commit, results, runtime_seconds):
        save_all_costs(
            self.workflow_config.output_dir,
            {
                "cost": 0.0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "duration": 0.0,
            },
            results,
            wall_clock_duration=runtime_seconds,
            manager_cost_breakdown={
                "analysis_cost": 0.0,
                "analysis_tokens": 0,
                "analysis_duration": 0.0,
                "delegation_cost": 0.0,
                "delegation_tokens": 0,
                "delegation_duration": 0.0,
                "assign_task_cost": 0.0,
                "assign_task_tokens": 0,
                "assign_task_duration": 0.0,
                "review_cost": 0.0,
                "review_tokens": 0,
                "review_duration": 0.0,
                "final_review_cost": 0.0,
                "final_review_tokens": 0,
                "final_review_duration": 0.0,
            },
            model=self.workflow_config.model,
            subagent_model=self.workflow_config.subagent_model,
        )

        patch_content, _ = generate_patch(workspace, repo_dir, base_commit, results)
        patch_file = Path(self.workflow_config.output_dir) / "patch.diff"
        with open(patch_file, "w") as f:
            f.write(patch_content)
        print(f"[Patch] Saved to {patch_file}")

        pytest_results = self.task_module.evaluate(workspace)
        output_dir = Path(self.workflow_config.output_dir)
        report_file = output_dir / "report.json"
        exit_code_file = output_dir / f"{self.repo_name}_pytest_exit_code.txt"
        test_output_file = output_dir / f"{self.repo_name}_test_output.txt"
        with open(report_file, "w") as f:
            f.write(pytest_results["report_json"])
        with open(exit_code_file, "w") as f:
            f.write(pytest_results["exit_code"])
        with open(test_output_file, "w") as f:
            f.write(pytest_results["test_output"])

        print(f"[Pytest] Saved report to {report_file}")

        self.write_probe_checkpoint(
            workspace,
            repo_dir,
            checkpoint_id="final_integrated",
            checkpoint_type="final_integrated",
            workspace_kind="integrated_workspace",
            integrated_workspace_version=self.read_head(workspace, repo_dir),
        )

        if getattr(self.task_module, "save_final_tarball", True):
            tarball_name = f"{self.repo_name}_repo.tar.gz"
            tar_cmd = f"cd /workspace && tar -czf {tarball_name} {self.repo_name}_repo"
            tar_result = workspace.execute_command(tar_cmd, timeout=300)
            if tar_result.exit_code == 0:
                final_repo_dir = output_dir / "final_repo"
                final_repo_dir.mkdir(parents=True, exist_ok=True)
                download_file_via_base64(
                    workspace,
                    f"/workspace/{tarball_name}",
                    str(final_repo_dir / f"{self.repo_name}.tar.gz"),
                )
            else:
                print(f"[Tarball] Warning: failed to create tarball: {tar_result.stderr}")
        else:
            print("[Tarball] Skipped for PR-hard source-build candidate")

    async def run_async_private(self, manager, workspace, repo_dir, subagent_llm, base_commit):
        subagents = self.build_subagents(workspace, repo_dir, base_commit)
        self.write_protocol_files(subagents)

        runners = []
        for subagent in subagents:
            self.create_worktree(workspace, repo_dir, subagent, base_commit)
            runners.append(self.setup_runner(subagent_llm, workspace, subagent))

        results = await run_subagents_parallel(
            runners,
            manager=None,
            task_module=self.task_module,
            output_logger=self.output_logger,
            enable_background_exploration=False,
            max_subagents=len(runners),
        )

        print("[StaticProtocol] All async-private workers finished; integrating artifacts now.")
        for result in results:
            if result.worktree_path:
                self.write_probe_checkpoint(
                    workspace,
                    result.worktree_path,
                    checkpoint_id=f"agent_artifact:{result.engineer_id}:round{result.round_num}",
                    checkpoint_type="agent_artifact",
                    agent_id=result.engineer_id,
                    task_id=result.task_id,
                    workspace_kind="agent_workspace",
                    artifact_version=result.commit_hash or self.read_head(workspace, result.worktree_path),
                )
            self.merge_result(manager, result)
            self.write_probe_checkpoint(
                workspace,
                repo_dir,
                checkpoint_id=f"integration_after_merge:{result.engineer_id}:round{result.round_num}",
                checkpoint_type="integration_after_merge",
                agent_id=result.engineer_id,
                task_id=result.task_id,
                workspace_kind="integrated_workspace",
                artifact_version=result.commit_hash,
                integrated_workspace_version=self.read_head(workspace, repo_dir),
            )

        for runner in runners:
            runner.cleanup()
        return results

    async def run_serial_specialists(self, manager, workspace, repo_dir, subagent_llm, base_commit):
        initial_subagents = self.build_subagents(workspace, repo_dir, base_commit)
        self.write_protocol_files(initial_subagents)

        results = []
        completed_context = ""
        for index, _ in enumerate(initial_subagents, start=1):
            head_result = workspace.execute_command(
                f"cd {repo_dir} && git rev-parse HEAD",
                timeout=30,
            )
            current_base = head_result.stdout.strip() if head_result.exit_code == 0 else base_commit

            subagent = self.build_subagents(
                workspace,
                repo_dir,
                current_base,
                completed_context=completed_context,
            )[index - 1]
            self.create_worktree(workspace, repo_dir, subagent, current_base)
            runner = self.setup_runner(subagent_llm, workspace, subagent)
            result = runner.run()
            self.output_logger.log_agent_response(
                **self.task_module.get_log_agent_response_kwargs(result)
            )
            if result.worktree_path:
                self.write_probe_checkpoint(
                    workspace,
                    result.worktree_path,
                    checkpoint_id=f"agent_artifact:{result.engineer_id}:round{result.round_num}",
                    checkpoint_type="agent_artifact",
                    agent_id=result.engineer_id,
                    task_id=result.task_id,
                    workspace_kind="agent_workspace",
                    artifact_version=result.commit_hash or self.read_head(workspace, result.worktree_path),
                    visible_upstream_artifact_version=current_base,
                )
            self.merge_result(manager, result)
            self.write_probe_checkpoint(
                workspace,
                repo_dir,
                checkpoint_id=f"integration_after_merge:{result.engineer_id}:round{result.round_num}",
                checkpoint_type="integration_after_merge",
                agent_id=result.engineer_id,
                task_id=result.task_id,
                workspace_kind="integrated_workspace",
                artifact_version=result.commit_hash,
                visible_upstream_artifact_version=current_base,
                integrated_workspace_version=self.read_head(workspace, repo_dir),
            )
            results.append(result)
            runner.cleanup()

            completed_context = self.build_completed_context(results)

        return results

    def build_completed_context(self, results):
        lines = []
        for result in results:
            status = "merged" if result.merged else "not merged"
            files = ", ".join(result.files_modified or [])
            lines.append(
                f"- {result.engineer_id}/{result.task_id}: {status}; "
                f"commit={result.commit_hash or 'none'}; files={files or 'none'}"
            )
        return "\n".join(lines)

    async def run_inner(self):
        start_time = datetime.now()
        self.load_scenario()

        print("=" * 70)
        print(f"AsynCodeBench Protocol: {self.protocol} ({self.repo_name})")
        print("=" * 70)
        scenario_id = str(self.scenario.get("scenario_id", ""))
        if self.task_name == "asyncodebench" and scenario_id.startswith("commit0-"):
            scenario_id = "asyncodebench-" + scenario_id.removeprefix("commit0-")
        print(f"- Scenario: {scenario_id}")
        if self.task_name == "asyncodebench":
            print("- Scenario contract: loaded from release manifest")
        else:
            print(f"- Scenario file: {self.scenario_path}")
        print(f"- Output dir: {self.workflow_config.output_dir}")

        litellm.set_verbose = False
        litellm.drop_params = True
        manager_llm, subagent_llm = self.load_llm()

        cleanup_stale_containers(verbose=True)
        workspace_ctx = self.build_workspace_context()

        with workspace_ctx as workspace:
            manager = Manager(
                llm=manager_llm,
                workspace=workspace,
                task=self.task_module,
                config=self.workflow_config,
                output_logger=self.output_logger,
                prompts=self.prompts,
            )
            manager.setup_workspace()

            repo_dir = self.task_module.get_work_dir()
            base_result = workspace.execute_command(
                f"cd {repo_dir} && git rev-parse HEAD",
                timeout=30,
            )
            if base_result.exit_code != 0:
                raise RuntimeError(f"Failed to read base commit: {base_result.stderr}")
            base_commit = base_result.stdout.strip()

            runtime_start = datetime.now()
            if self.protocol == "serial_specialists":
                results = await self.run_serial_specialists(
                    manager, workspace, repo_dir, subagent_llm, base_commit
                )
            else:
                results = await self.run_async_private(
                    manager, workspace, repo_dir, subagent_llm, base_commit
                )
            runtime_seconds = (datetime.now() - runtime_start).total_seconds()

            runtime_file = Path(self.workflow_config.output_dir) / "runtime.txt"
            with open(runtime_file, "w") as f:
                f.write(f"{runtime_seconds:.1f}")

            self.save_final_artifacts(
                workspace,
                repo_dir,
                base_commit,
                results,
                runtime_seconds,
            )

        total_time = (datetime.now() - start_time).total_seconds()
        print("=" * 70)
        print("Static Protocol Complete")
        print("=" * 70)
        print(f"- Protocol: {self.protocol}")
        print(f"- Runtime: {runtime_seconds:.1f}s")
        print(f"- Total time: {total_time:.1f}s")
        print(f"- Results: {len(results)} subagent runs")
        print(f"- Output dir: {self.workflow_config.output_dir}")

    async def run(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = str(Path(self.workflow_config.output_dir) / f"run_{timestamp}.log")
        with TeeLogger(log_path):
            return await self.run_inner()
