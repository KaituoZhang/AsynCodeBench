"""Persistent, event-driven manager with scoped online repair authority."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shlex
import sys
import threading
import time
import uuid
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from core.asyncodebench_manager import AsynCodeBenchManager
from core.control_plane_guard import (
    build_control_plane_guard_hook,
    combine_hook_configs,
)
from core.network_guard import build_network_guard_hook
from core.subagent import condenser_max_tokens
from core.utils import (
    PanelVisualizer,
    count_llm_iterations,
    extract_conversation_metrics,
    serialize_event,
)
from core.workspace_isolation import (
    build_workspace_guard_hook,
    private_remote_workspace,
)
from openhands.sdk import Agent, Conversation, LLMSummarizingCondenser
from openhands.sdk.context import AgentContext
from openhands.tools.preset.default import get_default_tools

from protocols.async_manager import POLICY, PROTOCOL
from protocols.async_manager.guard import build_guard
from protocols.async_manager.terminal_guard import build_terminal_guard
from protocols.asyncodebench.ordering import path_in_scope

PROTECTED_PARTS = frozenset(
    {".git", "tests", "test", "checkers", "manifests", "evaluators"}
)
DEFAULT_HEARTBEAT_SECONDS = 60.0
HEARTBEAT_ENV = "ASYNCODEBENCH_MANAGER_HEARTBEAT_SECONDS"


def dump(path, value) -> None:
    Path(path).write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _json_safe(value):
    """Normalize SDK identifiers and timestamps for protocol-local JSONL."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


