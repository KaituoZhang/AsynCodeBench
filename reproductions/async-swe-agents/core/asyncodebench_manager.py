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

    def assert_manager_workspace_clean(self, phase):
        """Reject manager-side solution edits before they can taint integration."""
        dirty = self.main_workspace_status()
        record = {
            "schema_version": "0.1",
            "phase": phase,
            "main_workspace_status": dirty,
            "passed": not dirty,
            "policy": "manager_is_read_only_outside_committed_artifact_merges",
        }
        path = Path(self.config.output_dir) / "manager_workspace_validation.jsonl"
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
        if dirty:
            raise RuntimeError(
                "Benchmark isolation violation: the CAID manager modified the "
                f"integrated workspace during {phase}: {dirty}"
            )
        return record

    def reject_final_review_writes(self, head_before):
        """Discard manager-side final-review writes and preserve audit evidence."""
        head_result = self.workspace.execute_command(
            f"cd {shlex.quote(self.repo_dir)} && git rev-parse HEAD",
            timeout=30,
        )
        head_after = head_result.stdout.strip() if head_result.exit_code == 0 else None
        dirty = self.main_workspace_status()
        changed_result = self.workspace.execute_command(
            f"cd {shlex.quote(self.repo_dir)} && git diff --name-only "
            f"{shlex.quote(head_before)}",
            timeout=30,
        )
        changed_paths = (
            [line.strip() for line in changed_result.stdout.splitlines() if line.strip()]
            if changed_result.exit_code == 0
            else []
        )
        rejected_paths = sorted(set(dirty + changed_paths))
        changed_head = bool(head_after and head_after != head_before)
        remediated = False

        if rejected_paths or changed_head:
            patch_result = self.workspace.execute_command(
                f"cd {shlex.quote(self.repo_dir)} && git diff --binary "
                f"{shlex.quote(head_before)}",
                timeout=60,
            )
            patch_path = Path(self.config.output_dir) / "rejected_manager_final_review.patch"
            patch_path.write_text(patch_result.stdout or "", encoding="utf-8")
            restore = self.workspace.execute_command(
                f"cd {shlex.quote(self.repo_dir)} && "
                f"git reset --hard {shlex.quote(head_before)}",
                timeout=120,
            )
            if restore.exit_code != 0:
                raise RuntimeError(
                    "Failed to restore the integrated workspace after rejecting "
                    f"manager final-review writes: {restore.stderr or restore.stdout}"
                )
            clean = self.workspace.execute_command(
                f"cd {shlex.quote(self.repo_dir)} && git clean -fd",
                timeout=120,
            )
            if clean.exit_code != 0:
                raise RuntimeError(
                    "Failed to remove untracked manager final-review writes: "
                    f"{clean.stderr or clean.stdout}"
                )
            remaining = self.main_workspace_status()
            verify_head = self.workspace.execute_command(
                f"cd {shlex.quote(self.repo_dir)} && git rev-parse HEAD",
                timeout=30,
            )
            if (
                remaining
                or verify_head.exit_code != 0
                or verify_head.stdout.strip() != head_before
            ):
                raise RuntimeError(
                    "Integrated workspace restoration could not be verified after "
                    "manager final review"
                )
            remediated = True
            self.log(
                "Rejected and restored manager final-review writes: "
                + ", ".join(rejected_paths or ["committed HEAD change"])
            )

        record = {
            "schema_version": "0.1",
            "phase": "final_review",
            "head_before": head_before,
            "head_after": head_after,
            "main_workspace_status": dirty,
            "rejected_paths": rejected_paths,
            "head_changed": changed_head,
            "passed": not rejected_paths and not changed_head,
            "remediated": remediated,
            "policy": "reject_and_restore_manager_final_review_writes",
        }
        path = Path(self.config.output_dir) / "manager_workspace_validation.jsonl"
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
        return record

    def scan_and_analyze(self):
        result = super().scan_and_analyze()
        self.assert_manager_workspace_clean("scan_and_analyze")
        return result

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
        result = self.enforce_manifest_delegation()
        self.assert_manager_workspace_clean("delegate_tasks")
        return result

    def final_review_all(self, subagent_results, max_iterations=30):
        self.assert_manager_workspace_clean("before_final_review")
        head = self.workspace.execute_command(
            f"cd {shlex.quote(self.repo_dir)} && git rev-parse HEAD",
            timeout=30,
        )
        if head.exit_code != 0:
            raise RuntimeError(
                "Failed to snapshot integrated HEAD before manager final review: "
                f"{head.stderr or head.stdout}"
            )
        head_before = head.stdout.strip()
        result = super().final_review_all(subagent_results, max_iterations=max_iterations)
        self.reject_final_review_writes(head_before)
        return result

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
        if result.worktree_path:
            self.task._clean_transient_test_artifacts(
                self.workspace, result.worktree_path
            )
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
