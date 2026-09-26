"""Dependency-aware static protocol runner for AsynCodeBench harness v2."""

import json
import os
import shlex
import time
from copy import deepcopy
from pathlib import Path

from core.subagent import run_subagents_parallel
from tasks.asyncodebench import AsynCodeBenchTask

from protocols.static_commit0 import StaticCommit0ProtocolRunner

from .metadata import HARNESS_VERSION
from .ordering import path_in_scope, topological_assignments


class AsynCodeBenchProtocolRunner(StaticCommit0ProtocolRunner):
    """Execute static protocols with manifest contracts enforced by the runner."""

    def __init__(self, *args, **kwargs):
        task_module = kwargs.get("task_module") or (args[0] if args else None)
        if not isinstance(task_module, AsynCodeBenchTask):
            raise TypeError("AsynCodeBenchProtocolRunner requires AsynCodeBenchTask")
        kwargs.setdefault("task_name", "asyncodebench")
        super().__init__(*args, **kwargs)
        self.assignment_by_agent = {}
        self.handoff_records = []
        self.integration_order = []
        self.dependency_cycle_nodes = []
        self.shared_writable_paths = {}
        self.base_commit_by_agent = {}
        self.source_build_records = []
        self.worktree_preparation_seconds = 0.0

    def load_scenario(self):
        scenario = deepcopy(self.task_module.scenario_for(self.protocol))
        ordered, cycle_nodes = topological_assignments(
            scenario.get("assignments", []),
            scenario.get("dependency_annotations", []),
        )
        scenario["assignments"] = ordered
        self.scenario = scenario
        self.assignment_by_agent = {
            item.get("agent_id"): item for item in scenario.get("assignments", [])
        }
        self.integration_order = [item.get("agent_id") for item in ordered]
        self.dependency_cycle_nodes = cycle_nodes
        path_owners = {}
        for assignment in ordered:
            for path in assignment.get("writable_paths", []):
                path_owners.setdefault(path, []).append(assignment.get("agent_id"))
        self.shared_writable_paths = {
            path: owners for path, owners in path_owners.items() if len(owners) > 1
        }
        return scenario

    def build_instruction(
        self,
        assignment,
        pass_functions,
        completed_context="",
        test_cmd="",
        test_dir="",
    ):
        writable_paths = assignment.get("writable_paths", [])
        primary_tests = assignment.get("primary_test_targets", [])
        subproblem_id = assignment.get("subproblem_id", "")
        relevant_dependencies = []
        for dependency in self.scenario.get("dependency_annotations", []):
            if subproblem_id in {
                dependency.get("producer_subproblem"),
                dependency.get("consumer_subproblem"),
            }:
                relevant_dependencies.append(
                    "- {producer} -> {consumer} [{kind}]: {description}".format(
                        producer=dependency.get("producer_subproblem", "unknown"),
                        consumer=dependency.get("consumer_subproblem", "unknown"),
                        kind=dependency.get("dependency_type", "dependency"),
                        description=dependency.get("description", ""),
                    )
                )

        targets = []
        for path in writable_paths:
            functions = pass_functions.get(path) or []
            target_description = (
                ", ".join(functions) if functions else "assigned missing logic"
            )
            targets.append(f"- {path}: {target_description}")

        parts = [
            f"AsynCodeBench task: {self.task_module.task_id}",
            f"Scenario: {self.scenario.get('scenario_id')}",
            f"Role: {assignment.get('role', subproblem_id)}",
            f"Subproblem: {subproblem_id}",
            "",
            "Task specification:",
            self.task_module.task_manifest.get("problem_statement", ""),
            "",
            "Workspace semantics:",
            "- This is your private git worktree. Other specialists cannot see edits "
            "until the harness integrates a committed artifact.",
            "- Inspect and edit only the writable paths listed below.",
            "- Public tests are read-only evaluation evidence; do not modify tests.",
            "",
            "Writable scope:",
            *[f"- {path}" for path in writable_paths],
            "",
            "Detected implementation targets:",
            *targets,
        ]
        if relevant_dependencies:
            parts.extend(["", "Relevant dependency contracts:", *relevant_dependencies])
        if completed_context:
            parts.extend(
                [
                    "",
                    "Upstream artifacts visible before this worktree was created:",
                    completed_context,
                ]
            )
        if primary_tests:
            parts.extend(
                ["", "Role-specific public tests:", *[f"- {t}" for t in primary_tests]]
            )
        if test_cmd:
            worktree_build_command = getattr(
                self.task_module, "worktree_build_command", None
            )
            parts.extend(
                [
                    "",
                    "Validation workflow:",
                    "- Work iteratively: inspect, implement, then run relevant "
                    "tests, diagnose failures, and repair within scope.",
                    *(
                        [
                            "- After C++ or header edits, rebuild this worktree "
                            f"before testing: {worktree_build_command}"
                        ]
                        if worktree_build_command
                        else []
                    ),
                    "- Suggested command: "
                    f"{test_cmd} {' '.join(primary_tests) or test_dir}",
                ]
            )
        parts.extend(
            [
                "",
                "Completion requirements:",
                "- Preserve public API names and behavior.",
                "- Do not hide failures by weakening tests or deleting existing code.",
                "- Commit the final artifact locally before finishing.",
                "- Report unresolved cross-scope dependencies instead of editing "
                "outside scope.",
            ]
        )
        return "\n".join(parts)

    def write_protocol_files(self, subagents):
        super().write_protocol_files(subagents)
        path = Path(self.workflow_config.output_dir) / "protocol.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload.update(
            {
                "harness": HARNESS_VERSION,
                "task_id": self.task_module.task_id,
                "source_task_id": self.task_module.source_task_id,
                "scenario_id": self.task_module.public_scenario_id(self.protocol),
                "source_scenario_id": self.scenario.get("scenario_id"),
                "dependency_ordered_integration": True,
                "resolved_integration_order": self.integration_order,
                "dependency_cycle_nodes": self.dependency_cycle_nodes,
                "shared_writable_paths": self.shared_writable_paths,
                "scope_policy": "reject_artifact_on_out_of_scope_change",
            }
        )
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _parse_status_paths(status_output):
        paths = []
        for line in status_output.splitlines():
            if len(line) < 4:
                continue
            path = line[3:].strip()
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            if path:
                paths.append(path)
        return paths

    def create_worktree(self, workspace, repo_dir, subagent, base_commit):
        super().create_worktree(workspace, repo_dir, subagent, base_commit)
        self.base_commit_by_agent[subagent.engineer_id] = base_commit
        preparer = getattr(self.task_module, "prepare_worktree_runtime", None)
        if preparer is not None:
            started = time.monotonic()
            try:
                preparer(workspace, subagent.worktree_path)
            finally:
                self.worktree_preparation_seconds += time.monotonic() - started
        else:
            validator = getattr(self.task_module, "validate_worktree_runtime", None)
            if validator is not None:
                validator(workspace, subagent.worktree_path)

    def measured_runtime_seconds(self, raw_runtime_seconds):
        """Exclude deterministic worktree prebuilds already excluded for single-agent runs."""
        preparation_seconds = min(
            max(0.0, self.worktree_preparation_seconds), raw_runtime_seconds
        )
        measured_seconds = max(0.0, raw_runtime_seconds - preparation_seconds)
        timing = {
            "schema_version": "0.1",
            "raw_protocol_seconds": raw_runtime_seconds,
            "worktree_preparation_seconds": preparation_seconds,
            "reported_protocol_seconds": measured_seconds,
            "policy": "exclude_deterministic_worktree_source_build_preparation",
        }
        path = Path(self.workflow_config.output_dir) / "infrastructure_timing.json"
        path.write_text(json.dumps(timing, indent=2) + "\n", encoding="utf-8")
        if preparation_seconds:
            print(
                "[PR-hard] Excluding deterministic worktree preparation from "
                f"protocol runtime: {preparation_seconds:.1f}s"
            )
        return measured_seconds

    def refresh_source_build(self, workspace, workspace_path, reason):
        refresh = getattr(self.task_module, "refresh_source_build", None)
        if refresh is None:
            return {"status": "not_required", "workspace_path": workspace_path}
        result = refresh(workspace, workspace_path)
        record = {
            "schema_version": "0.1",
            "reason": reason,
            **result,
        }
        self.source_build_records.append(record)
        path = Path(self.workflow_config.output_dir) / "source_build_checkpoints.jsonl"
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
        print(
            "[PR-hard] Source build "
            f"{reason}: {result.get('status')} ({workspace_path})"
        )
        return result

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
        source_build = self.refresh_source_build(
            workspace, workspace_path, reason=f"probe:{checkpoint_id}"
        )
        return super().write_probe_checkpoint(
            workspace,
            workspace_path,
            checkpoint_id,
            checkpoint_type,
            agent_id=agent_id,
            task_id=task_id,
            workspace_kind=workspace_kind,
            artifact_version=artifact_version,
            visible_upstream_artifact_version=visible_upstream_artifact_version,
            integrated_workspace_version=integrated_workspace_version,
            source_build=source_build,
        )

    def changed_paths(self, workspace, result):
        if result.worktree_path:
            self.task_module._clean_transient_test_artifacts(
                workspace, result.worktree_path
            )
        paths = set(result.files_modified or [])
        if result.branch_name and result.worktree_path:
            base_commit = self.base_commit_by_agent.get(result.engineer_id)
            revision_range = (
                f"{shlex.quote(base_commit)}..HEAD" if base_commit else "HEAD^!"
            )
            diff = workspace.execute_command(
                f"cd {shlex.quote(result.worktree_path)} && "
                f"git diff --name-only {revision_range} "
                "2>/dev/null || true",
                timeout=30,
            )
            paths.update(
                line.strip() for line in diff.stdout.splitlines() if line.strip()
            )
            status = workspace.execute_command(
                f"cd {shlex.quote(result.worktree_path)} && git status --porcelain",
                timeout=30,
            )
            if status.exit_code == 0:
                paths.update(self._parse_status_paths(status.stdout))
        return sorted(paths)

    def validate_scope(self, workspace, result):
        assignment = self.assignment_by_agent.get(result.engineer_id, {})
        writable_paths = assignment.get("writable_paths", [])
        changed = self.changed_paths(workspace, result)
        repo_dir = self.task_module.get_work_dir()
        self.task_module._clean_transient_test_artifacts(workspace, repo_dir)
        main_status = workspace.execute_command(
            f"cd {shlex.quote(repo_dir)} && git status --porcelain", timeout=30
        )
        main_dirty = (
            self._parse_status_paths(main_status.stdout)
            if main_status.exit_code == 0
            else [f"<status-error:{main_status.stderr.strip()}>"]
        )
        violations = [
            path for path in changed if not path_in_scope(path, writable_paths)
        ]
        record = {
            "agent_id": result.engineer_id,
            "task_assignment_id": result.task_id,
            "writable_paths": writable_paths,
            "changed_paths": changed,
            "violations": violations,
            "main_workspace_status_before_merge": main_dirty,
            "passed": not violations and not main_dirty,
            "policy": "reject_artifact_on_out_of_scope_change",
        }
        path = Path(self.workflow_config.output_dir) / "scope_validation.jsonl"
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
        return record

    def merge_scoped_result(self, manager, workspace, result):
        scope = self.validate_scope(workspace, result)
        if scope["main_workspace_status_before_merge"]:
            raise RuntimeError(
                "Benchmark isolation violation: a specialist wrote directly to "
                "the integrated workspace before merge: "
                + ", ".join(scope["main_workspace_status_before_merge"])
            )
        if not scope["passed"]:
            result.merged = False
            result.merge_method = "scope_rejected"
            reasons = []
            if scope["violations"]:
                reasons.append(
                    "out-of-scope changes: " + ", ".join(scope["violations"])
                )
            if scope["main_workspace_status_before_merge"]:
                reasons.append(
                    "main workspace dirty: "
                    + ", ".join(scope["main_workspace_status_before_merge"])
                )
            result.error = "; ".join(reasons)
            return {"merged": False, "merge_method": "scope_rejected"}
        return self.merge_result(manager, result)

    def recover_async_private_workspace(
        self, workspace, repo_dir, base_commit, results
    ):
        """Reject and remove out-of-band specialist writes before integration.

        Async-private specialists run concurrently, so a dirty integrated
        workspace cannot safely be blamed on whichever result happens to be
        integrated first.  Detect the contamination once after all workers
        finish, attribute paths from the frozen manifest ownership, preserve
        audit evidence, restore the clean base, and let unaffected private
        artifacts proceed through the normal merge gate.
        """
        self.task_module._clean_transient_test_artifacts(workspace, repo_dir)
        status = workspace.execute_command(
            f"cd {shlex.quote(repo_dir)} && git status --porcelain", timeout=30
        )
        if status.exit_code != 0:
            raise RuntimeError(
                "Failed to inspect the async-private integrated workspace: "
                + (status.stderr or status.stdout)
            )
        dirty_paths = set(self._parse_status_paths(status.stdout))

        head = workspace.execute_command(
            f"cd {shlex.quote(repo_dir)} && git rev-parse HEAD", timeout=30
        )
        if head.exit_code != 0:
            raise RuntimeError(
                "Failed to inspect the async-private integrated workspace HEAD: "
                + (head.stderr or head.stdout)
            )
        head_before_restore = head.stdout.strip()
        head_changed = head_before_restore != base_commit
        committed_paths = set()
        if head_changed:
            changed = workspace.execute_command(
                f"cd {shlex.quote(repo_dir)} && git diff --name-only "
                f"{shlex.quote(base_commit)}..HEAD",
                timeout=30,
            )
            if changed.exit_code != 0:
                raise RuntimeError(
                    "Failed to inspect committed async-private workspace writes: "
                    + (changed.stderr or changed.stdout)
                )
            committed_paths.update(
                line.strip() for line in changed.stdout.splitlines() if line.strip()
            )

        changed_paths = sorted(dirty_paths | committed_paths)
        if not changed_paths and not head_changed:
            return {}

        ownership = {}
        for path in changed_paths:
            ownership[path] = sorted(
                agent_id
                for agent_id, assignment in self.assignment_by_agent.items()
                if path_in_scope(path, assignment.get("writable_paths", []))
            )
        unattributed_paths = sorted(
            path for path, owners in ownership.items() if not owners
        )
        rejected_agents = {
            agent_id for owners in ownership.values() for agent_id in owners
        }
        if unattributed_paths:
            # Unknown out-of-band writes make every concurrently active
            # specialist suspect. Reject all private artifacts conservatively.
            rejected_agents.update(result.engineer_id for result in results)

        patch_result = workspace.execute_command(
            f"cd {shlex.quote(repo_dir)} && git diff --binary "
            f"{shlex.quote(base_commit)}",
            timeout=60,
        )
        patch_path = (
            Path(self.workflow_config.output_dir)
            / "rejected_async_private_workspace.patch"
        )
        patch_path.write_text(patch_result.stdout or "", encoding="utf-8")

        restore = workspace.execute_command(
            f"cd {shlex.quote(repo_dir)} && git reset --hard "
            f"{shlex.quote(base_commit)}",
            timeout=120,
        )
        if restore.exit_code != 0:
            raise RuntimeError(
                "Failed to restore the async-private integrated workspace: "
                + (restore.stderr or restore.stdout)
            )
        clean = workspace.execute_command(
            f"cd {shlex.quote(repo_dir)} && git clean -fd", timeout=120
        )
        if clean.exit_code != 0:
            raise RuntimeError(
                "Failed to clean rejected async-private workspace writes: "
                + (clean.stderr or clean.stdout)
            )
        verify_status = workspace.execute_command(
            f"cd {shlex.quote(repo_dir)} && git status --porcelain", timeout=30
        )
        verify_head = workspace.execute_command(
            f"cd {shlex.quote(repo_dir)} && git rev-parse HEAD", timeout=30
        )
        if (
            verify_status.exit_code != 0
            or verify_status.stdout.strip()
            or verify_head.exit_code != 0
            or verify_head.stdout.strip() != base_commit
        ):
            raise RuntimeError(
                "Async-private integrated workspace restoration could not be verified"
            )

        rejected_by_agent = {
            agent_id: sorted(
                path
                for path, owners in ownership.items()
                if agent_id in owners or path in unattributed_paths
            )
            for agent_id in sorted(rejected_agents)
        }
        validation = {
            "schema_version": "0.1",
            "protocol": "async_private",
            "base_commit": base_commit,
            "head_before_restore": head_before_restore,
            "head_changed": head_changed,
            "changed_paths": changed_paths,
            "path_ownership_candidates": ownership,
            "unattributed_paths": unattributed_paths,
            "rejected_agents": sorted(rejected_agents),
            "remediated": True,
            "patch_path": patch_path.name,
            "policy": "reject_out_of_band_integrated_workspace_writes",
        }
        validation_path = (
            Path(self.workflow_config.output_dir)
            / "workspace_isolation_validation.jsonl"
        )
        with validation_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(validation, sort_keys=True) + "\n")

        result_by_agent = {result.engineer_id: result for result in results}
        scope_path = Path(self.workflow_config.output_dir) / "scope_validation.jsonl"
        with scope_path.open("a", encoding="utf-8") as stream:
            for agent_id, paths in rejected_by_agent.items():
                assignment = self.assignment_by_agent.get(agent_id, {})
                result = result_by_agent.get(agent_id)
                writable_paths = assignment.get("writable_paths", [])
                ownership_violations = [
                    path for path in paths if not path_in_scope(path, writable_paths)
                ]
                record = {
                    "agent_id": agent_id,
                    "task_assignment_id": getattr(result, "task_id", None),
                    "writable_paths": writable_paths,
                    "changed_paths": paths,
                    "violations": ownership_violations,
                    "workspace_isolation_violations": paths,
                    "main_workspace_status_before_merge": changed_paths,
                    "passed": False,
                    "remediated": True,
                    "policy": "reject_out_of_band_integrated_workspace_writes",
                }
                stream.write(json.dumps(record, sort_keys=True) + "\n")

        print(
            "[AsynCodeBench] Rejected and restored out-of-band async-private "
            "workspace writes: "
            + ", ".join(changed_paths)
        )
        return rejected_by_agent

    @staticmethod
    def reject_workspace_isolation_result(result, changed_paths):
        reason = (
            "async-private workspace isolation violation: wrote directly to "
            "the integrated workspace before artifact merge: "
            + ", ".join(changed_paths)
        )
        result.merged = False
        result.merge_method = "workspace_isolation_rejected"
        result.error = reason if not result.error else f"{result.error}; {reason}"
        return {
            "merged": False,
            "merge_method": "workspace_isolation_rejected",
            "merge_message": reason,
        }

    def run_targeted_tests(self, workspace, repo_dir, assignment, agent_id):
        targets = assignment.get("primary_test_targets", [])
        if not targets:
            return {"status": "not_configured", "targets": [], "exit_code": None}
        source_build = self.refresh_source_build(
            workspace, repo_dir, reason=f"handoff:{agent_id}"
        )
        if source_build.get("status") not in {"passed", "not_required"}:
            return {
                "status": "build_failed",
                "targets": targets,
                "exit_code": source_build.get("exit_code"),
                "timed_out": False,
                "summary": {},
                "evaluator_source": "pr_hard_source_build",
                "output_excerpt": source_build.get("output_excerpt", ""),
                "source_build": source_build,
            }
        test_cmd, _, evaluator_source = self.task_module._resolve_evaluator()
        timeout = max(
            30,
            int(os.getenv("ASYNCODEBENCH_HANDOFF_TEST_TIMEOUT_SECONDS", "300")),
        )
        safe_agent = "".join(char if char.isalnum() else "_" for char in agent_id)
        report_path = f"/tmp/asyncodebench_handoff_{safe_agent}.json"
        output_path = f"/tmp/asyncodebench_handoff_{safe_agent}.txt"
        target_args = " ".join(shlex.quote(target) for target in targets)
        command = (
            f"cd {shlex.quote(repo_dir)} && "
            f"export PYTHONPATH={shlex.quote(repo_dir)}/src:"
            f"{shlex.quote(repo_dir)}:$PYTHONPATH && "
            f"timeout {timeout}s {test_cmd} --json-report "
            f"--json-report-file={shlex.quote(report_path)} "
            f"--continue-on-collection-errors {target_args} "
            f"> {shlex.quote(output_path)} 2>&1"
        )
        execution = workspace.execute_command(command, timeout=timeout + 30)
        report_result = workspace.execute_command(
            f"cat {shlex.quote(report_path)} 2>/dev/null || echo '{{}}'", timeout=30
        )
        output_result = workspace.execute_command(
            f"cat {shlex.quote(output_path)} 2>/dev/null || true", timeout=30
        )
        workspace.execute_command(
            f"rm -f {shlex.quote(report_path)} {shlex.quote(output_path)}", timeout=30
        )
        try:
            report = json.loads(report_result.stdout or "{}")
        except json.JSONDecodeError:
            report = {}
        summary = report.get("summary", {})
        return {
            "status": "passed" if execution.exit_code == 0 else "failed",
            "targets": targets,
            "exit_code": execution.exit_code,
            "timed_out": str(execution.exit_code) in {"124", "-1"},
            "summary": summary,
            "evaluator_source": evaluator_source,
            "output_excerpt": (output_result.stdout or "")[-2000:],
        }

    def record_handoff(self, result, assignment, targeted_tests, checkpoint):
        record = {
            "schema_version": "0.1",
            "from_agent": result.engineer_id,
            "subproblem_id": assignment.get("subproblem_id"),
            "artifact": {
                "commit": result.commit_hash,
                "merged": result.merged,
                "merge_method": result.merge_method,
                "files": result.files_modified or [],
            },
            "targeted_tests": targeted_tests,
            "dependency_probe": {
                "checkpoint_id": checkpoint.get("checkpoint_id")
                if checkpoint
                else None,
                "logical_step": checkpoint.get("logical_step") if checkpoint else None,
                "summary": checkpoint.get("pytest_summary") if checkpoint else None,
                "dependency_results": checkpoint.get("dependency_results")
                if checkpoint
                else [],
            },
        }
        self.handoff_records.append(record)
        path = Path(self.workflow_config.output_dir) / "artifact_handoffs.jsonl"
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
        return record

    def build_completed_context(self, results):
        del results
        return json.dumps(self.handoff_records, indent=2, sort_keys=True)

    async def run_serial_specialists(
        self, manager, workspace, repo_dir, subagent_llm, base_commit
    ):
        initial_subagents = self.build_subagents(workspace, repo_dir, base_commit)
        self.write_protocol_files(initial_subagents)
        results = []
        completed_context = ""
        for index, assignment in enumerate(self.scenario.get("assignments", [])):
            head = workspace.execute_command(
                f"cd {shlex.quote(repo_dir)} && git rev-parse HEAD", timeout=30
            )
            current_base = head.stdout.strip() if head.exit_code == 0 else base_commit
            subagent = self.build_subagents(
                workspace, repo_dir, current_base, completed_context=completed_context
            )[index]
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
                    artifact_version=result.commit_hash
                    or self.read_head(workspace, result.worktree_path),
                    visible_upstream_artifact_version=current_base,
                )
            self.merge_scoped_result(manager, workspace, result)
            targeted_tests = self.run_targeted_tests(
                workspace, repo_dir, assignment, result.engineer_id
            )
            checkpoint = self.write_probe_checkpoint(
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
            self.record_handoff(result, assignment, targeted_tests, checkpoint)
            completed_context = self.build_completed_context(results)
            runner.cleanup()
            if targeted_tests.get("status") == "build_failed":
                print(
                    "[PR-hard] Stopping serial prefix after an unbuildable "
                    f"artifact from {result.engineer_id}; final evaluation will "
                    "record the model-produced failure."
                )
                break
        return results

    async def run_async_private(
        self, manager, workspace, repo_dir, subagent_llm, base_commit
    ):
        subagents = self.build_subagents(workspace, repo_dir, base_commit)
        self.write_protocol_files(subagents)
        runners = []
        for subagent in subagents:
            self.create_worktree(workspace, repo_dir, subagent, base_commit)
            runners.append(self.setup_runner(subagent_llm, workspace, subagent))

        completion_order_results = await run_subagents_parallel(
            runners,
            manager=None,
            task_module=self.task_module,
            output_logger=self.output_logger,
            enable_background_exploration=False,
            max_subagents=len(runners),
        )
        by_agent = {result.engineer_id: result for result in completion_order_results}
        results = [
            by_agent[agent_id]
            for agent_id in self.integration_order
            if agent_id in by_agent
        ]
        print(
            "[AsynCodeBench] Workers completed privately; integrating in "
            "dependency order: " + " -> ".join(result.engineer_id for result in results)
        )
        workspace_rejections = self.recover_async_private_workspace(
            workspace, repo_dir, base_commit, results
        )
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
                    artifact_version=result.commit_hash
                    or self.read_head(workspace, result.worktree_path),
                )
            if result.engineer_id in workspace_rejections:
                self.reject_workspace_isolation_result(
                    result, workspace_rejections[result.engineer_id]
                )
            else:
                self.merge_scoped_result(manager, workspace, result)
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