def safe_production_path(path: str, scopes: list[str]) -> bool:
    candidate = PurePosixPath(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        return False
    if any(part in PROTECTED_PARTS for part in candidate.parts):
        return False
    return any(path_in_scope(path, [scope]) for scope in scopes)


class OnlineManager(AsynCodeBenchManager):
    """A single persistent manager that intervenes at integration boundaries.

    The inherited task analysis, delegation, specialist ownership, merge gate,
    and evaluator stay unchanged.  Only the manager conversation is moved into
    a private worktree and granted phase-gated file-editor authority.
    """

    active_instance = None

    def __init__(self, *args, **kwargs):
        task = kwargs.get("task")
        if task is None and len(args) >= 3:
            task = args[2]
        if task is None:
            raise TypeError("OnlineManager requires an AsynCodeBench task")

        # This is an instance-only capability switch.  The task class and the
        # released CAID manager policy remain unchanged.
        task.manager_must_be_read_only = False
        super().__init__(*args, **kwargs)
        self.read_only_manager_policy = False
        self.manager_worktree = None
        self.manager_mode_file = None
        self.manager_scopes = self._manager_scopes()
        self.pending_integration_event = None
        self.intervention_sequence = 0
        self.intervention_cost = 0.0
        self.intervention_tokens = 0
        self.intervention_duration = 0.0
        self.accepted_interventions = 0
        self.intervention_records = []
        self.manager_conversation_segments = 0
        self.recovered_conversation_metrics = {
            "cost": 0.0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        self._load_prompt_overrides()
        if OnlineManager.active_instance is not None:
            raise RuntimeError(
                "Only one online Async-Manager run is allowed per process"
            )
        OnlineManager.active_instance = self

    def _manager_scopes(self) -> list[str]:
        scopes = sorted(
            {
                path.rstrip("/")
                for assignment in self.active_scenario().get("assignments", [])
                for path in assignment.get("writable_paths", [])
                if str(path).strip()
            }
        )
        if not scopes or any(not safe_production_path(path, scopes) for path in scopes):
            raise RuntimeError(
                "Async-Manager manifest contains an unsafe or empty scope"
            )
        return scopes

    def _load_prompt_overrides(self) -> None:
        prompt_path = Path(__file__).with_name("prompts.json")
        overrides = json.loads(prompt_path.read_text(encoding="utf-8"))
        self.prompts = dict(self.prompts)
        self.prompts["user_instruction"] = overrides["user_instruction"]
        self.prompts["scan_analysis"] = overrides["scan_analysis"]
        self.prompts["assign_task"] = overrides["assign_task"]
        self.prompts["manager_final_review_all"] = overrides["final_review"]
        self.intervention_prompt = (
            Path(__file__)
            .with_name("intervention_prompt.txt")
            .read_text(encoding="utf-8")
        )

    def _command(self, command: str, timeout: int = 60) -> str:
        result = self.workspace.execute_command(command, timeout=timeout)
        if result.exit_code != 0:
            raise RuntimeError(
                "Async-Manager harness command failed: "
                + (result.stderr or result.stdout or command)
            )
        return result.stdout or ""

    def current_head(self) -> str:
        return self._command(
            f"git -C {shlex.quote(self.repo_dir)} rev-parse HEAD", timeout=30
        ).strip()

    def _set_mode(self, mode: str) -> None:
        if mode not in {"observe", "intervene"}:
            raise ValueError(f"Unknown manager authorization mode: {mode}")
        if not self.manager_mode_file:
            raise RuntimeError("Manager authorization state is not initialized")
        command = (
            "printf '%s\\n' "
            + shlex.quote(mode)
            + " > "
            + shlex.quote(self.manager_mode_file)
        )
        self._command(command, timeout=30)

    def _sync_manager_worktree(self, head: str) -> None:
        root = shlex.quote(self.manager_worktree)
        self._command(f"git -C {root} reset --hard {shlex.quote(head)}", timeout=120)
        self._command(f"git -C {root} clean -fd", timeout=120)
        observed = self._command(f"git -C {root} rev-parse HEAD", timeout=30).strip()
        if observed != head:
            raise RuntimeError(
                "Private manager worktree did not synchronize to integrated HEAD"
            )

    def _validate_worktree_runtime_with_wrapper(
        self, workspace, worktree_path: str, owner: str
    ) -> None:
        """Validate a TVM worktree with the image's worktree-aware Python.

        The PR-hard image prepends its runtime environment to ``PATH``, while
        ``/usr/local/bin/python`` is the wrapper that derives ``PYTHONPATH``
        from the current Git worktree.  This protocol-local helper deliberately
        leaves the released task adapter and all legacy protocols unchanged.
        """

        quoted_worktree = shlex.quote(str(worktree_path))
        import_check = (
            "import pathlib, tvm; "
            "root=pathlib.Path.cwd().resolve(); "
            "loaded=pathlib.Path(tvm.__file__).resolve(); "
            "expected=(root/'python').resolve(); "
            "assert loaded.is_relative_to(expected), "
            "f'loaded {loaded}, expected beneath {expected}'; "
            "print(loaded)"
        )
        result = workspace.execute_command(
            f"cd {quoted_worktree} && test -x /usr/local/bin/python && "
            f"/usr/local/bin/python -c {shlex.quote(import_check)}",
            timeout=120,
        )
        if result.exit_code != 0:
            raise RuntimeError(
                f"Async-Manager {owner} worktree runtime isolation check failed for "
                f"{worktree_path}: {result.stderr or result.stdout}"
            )

    def _prepare_manager_worktree_runtime(self) -> None:
        """Prepare a private runtime without changing legacy task behavior.

        PR-hard installs a worktree-aware Python wrapper at
        ``/usr/local/bin/python``. Agent-server environments can place another
        interpreter earlier on ``PATH``; the legacy validator intentionally
        uses that ambient ``python``. Select the installed wrapper explicitly
        for this additive protocol instead of modifying the shared task adapter.
        """

        refresher = getattr(self.task, "refresh_source_build", None)
        if refresher is None:
            preparer = getattr(self.task, "prepare_worktree_runtime", None)
            if preparer is not None:
                preparer(self.workspace, self.manager_worktree)
            return

        self.log(
            "Preparing the manager private-worktree runtime "
            "(one-time TVM source build)..."
        )
        started = time.monotonic()
        build = refresher(self.workspace, self.manager_worktree)
        if build.get("status") != "passed":
            raise RuntimeError(
                "Async-Manager private-worktree source build failed for "
                f"{self.manager_worktree} ({build.get('status')}):\n"
                f"{build.get('output_excerpt', '')}"
            )

        self._validate_worktree_runtime_with_wrapper(
            self.workspace, self.manager_worktree, "private-manager"
        )
        self.log(
            "Manager private-worktree runtime ready in "
            f"{time.monotonic() - started:.1f}s"
        )

    def setup(self, mode="multi_agent"):
        if mode != "multi_agent":
            raise RuntimeError(
                "OnlineManager is only valid for the async_manager protocol"
            )
        self.log("Setting up persistent online manager in a private worktree...")
        head = self.current_head()
        if self.manager_worktree is None:
            token = uuid.uuid4().hex
            self.manager_worktree = f"/workspace/async-manager-{token}"
            self.manager_mode_file = f"/tmp/async-manager-mode-{token}"
            self._command(
                f"git -C {shlex.quote(self.repo_dir)} worktree add --detach "
                f"{shlex.quote(self.manager_worktree)} {shlex.quote(head)}",
                timeout=120,
            )
            self._set_mode("observe")

            started = time.monotonic()
            try:
                self._prepare_manager_worktree_runtime()
            finally:
                self.worktree_preparation_seconds += time.monotonic() - started
        else:
            # Conversation recovery must retain the same logical manager
            # workspace and never create a fresh coding budget or leaked tree.
            self._sync_manager_worktree(head)
            self._set_mode("observe")

        tools = [
            tool
            for tool in get_default_tools(enable_browser=False)
            if getattr(tool, "name", "") in {"terminal", "file_editor"}
        ]
        format_args = self.task.get_prompt_format_args(self.config)
        format_args["manager_workspace"] = self.manager_worktree
        instruction = self.prompts["user_instruction"].format(**format_args)
        condenser = LLMSummarizingCondenser(
            llm=self.llm.model_copy(update={"usage_id": "condenser"}),
            max_size=200,
            max_tokens=condenser_max_tokens(self.llm),
            keep_first=4,
        )
        self.agent = Agent(
            llm=self.llm,
            tools=tools,
            agent_context=AgentContext(system_message_suffix=instruction),
            condenser=condenser,
        )
        hooks = combine_hook_configs(
            build_control_plane_guard_hook(),
            build_workspace_guard_hook(self.manager_worktree, self.repo_dir),
        )
        hooks = combine_hook_configs(hooks, build_terminal_guard())
        hooks = combine_hook_configs(
            hooks,
            build_guard(
                self.manager_worktree,
                self.manager_mode_file,
                self.manager_scopes,
            ),
        )
        if getattr(self.task, "deny_agent_network", False):
            hooks = combine_hook_configs(hooks, build_network_guard_hook())
        remote = private_remote_workspace(self.workspace, self.manager_worktree)
        self.conversation_mode = mode
        self.conversation = Conversation(
            agent=self.agent,
            workspace=remote,
            max_iteration_per_run=self.config.manager_max_iterations,
            visualizer=PanelVisualizer(),
            hook_config=hooks,
        )
        self.manager_conversation_segments += 1
        self.conversation_needs_reset = False
        self.log(
            "Persistent online manager ready; terminal is read-only and "
            "file-editor writes are phase-gated"
        )

    def ensure_usable_conversation(self):
        """Recover a terminal transport session without changing manager identity."""

        if not self.conversation_needs_reset:
            return
        previous = self.conversation
        if previous is not None:
            metrics = extract_conversation_metrics(previous)
            for field in self.recovered_conversation_metrics:
                self.recovered_conversation_metrics[field] += metrics.get(field, 0)
            self.retired_conversations.append(previous)
            try:
                previous.close()
            except Exception as error:
                self.log(f"Warning: could not close retired manager session: {error}")
        self.log(
            "Recovering the persistent logical manager in a fresh transport "
            "session over the same private worktree"
        )
        self.setup(mode=self.conversation_mode)

    def save_events(self, phase, event_start_idx=0):
        """Write Async-Manager events without leaking SDK-only JSON types."""

        if not self.conversation or not self.output_logger:
            return

        events = list(self.conversation.state.events)
        if event_start_idx >= len(events):
            return

        new_events = events[event_start_idx:]
        self.log(
            f"Saving {len(new_events)} new events (phase={phase}) "
            "to manager_events.jsonl..."
        )
        for idx, event in enumerate(new_events):
            global_idx = event_start_idx + idx
            serialized = serialize_event(event, global_idx)
            serialized["engineer_id"] = "manager"
            serialized["phase"] = phase
            serialized["start_time"] = serialized.get("timestamp")
            if global_idx + 1 < len(events):
                serialized["end_time"] = getattr(
                    events[global_idx + 1], "timestamp", None
                )
            else:
                serialized["end_time"] = datetime.now(timezone.utc).isoformat()
            self.output_logger.log_agent_event(
                "manager", _json_safe(serialized)
            )

    def collect_and_merge(self, subagent_result, output_logger=None):
        result = super().collect_and_merge(subagent_result, output_logger)
        if self.pending_integration_event is not None:
            raise RuntimeError(
                "Previous Async-Manager integration event was not consumed"
            )
        self.pending_integration_event = {
            "subagent_result": subagent_result,
            "collect_result": dict(result),
        }
        return result

    def consume_integration_event(self, checkpoint: dict | None):
        event = self.pending_integration_event
        self.pending_integration_event = None
        if event is None:
            return None
        event["specialist_checkpoint"] = checkpoint
        return event

    @staticmethod
    def _compact_checkpoint(checkpoint: dict | None) -> dict:
        if not checkpoint:
            return {}
        return {
            "checkpoint_id": checkpoint.get("checkpoint_id"),
            "logical_step": checkpoint.get("logical_step"),
            "pytest_summary": checkpoint.get("pytest_summary"),
            "timed_out": checkpoint.get("timed_out"),
            "dependency_results": checkpoint.get("dependency_results", []),
            "integrated_workspace_version": checkpoint.get(
                "integrated_workspace_version"
            ),
        }

    def _event_evidence(self, event: dict, head: str) -> dict:
        result = event["subagent_result"]
        collect = event["collect_result"]
        return {
            "protocol": PROTOCOL,
            "policy": POLICY,
            "event": "specialist_integration_checkpoint",
            "integrated_head": head,
            "manager_workspace": self.manager_worktree,
            "manager_writable_scope": self.manager_scopes,
            "specialist": {
                "agent_id": result.engineer_id,
                "task_id": result.task_id,
                "round": result.round_num,
                "conversation_success": result.success,
                "error": result.error,
                "commit": result.commit_hash,
                "reported_files": result.files_modified or [],
                "diff_excerpt": str(result.git_diff or "")[-12000:],
            },
            "integration": {
                "merged": collect.get("merged", False),
                "method": collect.get("merge_method"),
                "message": collect.get("merge_message"),
                "review_notes": collect.get("review_notes"),
                "conflict_files": collect.get("conflict_files", []),
            },
            "dependency_checkpoint": self._compact_checkpoint(
                event.get("specialist_checkpoint")
            ),
        }

    def _heartbeat_seconds(self) -> float:
        """Return a safe, observability-only heartbeat interval."""

        raw = os.getenv(HEARTBEAT_ENV, str(DEFAULT_HEARTBEAT_SECONDS))
        try:
            interval = float(raw)
        except (TypeError, ValueError):
            interval = DEFAULT_HEARTBEAT_SECONDS
            self.log(
                f"Ignoring invalid {HEARTBEAT_ENV}={raw!r}; "
                f"using {DEFAULT_HEARTBEAT_SECONDS:g}s"
            )
        if not math.isfinite(interval) or interval <= 0:
            interval = DEFAULT_HEARTBEAT_SECONDS
            self.log(
                f"Ignoring non-positive {HEARTBEAT_ENV}={raw!r}; "
                f"using {DEFAULT_HEARTBEAT_SECONDS:g}s"
            )
        return interval

    def _progress_log(self, message: str) -> None:
        """Emit a heartbeat line immediately, including under redirected stdout."""

        self.log(message)
        with suppress(AttributeError, OSError):
            sys.stdout.flush()

    @staticmethod
    def _intervention_trigger_label(evidence: dict) -> tuple[str, str]:
        specialist = evidence.get("specialist", {})
        checkpoint = evidence.get("dependency_checkpoint", {})
        agent = specialist.get("agent_id") or "unknown-agent"
        round_num = specialist.get("round") or "?"
        checkpoint_id = checkpoint.get("checkpoint_id") or "unknown-checkpoint"
        return f"{agent}:round{round_num}", checkpoint_id

    def _run_intervention_turn_with_heartbeat(
        self, sequence: int, evidence: dict, prompt: str
    ) -> None:
        """Run one manager turn while emitting protocol-local progress logs.

        The heartbeat thread only writes human-readable log messages. It does
        not poll or mutate the conversation, scheduler, workspace, or metrics.
        """

        trigger, checkpoint_id = self._intervention_trigger_label(evidence)
        interval = self._heartbeat_seconds()
        stopped = threading.Event()
        started = time.monotonic()

        self._progress_log(
            f"Online intervention #{sequence} starting: trigger={trigger}, "
            f"checkpoint={checkpoint_id}"
        )
        self._progress_log(
            "Integration processing is serialized at this checkpoint; "
            "in-flight specialists may continue remotely, while completed "
            "results are consumed after this intervention"
        )

        def emit_heartbeat() -> None:
            heartbeat = 0
            while not stopped.wait(interval):
                heartbeat += 1
                elapsed = time.monotonic() - started
                self._progress_log(
                    f"Online intervention #{sequence} still running: "
                    f"elapsed={elapsed:.0f}s, heartbeat={heartbeat}, "
                    f"trigger={trigger}, checkpoint={checkpoint_id}"
                )

        thread = threading.Thread(
            target=emit_heartbeat,
            name=f"async-manager-heartbeat-{sequence}",
            daemon=True,
        )
        thread.start()
        try:
            self.send_message(prompt)
            self.run_active_conversation()
        except BaseException:
            elapsed = time.monotonic() - started
            self._progress_log(
                f"Online intervention #{sequence} conversation exited with "
                f"an error after {elapsed:.1f}s; validating recovery state"
            )
            raise
        else:
            elapsed = time.monotonic() - started
            self._progress_log(
                f"Online intervention #{sequence} conversation returned after "
                f"{elapsed:.1f}s; validating scoped workspace changes"
            )
        finally:
            stopped.set()
            thread.join(timeout=1.0)

    def _log_intervention_result(self, record: dict) -> None:
        self._progress_log(
            f"Online intervention #{record['sequence']} finalized: "
            f"status={record.get('status', 'unknown')}, "
            f"accepted={record.get('accepted', False)}, "
            f"duration={record.get('duration', 0.0):.1f}s, "
            f"iterations={record.get('iterations', 0)}/"
            f"{record.get('max_iterations', '?')}, "
            f"changed_paths={len(record.get('changed_paths', []))}, "
            f"rejected_paths={len(record.get('rejected_paths', []))}"
        )

    def _changed_paths(self) -> list[str]:
        self.task._clean_transient_test_artifacts(self.workspace, self.manager_worktree)
        status = self._command(
            f"git -C {shlex.quote(self.manager_worktree)} status --porcelain",
            timeout=30,
        )
        return sorted(set(self._status_paths(status)))

    def _write_patch(self, sequence: int, base_head: str, changed: list[str]) -> Path:
        patch_dir = Path(self.config.output_dir) / "manager_interventions"
        patch_dir.mkdir(parents=True, exist_ok=True)
        patch_path = patch_dir / f"{sequence:04d}.patch"
        if changed:
            paths = " ".join(shlex.quote(path) for path in changed)
            self._command(
                f"git -C {shlex.quote(self.manager_worktree)} add -- {paths}",
                timeout=60,
            )
            patch = self._command(
                f"git -C {shlex.quote(self.manager_worktree)} diff --cached "
                f"--binary {shlex.quote(base_head)}",
                timeout=60,
            )
        else:
            patch = ""
        patch_path.write_text(patch, encoding="utf-8")
        return patch_path

    def _candidate_validation_dependencies(
        self, metrics: dict, changed: list[str]
    ) -> list[dict]:
        changed_paths = set(changed)
        changed_subproblems = set()
        try:
            scenario = self.active_scenario()
        except Exception:
            scenario = {}
        for assignment in scenario.get("assignments", []):
            if changed_paths.intersection(assignment.get("writable_paths", [])):
                subproblem = assignment.get("subproblem_id")
                if subproblem:
                    changed_subproblems.add(subproblem)

        affected = []
        for dependency in metrics.get("dependency_points", []):
            dependency_paths = set(dependency.get("producer_files", [])) | set(
                dependency.get("consumer_files", [])
            )
            dependency_subproblems = {
                dependency.get("producer_subproblem"),
                dependency.get("consumer_subproblem"),
            }
            if changed_paths.intersection(dependency_paths) or (
                changed_subproblems.intersection(dependency_subproblems)
            ):
                affected.append(dependency)
        return affected

    @staticmethod
    def _probe_selector_results(report: dict, selectors: list[str]) -> dict:
        outcomes = {}
        for test in report.get("tests", []) or []:
            nodeid = test.get("nodeid")
            outcome = test.get("outcome")
            if nodeid:
                outcomes[nodeid] = outcome

        results = {}
        for selector in selectors:
            matched = [
                outcome
                for nodeid, outcome in outcomes.items()
                if nodeid == selector
                or re.sub(r"\[[^\]]+\]$", "", nodeid) == selector
            ]
            if not matched:
                results[selector] = {"status": "not_collected", "passed": False}
            else:
                passed = all(outcome == "passed" for outcome in matched)
                results[selector] = {
                    "status": "passed" if passed else "failed",
                    "passed": passed,
                }
        return results

    def _run_candidate_dependency_probes(
        self, sequence: int, selectors: list[str], timeout: int
    ) -> dict:
        token = uuid.uuid4().hex
        report_path = f"/tmp/async-manager-validation-{token}.json"
        output_path = f"/tmp/async-manager-validation-{token}.txt"
        quoted_worktree = shlex.quote(self.manager_worktree)
        selector_args = " ".join(shlex.quote(selector) for selector in selectors)
        command = (
            f"cd {quoted_worktree} && "
            f"export PYTHONPATH={quoted_worktree}/src:{quoted_worktree}:$PYTHONPATH "
            f"&& timeout {timeout}s python -m pytest "
            f"--json-report --json-report-file={shlex.quote(report_path)} "
            "--continue-on-collection-errors "
            f"{selector_args} > {shlex.quote(output_path)} 2>&1"
        )
        run = self.workspace.execute_command(command, timeout=timeout + 30)
        report_result = self.workspace.execute_command(
            f"cat {shlex.quote(report_path)} 2>/dev/null || echo '{{}}'",
            timeout=30,
        )
        output_result = self.workspace.execute_command(
            f"cat {shlex.quote(output_path)} 2>/dev/null || true",
            timeout=30,
        )
        self.workspace.execute_command(
            f"rm -f -- {shlex.quote(report_path)} {shlex.quote(output_path)}",
            timeout=30,
        )
        try:
            report = json.loads(report_result.stdout or "{}")
        except json.JSONDecodeError:
            report = {}
        results = self._probe_selector_results(report, selectors)
        return {
            "exit_code": run.exit_code,
            "timed_out": str(run.exit_code) in {"124", "-1"},
            "selector_results": results,
            "summary": {
                "total": len(results),
                "passed": sum(item["passed"] for item in results.values()),
                "failed": sum(
                    item["status"] == "failed" for item in results.values()
                ),
                "not_collected": sum(
                    item["status"] == "not_collected" for item in results.values()
                ),
            },
            "output_excerpt": (output_result.stdout or "")[-4000:],
            "sequence": sequence,
        }

    def _validate_candidate_patch(
        self,
        *,
        sequence: int,
        event: dict,
        changed: list[str],
        head_before: str,
        patch_sha: str,
        termination_reason: str,
    ) -> dict:
        validation_started = time.monotonic()
        settings = dict(getattr(self, "candidate_patch_validation", {}) or {})
        if not settings.get("enabled"):
            return {
                "required": False,
                "passed": True,
                "mode": "legacy_scope_only",
                "termination_reason": termination_reason,
            }

        validation_dir = (
            Path(self.config.output_dir)
            / "manager_candidate_validations"
            / f"{sequence:04d}"
        )
        validation_dir.mkdir(parents=True, exist_ok=True)
        validation_path = validation_dir / "validation.json"
        result = {
            "schema_version": "async-manager-candidate-validation-v1",
            "required": True,
            "passed": False,
            "mode": settings.get("mode"),
            "termination_reason": termination_reason,
            "completion_signal": termination_reason == "agent_finish",
            "changed_paths": changed,
            "reason_codes": [],
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            checkpoint = event.get("specialist_checkpoint") or {}
            raw_metrics_path = checkpoint.get("metrics_manifest")
            if not raw_metrics_path:
                manifest_paths = getattr(self.task, "manifest_paths", {})
                if isinstance(manifest_paths, dict):
                    raw_metrics_path = manifest_paths.get("metrics")
            metrics_path = Path(raw_metrics_path) if raw_metrics_path else None
            if metrics_path is None or not metrics_path.is_file():
                result["reason_codes"].append("metrics_manifest_missing")
            else:
                metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
                affected = self._candidate_validation_dependencies(metrics, changed)
                selectors = sorted(
                    {
                        selector
                        for dependency in affected
                        for selector in dependency.get("integrated_probe_tests", [])
                    }
                )
                result["metrics_manifest"] = str(metrics_path)
                result["affected_dependencies"] = [
                    dependency.get("dependency_id") for dependency in affected
                ]
                result["selectors"] = selectors
                result["selector_count"] = len(selectors)
                max_selectors = max(1, int(settings.get("max_selectors", 40)))
                result["max_selectors"] = max_selectors
                if not affected or not selectors:
                    result["reason_codes"].append(
                        "changed_paths_not_covered_by_dependency_manifest"
                    )
                elif len(selectors) > max_selectors:
                    result["reason_codes"].append("selector_limit_exceeded")
                else:
                    baseline = checkpoint.get("probe_test_results") or {}
                    missing_baseline = [
                        selector for selector in selectors if selector not in baseline
                    ]
                    result["missing_baseline_selectors"] = missing_baseline
                    if missing_baseline:
                        result["reason_codes"].append("baseline_probe_evidence_missing")

                    source_build = {"status": "not_required"}
                    refresh = getattr(self.task, "refresh_source_build", None)
                    if refresh is not None:
                        source_build = refresh(
                            self.workspace, self.manager_worktree
                        )
                    result["source_build"] = source_build
                    if source_build.get("status") not in {
                        "passed",
                        "not_required",
                    }:
                        result["reason_codes"].append("source_build_failed")
                    else:
                        timeout = max(
                            30, int(settings.get("timeout_seconds", 600))
                        )
                        result["timeout_seconds"] = timeout
                        probes = self._run_candidate_dependency_probes(
                            sequence, selectors, timeout
                        )
                        result["probe"] = probes
                        if probes["timed_out"]:
                            result["reason_codes"].append("dependency_probe_timed_out")
                        if (
                            settings.get("require_all_selectors_collected", True)
                            and probes["summary"]["not_collected"]
                        ):
                            result["reason_codes"].append(
                                "dependency_selectors_not_collected"
                            )
                        regressions = [
                            selector
                            for selector in selectors
                            if baseline.get(selector, {}).get("passed")
                            and not probes["selector_results"]
                            .get(selector, {})
                            .get("passed")
                        ]
                        result["regressions"] = regressions
                        if (
                            settings.get("require_no_regression", True)
                            and regressions
                        ):
                            result["reason_codes"].append(
                                "previously_passing_selector_regressed"
                            )

            post_validation_paths = self._changed_paths()
            result["post_validation_changed_paths"] = post_validation_paths
            if post_validation_paths != changed:
                result["reason_codes"].append("candidate_changed_during_validation")
            staged_patch = self._command(
                f"git -C {shlex.quote(self.manager_worktree)} diff --cached "
                f"--binary {shlex.quote(head_before)}",
                timeout=60,
            )
            post_validation_sha = hashlib.sha256(staged_patch.encode()).hexdigest()
            result["post_validation_patch_sha256"] = post_validation_sha
            if post_validation_sha != patch_sha:
                result["reason_codes"].append("candidate_patch_changed_during_validation")
        except Exception as error:
            result["reason_codes"].append("candidate_validation_error")
            result["error"] = f"{type(error).__name__}: {error}"

        result["reason_codes"] = sorted(set(result["reason_codes"]))
        result["passed"] = not result["reason_codes"]
        result["duration_seconds"] = time.monotonic() - validation_started
        result["completed_at"] = datetime.now(timezone.utc).isoformat()
        result["artifact"] = validation_path.relative_to(
            self.config.output_dir
        ).as_posix()
        dump(validation_path, result)
        result["artifact_sha256"] = hashlib.sha256(
            validation_path.read_bytes()
        ).hexdigest()
        return result

    def _refresh_triggering_specialist(
        self, event: dict, head: str, sequence: int
    ) -> dict:
        """Make any later round from the completed specialist see manager work.

        The triggering conversation is no longer running at this event boundary.
        Preserve its full pre-refresh diff, then advance that private worktree to
        the newly integrated manager commit. Other in-flight specialists retain
        their original async-private snapshot by design.
        """

        result = event["subagent_result"]
        worktree = getattr(result, "worktree_path", None)
        if not worktree:
            return {"refreshed": False, "reason": "no_worktree"}
        archive_dir = Path(self.config.output_dir) / "manager_interventions"
        archive_path = archive_dir / f"{sequence:04d}.triggering-specialist.patch"
        merge_base = self.workspace.execute_command(
            f"git -C {shlex.quote(worktree)} merge-base HEAD {shlex.quote(head)}",
            timeout=30,
        )
        base = (
            merge_base.stdout.strip()
            if merge_base.exit_code == 0 and merge_base.stdout.strip()
            else "HEAD"
        )
        diff = self.workspace.execute_command(
            f"git -C {shlex.quote(worktree)} diff --binary {shlex.quote(base)}..HEAD",
            timeout=60,
        )
        dirty = self.workspace.execute_command(
            f"git -C {shlex.quote(worktree)} diff --binary", timeout=60
        )
        archive_path.write_text(
            (diff.stdout if diff.exit_code == 0 else "")
            + (dirty.stdout if dirty.exit_code == 0 else ""),
            encoding="utf-8",
        )
        reset = self.workspace.execute_command(
            f"git -C {shlex.quote(worktree)} reset --hard {shlex.quote(head)}",
            timeout=120,
        )
        clean = self.workspace.execute_command(
            f"git -C {shlex.quote(worktree)} clean -fd", timeout=120
        )
        verify = self.workspace.execute_command(
            f"git -C {shlex.quote(worktree)} rev-parse HEAD", timeout=30
        )
        refreshed = (
            reset.exit_code == 0
            and clean.exit_code == 0
            and verify.exit_code == 0
            and verify.stdout.strip() == head
        )
        if not refreshed:
            raise RuntimeError(
                "Could not refresh the triggering specialist after manager integration"
            )
        return {
            "refreshed": True,
            "worktree": worktree,
            "head": head,
            "archive": archive_path.relative_to(self.config.output_dir).as_posix(),
            "archive_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
        }

    def intervene(self, event: dict) -> dict:
        """Run one bounded intervention turn and integrate a valid patch."""

        self.intervention_sequence += 1
        sequence = self.intervention_sequence
        started_at = datetime.now(timezone.utc)
        started = time.monotonic()
        head_before = self.current_head()
        if self.main_workspace_status():
            raise RuntimeError(
                "Integrated workspace is dirty before manager intervention"
            )
        self._sync_manager_worktree(head_before)
        evidence = self._event_evidence(event, head_before)
        prompt = self.intervention_prompt.format(
            event_json=json.dumps(evidence, indent=2, sort_keys=True)
        )
        prompt_path = (
            Path(self.config.output_dir)
            / "manager_interventions"
            / f"{sequence:04d}.prompt.txt"
        )
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(prompt, encoding="utf-8")

        self.ensure_usable_conversation()
        event_start = len(list(self.conversation.state.events))
        iteration_before = count_llm_iterations(self.conversation.state.events)
        metrics_before = extract_conversation_metrics(self.conversation)
        execution_error = None
        self._set_mode("intervene")
        try:
            self._run_intervention_turn_with_heartbeat(sequence, evidence, prompt)
        except Exception as error:
            execution_error = f"{type(error).__name__}: {error}"
            self.log(f"Online intervention ended with: {execution_error}")
        finally:
            self._set_mode("observe")

        termination_reason = getattr(
            self, "last_termination_reason", "completed_without_finish"
        )

        duration = time.monotonic() - started
        metrics_after = extract_conversation_metrics(self.conversation)
        cost = metrics_after["cost"] - metrics_before["cost"]
        tokens = metrics_after["total_tokens"] - metrics_before["total_tokens"]
        iterations = (
            count_llm_iterations(self.conversation.state.events) - iteration_before
        )
        self.intervention_cost += cost
        self.intervention_tokens += tokens
        self.intervention_duration += duration
        # The frozen cost writer already has a generic review lane.  Account
        # for online interventions there, then add a more precise subrecord.
        self.review_total_cost += cost
        self.review_total_tokens += tokens
        self.review_total_time += duration
        self.save_events(f"online_intervention_{sequence}", event_start)

        if self.current_head() != head_before or self.main_workspace_status():
            raise RuntimeError(
                "Integrated workspace changed out of band during manager intervention"
            )
        manager_head = self._command(
            f"git -C {shlex.quote(self.manager_worktree)} rev-parse HEAD",
            timeout=30,
        ).strip()
        if manager_head != head_before:
            raise RuntimeError(
                "Manager changed Git HEAD; only harness-owned commits are allowed"
            )

        changed = self._changed_paths()
        violations = [
            path
            for path in changed
            if not safe_production_path(path, self.manager_scopes)
        ]
        for path in changed:
            check = self.workspace.execute_command(
                f"test -L {shlex.quote(self.manager_worktree + '/' + path)}",
                timeout=30,
            )
            if check.exit_code == 0 and path not in violations:
                violations.append(path)
        patch_path = self._write_patch(sequence, head_before, changed)
        patch_sha = hashlib.sha256(patch_path.read_bytes()).hexdigest()

        record = {
            "schema_version": "async-manager-intervention-v1",
            "protocol": PROTOCOL,
            "policy": POLICY,
            "sequence": sequence,
            "trigger": evidence["specialist"],
            "specialist_integration": evidence["integration"],
            "specialist_checkpoint_id": evidence["dependency_checkpoint"].get(
                "checkpoint_id"
            ),
            "head_before": head_before,
            "manager_workspace": self.manager_worktree,
            "allowed_paths": self.manager_scopes,
            "changed_paths": changed,
            "rejected_paths": sorted(violations),
            "patch": patch_path.relative_to(self.config.output_dir).as_posix(),
            "patch_sha256": patch_sha,
            "started_at": started_at.isoformat(),
            "duration": duration,
            "cost": cost,
            "tokens": tokens,
            "iterations": iterations,
            "max_iterations": self.config.manager_max_iterations,
            "execution_error": execution_error,
            "termination_reason": termination_reason,
            "accepted": False,
            "manager_checkpoint_id": None,
        }

        fatal_execution_error = bool(execution_error) and termination_reason not in {
            "iteration_limit",
            "agent_finish",
            "completed_without_finish",
        }
        if fatal_execution_error:
            record["status"] = "execution_error"
            self._log_intervention_result(record)
            return record
        if violations:
            record["status"] = "scope_rejected"
            self._log_intervention_result(record)
            return record
        if not changed:
            record["status"] = "no_change"
            self._log_intervention_result(record)
            return record

        validation = self._validate_candidate_patch(
            sequence=sequence,
            event=event,
            changed=changed,
            head_before=head_before,
            patch_sha=patch_sha,
            termination_reason=termination_reason,
        )
        record["candidate_validation"] = validation
        if not validation["passed"]:
            record["status"] = "validation_rejected"
            self._log_intervention_result(record)
            return record

        commit_message = "Async-Manager online intervention " + str(sequence)
        self._command(
            f"git -C {shlex.quote(self.manager_worktree)} "
            "-c user.name=AsynCodeBench "
            "-c user.email=benchmark@localhost "
            f"commit -m {shlex.quote(commit_message)}",
            timeout=120,
        )
        commit = self._command(
            f"git -C {shlex.quote(self.manager_worktree)} rev-parse HEAD",
            timeout=30,
        ).strip()
        if self.current_head() != head_before or self.main_workspace_status():
            raise RuntimeError(
                "Integrated workspace moved before manager patch integration"
            )
        merge_command = (
            f"git -C {shlex.quote(self.repo_dir)} merge --ff-only {shlex.quote(commit)}"
        )
        self._command(merge_command, timeout=120)
        if self.current_head() != commit or self.main_workspace_status():
            raise RuntimeError("Manager patch integration could not be verified")
        record.update(
            status="accepted",
            accepted=True,
            manager_commit=commit,
            head_after=commit,
        )
        record["triggering_specialist_refresh"] = self._refresh_triggering_specialist(
            event, commit, sequence
        )
        self.accepted_interventions += 1
        self._log_intervention_result(record)
        return record

    def finalize_intervention_record(
        self, record: dict, manager_checkpoint: dict | None
    ) -> None:
        if manager_checkpoint:
            record["manager_checkpoint_id"] = manager_checkpoint.get("checkpoint_id")
            record["manager_checkpoint_step"] = manager_checkpoint.get("logical_step")
        record["completed_at"] = datetime.now(timezone.utc).isoformat()
        path = Path(self.config.output_dir) / "manager_interventions.jsonl"
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
        self.intervention_records.append(record)
        if self.output_logger:
            self.output_logger.log_event(
                event_type="async_manager_intervention",
                source="manager",
                content=record,
            )

    def final_review_all(self, subagent_results, max_iterations=30):
        # The last specialist integration already triggered the final online
        # intervention opportunity.  Final review is deliberately read-only.
        head = self.current_head()
        self._sync_manager_worktree(head)
        self._set_mode("observe")
        original_repo_dir = self.repo_dir
        try:
            self.repo_dir = self.manager_worktree
            return super().final_review_all(
                subagent_results, max_iterations=max_iterations
            )
        finally:
            self.repo_dir = original_repo_dir

    def prepare_final_evaluation(self):
        super().prepare_final_evaluation()
        cost_path = Path(self.config.output_dir) / "cost.json"
        data = json.loads(cost_path.read_text(encoding="utf-8"))
        current = extract_conversation_metrics(self.conversation)
        aggregate = {
            field: self.recovered_conversation_metrics[field] + current.get(field, 0)
            for field in self.recovered_conversation_metrics
        }
        manager = data.setdefault("manager", {})
        previous = {field: manager.get(field, 0) for field in aggregate}
        manager.update(aggregate)
        total = data.setdefault("total", {})
        for field in aggregate:
            total[field] = total.get(field, 0) + aggregate[field] - previous[field]
        data.setdefault("manager", {}).setdefault("operations", {})[
            "online_intervention"
        ] = {
            "policy": POLICY,
            "events": self.intervention_sequence,
            "accepted": self.accepted_interventions,
            "cost": self.intervention_cost,
            "tokens": self.intervention_tokens,
            "duration": self.intervention_duration,
            "conversation_segments": self.manager_conversation_segments,
        }
        data["manager"]["accounting_policy"] = (
            "sum_all_recovered_and_current_manager_conversation_segments"
        )
        dump(cost_path, data)

    def cleanup(self):
        try:
            super().cleanup()
        finally:
            if self.manager_worktree:
                self.workspace.execute_command(
                    f"git -C {shlex.quote(self.repo_dir)} worktree remove --force "
                    f"{shlex.quote(self.manager_worktree)}",
                    timeout=120,
                )
            if self.manager_mode_file:
                self.workspace.execute_command(
                    f"rm -f -- {shlex.quote(self.manager_mode_file)}", timeout=30
                )
            if OnlineManager.active_instance is self:
                OnlineManager.active_instance = None
