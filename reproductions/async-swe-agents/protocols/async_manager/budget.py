"""Task-budgeted online manager with explicit remote shutdown evidence."""

from __future__ import annotations

import json
import shlex
import time
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from core.utils import extract_conversation_metrics

from protocols.async_manager import POLICY
from protocols.async_manager.manager import OnlineManager


def load_profile() -> dict:
    return json.loads(
        Path(__file__).with_name("profile.json").read_text(encoding="utf-8")
    )


class BudgetedOnlineManager(OnlineManager):
    """The v1 online manager constrained as one logical task-level agent."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        profile = load_profile()
        self.budget_profile = profile
        self.manager_iterations_limit = int(profile["manager_max_iterations_total"])
        self.manager_tokens_limit = int(profile["manager_max_tokens_total"])
        self.manager_active_seconds_limit = float(
            profile["manager_max_active_seconds_total"]
        )
        self.manager_event_seconds_limit = float(
            profile["manager_max_active_seconds_per_event"]
        )
        self.manager_interventions_limit = int(profile["manager_max_interventions"])
        self.manager_shutdown_grace = float(profile["manager_shutdown_grace_seconds"])
        self.candidate_patch_validation = dict(
            profile.get("candidate_patch_validation", {})
        )
        self.manager_budget_tokens_total = 0
        self.manager_budget_active_seconds_total = 0.0
        self.manager_interventions_executed = 0
        self.manager_budget_exhausted = False
        self.manager_budget_reasons: list[str] = []
        self.manager_budget_phase = "setup"
        self.last_run_budget_interrupted = False
        self._write_budget_state()

    @contextmanager
    def _phase(self, name: str):
        previous = self.manager_budget_phase
        self.manager_budget_phase = name
        self._write_budget_state()
        try:
            yield
        finally:
            self.manager_budget_phase = previous
            self._write_budget_state()

    def _current_budget_reasons(self) -> list[str]:
        reasons = []
        if self.manager_iterations_total >= self.manager_iterations_limit:
            reasons.append("manager_iterations_total")
        if self.manager_budget_tokens_total >= self.manager_tokens_limit:
            reasons.append("manager_tokens_total")
        if (
            self.manager_budget_active_seconds_total
            >= self.manager_active_seconds_limit
        ):
            reasons.append("manager_active_seconds_total")
        return reasons

    def _refresh_budget_status(self) -> list[str]:
        reasons = self._current_budget_reasons()
        self.manager_budget_reasons = reasons
        self.manager_budget_exhausted = bool(reasons)
        return reasons

    def _budget_state(self) -> dict:
        reasons = self._refresh_budget_status()
        return {
            "schema_version": "async-manager-budget-v1",
            "policy": POLICY,
            "phase": self.manager_budget_phase,
            "exhausted": bool(reasons),
            "exhaustion_reasons": reasons,
            "limits": {
                "manager_iterations_total": self.manager_iterations_limit,
                "manager_tokens_total": self.manager_tokens_limit,
                "manager_active_seconds_total": self.manager_active_seconds_limit,
                "manager_active_seconds_per_event": self.manager_event_seconds_limit,
                "manager_interventions": self.manager_interventions_limit,
            },
            "usage": {
                "manager_iterations_total": self.manager_iterations_total,
                "manager_tokens_total": self.manager_budget_tokens_total,
                "manager_active_seconds_total": (
                    self.manager_budget_active_seconds_total
                ),
                "manager_interventions": self.manager_interventions_executed,
            },
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _write_budget_state(self) -> None:
        output = Path(self.config.output_dir)
        if not output.is_dir():
            return
        destination = output / "manager_budget.json"
        temporary = output / ".manager_budget.json.tmp"
        temporary.write_text(
            json.dumps(self._budget_state(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(destination)

    def _archive_and_discard_partial_manager_changes(self, reason: str) -> None:
        if not self.manager_worktree:
            return
        archive_dir = Path(self.config.output_dir) / "manager_budget_interruptions"
        archive_dir.mkdir(parents=True, exist_ok=True)
        sequence = len(list(archive_dir.glob("*.archive.json"))) + 1
        archive = archive_dir / f"{sequence:04d}.patch"
        from protocols.async_manager.artifacts import archive_worktree

        archive_worktree(self, self.manager_worktree, "HEAD", archive.with_suffix(""))
        # Archive failure must leave the private tree untouched, never clean in
        # a finally block. Shutdown confirmation is required by the caller.
        self._command(
            f"git -C {shlex.quote(self.manager_worktree)} reset --hard HEAD",
            timeout=120,
        )
        self._command(
            f"git -C {shlex.quote(self.manager_worktree)} clean -fd", timeout=120
        )
        (archive.with_suffix(".json")).write_text(
            json.dumps(
                {
                    "reason": reason,
                    "phase": self.manager_budget_phase,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    def _desired_event_iterations(self) -> int:
        remaining = max(
            1, self.manager_iterations_limit - self.manager_iterations_total
        )
        return min(int(self.config.manager_max_iterations), remaining)

    def _prepare_budgeted_conversation(self) -> bool:
        """Select the remote session before a caller records its baselines.

        A conversation's iteration cap is persisted by the remote server when
        that conversation is created.  Therefore a reduced final slice of the
        task budget requires a fresh transport session.  This preparation must
        happen before the prompt is sent and before phase metrics are sampled;
        rotating inside ``run_active_conversation`` loses the prompt and makes
        old/new-session metric deltas negative.
        """

        reasons = self._refresh_budget_status()
        if reasons:
            self.last_termination_reason = "manager_budget_exhausted"
            self.last_iteration_cap_hit = "manager_iterations_total" in reasons
            self.last_run_budget_interrupted = True
            self.log("Manager budget exhausted: " + ", ".join(reasons))
            self._write_budget_state()
            return False

        desired = self._desired_event_iterations()
        conversation = getattr(self, "conversation", None)
        current_cap = getattr(conversation, "max_iteration_per_run", None)
        try:
            current_cap = int(current_cap)
        except (TypeError, ValueError):
            current_cap = None
        if (
            self.conversation_needs_reset
            or current_cap is None
            or current_cap > desired
        ):
            original_config_iterations = self.config.manager_max_iterations
            self.config.manager_max_iterations = desired
            self.conversation_needs_reset = True
            try:
                self.ensure_usable_conversation()
            finally:
                self.config.manager_max_iterations = original_config_iterations
            self.log(
                "Prepared a fresh manager transport session with an event "
                f"budget of {desired} iterations"
            )
        return True

    def send_message(self, message):
        """Guarantee that a prompt is sent to the session that will run it."""

        if not self._prepare_budgeted_conversation():
            return None
        return super().send_message(message)

    def run_active_conversation(self):
        """Enforce task and event limits around every manager conversation run."""
        reasons = self._refresh_budget_status()
        if reasons:
            self.last_termination_reason = "manager_budget_exhausted"
            self.last_iteration_cap_hit = "manager_iterations_total" in reasons
            self.last_run_budget_interrupted = True
            self.log("Manager budget exhausted: " + ", ".join(reasons))
            self._write_budget_state()
            return

        desired_event_iterations = self._desired_event_iterations()
        requested_iterations = int(self.conversation.max_iteration_per_run)
        if requested_iterations > desired_event_iterations:
            raise RuntimeError(
                "Async-Manager conversation was not prepared before its prompt: "
                f"remote cap={self.conversation.max_iteration_per_run}, "
                f"required cap={desired_event_iterations}"
            )
        run_iterations = min(requested_iterations, desired_event_iterations)
        remaining_seconds = max(
            1.0,
            self.manager_active_seconds_limit
            - self.manager_budget_active_seconds_total,
        )
        event_timeout = max(
            1.0, min(self.manager_event_seconds_limit, remaining_seconds)
        )
        active_conversation = self.conversation
        original_iterations = active_conversation.max_iteration_per_run
        from protocols.async_manager.timeouts import manager_timeout

        timeout_token = manager_timeout.set(event_timeout)
        active_conversation.max_iteration_per_run = run_iterations
        before = extract_conversation_metrics(active_conversation)
        started = time.monotonic()
        self.last_run_budget_interrupted = False
        try:
            try:
                return super().run_active_conversation()
            except RuntimeError as error:
                if "Run timed out after" not in str(error):
                    if not (
                        self.last_iteration_cap_hit
                        and self.last_termination_reason == "iteration_limit"
                    ):
                        self._record_runtime_error(error)
                    raise
                self.last_run_budget_interrupted = True
                self.last_termination_reason = "manager_event_time_budget_exhausted"
                shutdown = self._interrupt_and_confirm(self.last_termination_reason)
                if not shutdown["confirmed"]:
                    self._record_runtime_error(
                        RuntimeError(
                            "Manager event timed out and remote interruption could "
                            "not be confirmed"
                        ),
                        kind="shutdown_confirmation_error",
                    )
                    raise RuntimeError(
                        "Manager shutdown unconfirmed; private workspace retained"
                    ) from error
                try:
                    self._archive_and_discard_partial_manager_changes(
                        self.last_termination_reason
                    )
                except Exception as cleanup_error:
                    self._record_runtime_error(cleanup_error, kind="cleanup_error")
                self.log(
                    "Manager event reached its active-time budget; discarded and "
                    "archived the incomplete private-worktree patch"
                )
                return None
            except Exception as error:
                self._record_runtime_error(error)
                raise
        except KeyboardInterrupt:
            self.last_run_budget_interrupted = True
            self.last_termination_reason = "operator_cancelled"
            shutdown = self._interrupt_and_confirm("operator_cancelled")
            try:
                if shutdown["confirmed"]:
                    self._archive_and_discard_partial_manager_changes(
                        "operator_cancelled"
                    )
            except Exception as cleanup_error:
                self._record_runtime_error(cleanup_error, kind="cleanup_error")
            raise
        finally:
            elapsed = time.monotonic() - started
            after = extract_conversation_metrics(active_conversation)
            self.manager_budget_active_seconds_total += elapsed
            self.manager_budget_tokens_total += max(
                0, int(after["total_tokens"]) - int(before["total_tokens"])
            )
            active_conversation.max_iteration_per_run = original_iterations
            manager_timeout.reset(timeout_token)
            self._write_budget_state()

    def _record_runtime_error(self, error: BaseException, kind="manager_run_error"):
        output = Path(self.config.output_dir)
        if not output.is_dir():
            return
        try:
            conversation = self.conversation
            record = {
                "schema_version": "async-manager-runtime-error-v1",
                "policy": POLICY,
                "kind": kind,
                "phase": self.manager_budget_phase,
                "conversation_id": (str(getattr(conversation, "id", "") or "") or None),
                "type": type(error).__name__,
                "detail": str(error),
                "termination_reason": self.last_termination_reason,
                "traceback": traceback.format_exc(),
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }
            with (output / "manager_runtime_errors.jsonl").open(
                "a", encoding="utf-8"
            ) as stream:
                stream.write(json.dumps(record, sort_keys=True, default=str) + "\n")
        except Exception as logging_error:
            # Diagnostics must never replace the manager exception being
            # diagnosed. Keep the original exception active for the caller.
            self.log(
                "Warning: could not persist Async-Manager runtime error: "
                f"{type(logging_error).__name__}: {logging_error}"
            )

    def _interrupt_and_confirm(self, reason: str) -> dict:
        conversation = self.conversation
        result = {
            "reason": reason,
            "attempted": False,
            "confirmed": False,
            "initial_status": None,
            "final_status": None,
            "error": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if conversation is None:
            return result
        poll = getattr(conversation, "_poll_status_once", None)
        try:
            status = poll() if callable(poll) else None
            normalized = str(getattr(status, "value", status) or "").lower()
            result["initial_status"] = normalized or None
            terminal_states = {"finished", "paused", "stopped", "error", "idle"}
            if normalized in terminal_states:
                result["confirmed"] = True
                result["final_status"] = normalized or "not_running"
                return result
            result["attempted"] = True
            conversation.interrupt()
            deadline = time.monotonic() + self.manager_shutdown_grace
            while time.monotonic() < deadline:
                status = poll() if callable(poll) else None
                normalized = str(getattr(status, "value", status) or "").lower()
                if normalized in terminal_states:
                    result["confirmed"] = True
                    result["final_status"] = normalized or "not_running"
                    break
                time.sleep(0.5)
            if not result["confirmed"]:
                result["final_status"] = normalized or "unknown"
        except Exception as error:
            result["error"] = f"{type(error).__name__}: {error}"
        return result

    def _write_shutdown(self, result: dict) -> None:
        output = Path(self.config.output_dir)
        if output.is_dir():
            (output / "manager_shutdown.json").write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

    def _skipped_intervention(self, event: dict, reasons: list[str]) -> dict:
        self.intervention_sequence += 1
        sequence = self.intervention_sequence
        head = self.current_head()
        evidence = self._event_evidence(event, head)
        prompt_dir = Path(self.config.output_dir) / "manager_interventions"
        prompt_dir.mkdir(parents=True, exist_ok=True)
        (prompt_dir / f"{sequence:04d}.prompt.txt").write_text(
            "Manager intervention skipped because the task-level budget was "
            "exhausted.\nReasons: " + ", ".join(reasons) + "\n",
            encoding="utf-8",
        )
        patch = self._write_patch(sequence, head, [])
        import hashlib

        return {
            "schema_version": "async-manager-intervention-v1",
            "protocol": "async_manager",
            "policy": POLICY,
            "sequence": sequence,
            "trigger": evidence["specialist"],
            "specialist_integration": evidence["integration"],
            "specialist_checkpoint_id": evidence["dependency_checkpoint"].get(
                "checkpoint_id"
            ),
            "head_before": head,
            "manager_workspace": self.manager_worktree,
            "allowed_paths": self.manager_scopes,
            "changed_paths": [],
            "rejected_paths": [],
            "patch": patch.relative_to(self.config.output_dir).as_posix(),
            "patch_sha256": hashlib.sha256(patch.read_bytes()).hexdigest(),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "duration": 0.0,
            "cost": 0.0,
            "tokens": 0,
            "iterations": 0,
            "max_iterations": 0,
            "execution_error": None,
            "termination_reason": "manager_budget_exhausted",
            "budget_exhaustion_reasons": reasons,
            "status": "budget_exhausted",
            "accepted": False,
            "manager_checkpoint_id": None,
        }

    def intervene(self, event: dict) -> dict:
        reasons = self._refresh_budget_status()
        if self.manager_interventions_executed >= self.manager_interventions_limit:
            reasons = [*reasons, "manager_interventions"]
        if reasons:
            record = self._skipped_intervention(event, sorted(set(reasons)))
            self._write_budget_state()
            return record
        self.manager_interventions_executed += 1
        with self._phase("online_intervention"):
            self._prepare_budgeted_conversation()
            record = super().intervene(event)
        record["policy"] = POLICY
        if self.last_run_budget_interrupted and not record.get("accepted"):
            record["status"] = "budget_exhausted"
            record["execution_error"] = None
            record["termination_reason"] = self.last_termination_reason
        self._write_budget_state()
        return record

    def scan_and_analyze(self):
        with self._phase("scan_analysis"):
            self._prepare_budgeted_conversation()
            return super().scan_and_analyze()

    def delegate_tasks(self):
        with self._phase("task_delegation"):
            self._prepare_budgeted_conversation()
            return super().delegate_tasks()

    def assign_task(self, *args, **kwargs):
        if self._refresh_budget_status():
            self._write_budget_state()
            return {"assignments": [], "reasoning": "manager budget exhausted"}
        with self._phase("assign_task"):
            self._prepare_budgeted_conversation()
            return super().assign_task(*args, **kwargs)

    def explore_background(self, *args, **kwargs):
        if self._refresh_budget_status():
            self._write_budget_state()
            return {"findings": [], "budget_exhausted": True}
        with self._phase("background_exploration"):
            self._prepare_budgeted_conversation()
            return super().explore_background(*args, **kwargs)

    def final_review_all(self, subagent_results, max_iterations=30):
        if self._refresh_budget_status():
            self._write_budget_state()
            return {"skipped": True, "reason": "manager_budget_exhausted"}
        with self._phase("final_review"):
            self._prepare_budgeted_conversation()
            return super().final_review_all(
                subagent_results,
                max_iterations=min(max_iterations, self._desired_event_iterations()),
            )

    def prepare_final_evaluation(self):
        self._write_budget_state()
        return super().prepare_final_evaluation()

    def cleanup(self):
        shutdown = self._interrupt_and_confirm("workflow_cleanup")
        self._write_shutdown(shutdown)
        self._write_budget_state()
        if not shutdown["confirmed"]:
            raise RuntimeError(
                "Cannot confirm manager shutdown; retaining its private worktree"
            )
        return super().cleanup()


__all__ = ["BudgetedOnlineManager", "load_profile"]
