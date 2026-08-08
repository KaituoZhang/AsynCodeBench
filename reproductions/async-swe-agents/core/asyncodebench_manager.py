"""CAID manager adapter that enforces AsynCodeBench runtime contracts."""

import json
import shlex
from datetime import datetime
from pathlib import Path

from protocols.asyncodebench.ordering import path_in_scope
from tasks.asyncodebench import AsynCodeBenchTask

from core.manager import Manager
from core.utils import build_delegation_plan


class AsynCodeBenchManager(Manager):
    """Manager-mediated CAID with manifest delegation and merge gates."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not isinstance(self.task, AsynCodeBenchTask):
            raise TypeError("AsynCodeBenchManager requires AsynCodeBenchTask")

    def active_scenario(self):
        return self.task.scenario_for("caid_manager")

    def build_commit0_scenario_fallback_delegation(self):
        fallback = self.task.build_manifest_delegation(
            "caid_manager", max_agents=self.config.max_subagents
        )
        self.log(
            "Using active AsynCodeBench scenario fallback delegation: "
            f"{fallback['asyncodebench']['scenario_id']}"
        )
        return fallback

    @staticmethod
    def _task_paths(task):
        return {
            path.strip()
            for path in str(getattr(task, "file_path", "")).split(",")
            if path.strip()
        }

    def validate_delegation_plan(self):
        scenario = self.active_scenario()
        expected = {
            assignment.get("subproblem_id"): set(assignment.get("writable_paths", []))
            for assignment in scenario.get("assignments", [])
        }
        tasks = []
        if self.delegation_plan:
            tasks.extend(self.delegation_plan.first_round_tasks)
            tasks.extend(self.delegation_plan.remaining_tasks)

        reasons = []
        seen = set()
        for task in tasks:
            task_id = getattr(task, "task_id", "")
            if task_id not in expected:
                reasons.append(f"unknown subproblem: {task_id or '<empty>'}")
                continue
            if task_id in seen:
                reasons.append(f"duplicate subproblem: {task_id}")
            seen.add(task_id)
            actual_paths = self._task_paths(task)
            if actual_paths != expected[task_id]:
                reasons.append(
                    f"scope mismatch for {task_id}: expected "
                    f"{sorted(expected[task_id])}, found {sorted(actual_paths)}"
                )

        missing = sorted(set(expected) - seen)
        if missing:
            reasons.append(f"missing manifest subproblems: {missing}")
        if len(tasks) != len(expected):
            expected_count = len(expected)
            observed_count = len(tasks)
            reasons.append(
                f"assignment count mismatch: expected {expected_count}, "
                f"found {observed_count}"
            )
        declared_agents = int(scenario.get("agent_count", len(expected)))
        observed_agents = (
            int(self.delegation_plan.num_agents) if self.delegation_plan else 0
        )
        if observed_agents != declared_agents:
            reasons.append(
                f"active-agent count mismatch: expected {declared_agents}, "
                f"found {observed_agents}"
            )
        return {
            "passed": not reasons,
            "scenario_id": scenario.get("scenario_id"),
            "execution_mode": scenario.get("execution_mode"),
            "expected_subproblems": sorted(expected),
            "observed_subproblems": sorted(seen),
            "reasons": reasons,
        }

    def enforce_manifest_delegation(self):
        validation = self.validate_delegation_plan()
        validation["fallback_applied"] = not validation["passed"]
        if not validation["passed"]:
            self.log(
                "Manager delegation violates the active manifest; replacing it: "
                + "; ".join(validation["reasons"])
            )
            fallback = self.build_commit0_scenario_fallback_delegation()
            self.delegation_plan = build_delegation_plan(fallback)
            output_path = Path(self.config.output_dir) / "delegations.json"
            output_path.write_text(
                json.dumps(fallback, indent=2) + "\n", encoding="utf-8"
            )

        validation_path = Path(self.config.output_dir) / "delegation_validation.json"
        validation_path.write_text(
            json.dumps(validation, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return validation

    def delegate_tasks(self):
        super().delegate_tasks()
        return self.enforce_manifest_delegation()

    def assignment_for_result(self, result):
        scenario = self.active_scenario()
        assignments = scenario.get("assignments", [])
        for assignment in assignments:
            if result.task_id == assignment.get("subproblem_id"):
                return assignment

        result_paths = {
            path.strip()
            for path in str(result.file_path or "").split(",")
            if path.strip()
        }
        matches = [
            assignment
            for assignment in assignments
            if result_paths
            and result_paths == set(assignment.get("writable_paths", []))
        ]
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def _status_paths(status_output):
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

    def committed_and_uncommitted_paths(self, result):
        paths = set(result.files_modified or [])
        branch = result.branch_name or result.commit_hash
        if branch:
            merge_base = self.workspace.execute_command(
                f"cd {shlex.quote(self.repo_dir)} && "
                f"git merge-base HEAD {shlex.quote(branch)}",
                timeout=30,
            )
            if merge_base.exit_code == 0 and merge_base.stdout.strip():
                base = merge_base.stdout.strip()
                changed = self.workspace.execute_command(
                    f"cd {shlex.quote(self.repo_dir)} && "
                    f"git diff --name-only {shlex.quote(base)}.."
                    f"{shlex.quote(branch)}",
                    timeout=30,
                )
                if changed.exit_code == 0:
                    paths.update(
                        line.strip()
                        for line in changed.stdout.splitlines()
                        if line.strip()
                    )

        if result.worktree_path:
            status = self.workspace.execute_command(
                f"cd {shlex.quote(result.worktree_path)} && git status --porcelain",
                timeout=30,
            )
            if status.exit_code == 0:
                paths.update(self._status_paths(status.stdout))
        return sorted(paths)

    def main_workspace_status(self):
        self.task._clean_transient_test_artifacts(self.workspace, self.repo_dir)
        result = self.workspace.execute_command(
            f"cd {shlex.quote(self.repo_dir)} && git status --porcelain",
            timeout=30,
        )
        if result.exit_code != 0:
            return [f"<status-error:{result.stderr.strip()}>"]
        return self._status_paths(result.stdout)

    def record_scope_validation(self, record):
        path = Path(self.config.output_dir) / "scope_validation.jsonl"
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")

    def rejected_review(self, result, reason, changed_paths, output_logger):
        result.merged = False
        result.merge_method = "scope_rejected"
        result.error = reason
        now = datetime.now()
        if output_logger:
            output_logger.log_manager_review(
                engineer_id=result.engineer_id,
                task_id=result.task_id,
                merged=False,
                review_reason=reason,
                commit_hash=result.commit_hash,
                files_modified=changed_paths,
                round_num=result.round_num,
                start_time=now,
                end_time=now,
            )
        return {
            "engineer_id": result.engineer_id,
            "task_id": result.task_id,
            "subagent_success": result.success,
            "merged": False,
            "merge_message": reason,
            "review_notes": reason,
            "merge_method": "scope_rejected",
            "conflict_files": [],
        }

    def collect_and_merge(self, subagent_result, output_logger=None):
        assignment = self.assignment_for_result(subagent_result)
        changed_paths = self.committed_and_uncommitted_paths(subagent_result)
        main_dirty = self.main_workspace_status()
        writable_paths = assignment.get("writable_paths", []) if assignment else []
        violations = [
            path for path in changed_paths if not path_in_scope(path, writable_paths)
        ]
        reasons = []
        if assignment is None:
            reasons.append("result does not map to an active manifest assignment")
        if main_dirty:
            reasons.append(f"main workspace dirty before merge: {main_dirty}")
        if violations:
            reasons.append(f"out-of-scope committed changes: {violations}")

        record = {
            "schema_version": "0.1",
            "protocol": "caid_manager",
            "scenario_id": self.active_scenario().get("scenario_id"),
            "agent_id": subagent_result.engineer_id,
            "task_assignment_id": subagent_result.task_id,
            "manifest_subproblem_id": (
                assignment.get("subproblem_id") if assignment else None
            ),
            "writable_paths": writable_paths,
            "changed_paths": changed_paths,
            "violations": violations,
            "main_workspace_status_before_merge": main_dirty,
            "passed": not reasons,
            "reasons": reasons,
            "policy": "reject_artifact_before_merge",
        }
        self.record_scope_validation(record)
        if reasons:
            reason = "; ".join(reasons)
            self.log(f"Rejecting CAID artifact before merge: {reason}")
            return self.rejected_review(
                subagent_result, reason, changed_paths, output_logger
            )
        return super().collect_and_merge(subagent_result, output_logger)
