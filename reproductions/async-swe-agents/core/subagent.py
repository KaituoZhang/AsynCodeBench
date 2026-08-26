import asyncio
import os
import time
from datetime import datetime
from types import MethodType

import httpx
from config import SubAgent, SubAgentResult
from openhands.sdk import Agent, Conversation, LLMSummarizingCondenser
from openhands.tools.preset.default import get_default_tools

from core.dependency_probes import write_dependency_probe_checkpoint
from core.utils import (
    PanelVisualizer,
    build_subagent_prompt,
    count_llm_iterations,
    extract_conversation_metrics,
    serialize_event,
)


def task_metrics_manifest_path(task_module):
    """Return a task's explicit metrics manifest instead of guessing by repo name."""
    manifest_paths = getattr(task_module, "manifest_paths", {})
    if isinstance(manifest_paths, dict):
        return manifest_paths.get("metrics")
    return None


def _is_ambiguous_run_trigger_timeout(error):
    """Return whether the remote /run trigger may have reached the server."""
    message = str(error).strip().lower()
    return (
        "conversation run failed for id=" in message
        and message.endswith(": timed out")
    )


def conversation_run_timeout():
    return float(
        os.getenv("ASYNCODEBENCH_CONVERSATION_RUN_TIMEOUT", "3600")
    )


def remote_poll_timeout():
    return float(os.getenv("ASYNCODEBENCH_REMOTE_POLL_TIMEOUT", "900"))


def remote_trigger_timeout():
    return float(os.getenv("ASYNCODEBENCH_REMOTE_TRIGGER_TIMEOUT", "30"))


def remote_message_timeout():
    return float(os.getenv("ASYNCODEBENCH_REMOTE_MESSAGE_TIMEOUT", "900"))


def remote_poll_interval():
    return float(os.getenv("ASYNCODEBENCH_REMOTE_POLL_INTERVAL", "5"))


def remote_start_grace_seconds():
    return float(os.getenv("ASYNCODEBENCH_REMOTE_START_GRACE_SECONDS", "30"))


def remote_terminal_confirm_seconds():
    return float(
        os.getenv("ASYNCODEBENCH_REMOTE_TERMINAL_CONFIRM_SECONDS", "30")
    )


def condenser_max_tokens(llm):
    """Return the token threshold used to condense agent history."""
    configured = os.getenv("ASYNCODEBENCH_CONDENSER_MAX_TOKENS")
    if configured:
        value = int(configured)
        if value <= 0:
            raise ValueError(
                "ASYNCODEBENCH_CONDENSER_MAX_TOKENS must be positive"
            )
        return value

    context_window = getattr(llm, "max_input_tokens", None)
    output_budget = getattr(llm, "max_output_tokens", None) or 0
    if context_window:
        available = int(context_window) - int(output_budget)
        fallback = int(context_window) * 3 // 4
        # Condense before reaching the provider's exact input/output boundary.
        # Token counting can differ slightly across the SDK and model server.
        safe_available = available * 9 // 10
        return max(16384, safe_available if safe_available > 0 else fallback)
    return None


def configure_remote_message_timeout(conversation, log):
    """Give remote message submission time to wait for the server state lock."""
    if getattr(conversation, "_asyncodebench_message_timeout_configured", False):
        return True

    client = getattr(conversation, "_client", None)
    if client is None:
        return False

    timeout = remote_message_timeout()
    if timeout <= 0:
        raise ValueError("ASYNCODEBENCH_REMOTE_MESSAGE_TIMEOUT must be positive")

    client.timeout = httpx.Timeout(timeout)
    conversation._asyncodebench_message_timeout_configured = True
    log(f"Configured remote message request timeout: {timeout}s")
    return True


def send_conversation_message(conversation, message, log):
    """Submit a user message with the AsynCodeBench remote timeout policy."""
    configure_remote_message_timeout(conversation, log)
    conversation.send_message(message)


def configure_remote_status_polling(conversation, log):
    """Replace the SDK's fixed 30-second REST status timeout.

    The host runner and Docker agent server are built from the same locked
    OpenHands source revision. On long local-model tool turns, the status
    endpoint can still block behind conversation state for longer than 30
    seconds even though the run is healthy. Keep the SDK polling flow, but use
    a timeout suitable for long local-model turns.
    """
    if getattr(conversation, "_asyncodebench_polling_configured", False):
        return True

    client = getattr(conversation, "_client", None)
    poll_status = getattr(conversation, "_poll_status_once", None)
    conversation_id = getattr(conversation, "_id", None)
    if client is None or not callable(poll_status) or conversation_id is None:
        return False

    timeout = remote_poll_timeout()
    if timeout <= 0:
        raise ValueError("ASYNCODEBENCH_REMOTE_POLL_TIMEOUT must be positive")
    base_path = str(
        getattr(conversation, "_conversation_info_base_path", "/api/conversations")
    ).rstrip("/")

    def poll_status_once(self):
        response = self._client.get(
            f"{base_path}/{self._id}",
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json().get("execution_status")

    conversation._poll_status_once = MethodType(poll_status_once, conversation)
    conversation._asyncodebench_polling_configured = True
    log(f"Configured remote status polling: interval={remote_poll_interval()}s, "
        f"request_timeout={timeout}s")
    return True


def trigger_remote_run(conversation):
    """Trigger a remote run without the legacy SDK's noisy timeout wrapper."""
    timeout = remote_trigger_timeout()
    if timeout <= 0:
        raise ValueError("ASYNCODEBENCH_REMOTE_TRIGGER_TIMEOUT must be positive")
    base_path = str(
        getattr(conversation, "_conversation_info_base_path", "/api/conversations")
    ).rstrip("/")
    response = conversation._client.post(
        f"{base_path}/{conversation._id}/run",
        timeout=timeout,
    )
    if response.status_code not in {200, 201, 204, 409}:
        response.raise_for_status()


def _is_request_timeout(error):
    name = error.__class__.__name__.lower()
    message = str(error).strip().lower()
    return "timeout" in name or "timed out" in message


def _normalized_remote_status(status):
    value = getattr(status, "value", status)
    return str(value or "").strip().lower()


def _handle_remote_terminal_status(conversation, status):
    handler = getattr(conversation, "_handle_conversation_status", None)
    if callable(handler):
        handler(status)
        return
    normalized = _normalized_remote_status(status)
    if normalized == "error":
        raise RuntimeError("Remote conversation ended with error")
    if normalized == "stuck":
        raise RuntimeError("Remote conversation got stuck")


def _handle_remote_poll_exception(conversation, error):
    handler = getattr(conversation, "_handle_poll_exception", None)
    if callable(handler):
        handler(error)
        return
    raise error


def wait_for_remote_run_completion(conversation, log, timeout, poll_interval):
    """Wait for a remote run with explicit terminal-state confirmation.

    The agent server can briefly expose IDLE before a run starts and FINISHED
    before its stop hooks and final event flush complete. Confirm REST terminal
    state for a short interval and only retry a trigger after a bounded IDLE
    grace period.
    """
    if timeout <= 0:
        raise ValueError("ASYNCODEBENCH_CONVERSATION_RUN_TIMEOUT must be positive")
    if poll_interval <= 0:
        raise ValueError("ASYNCODEBENCH_REMOTE_POLL_INTERVAL must be positive")

    start_grace = remote_start_grace_seconds()
    terminal_confirm = remote_terminal_confirm_seconds()
    if start_grace < 0:
        raise ValueError(
            "ASYNCODEBENCH_REMOTE_START_GRACE_SECONDS must be nonnegative"
        )
    if terminal_confirm < 0:
        raise ValueError(
            "ASYNCODEBENCH_REMOTE_TERMINAL_CONFIRM_SECONDS must be nonnegative"
        )

    poll_status = getattr(conversation, "_poll_status_once", None)
    if not callable(poll_status):
        raise RuntimeError("Remote conversation does not expose status polling")

    started_at = time.monotonic()
    observed_running = False
    terminal_status = None
    terminal_first_seen_at = None

    while True:
        now = time.monotonic()
        elapsed = now - started_at
        if elapsed > timeout:
            raise RuntimeError(
                f"Run timed out after {timeout} seconds. "
                "The conversation may still be running on the server."
            )

        try:
            status = poll_status()
        except Exception as error:
            _handle_remote_poll_exception(conversation, error)
            terminal_status = None
            terminal_first_seen_at = None
        else:
            normalized = _normalized_remote_status(status)
            if normalized == "running":
                observed_running = True
                terminal_status = None
                terminal_first_seen_at = None
            elif normalized in {"error", "stuck"}:
                _handle_remote_terminal_status(conversation, normalized)
            elif normalized == "finished":
                if terminal_status != normalized:
                    terminal_status = normalized
                    terminal_first_seen_at = now
                if now - terminal_first_seen_at >= terminal_confirm:
                    reconcile_conversation_events(conversation, log)
                    return normalized
            elif normalized == "idle" and not observed_running:
                if elapsed >= start_grace:
                    return normalized
            elif normalized in {"paused", "waiting_for_confirmation"}:
                raise RuntimeError(
                    f"Remote conversation stopped in unexpected state: {normalized}"
                )
            else:
                terminal_status = None
                terminal_first_seen_at = None

        time.sleep(poll_interval)


def run_conversation_with_trigger_recovery(conversation, log):
    """Trigger and monitor a remote run with legacy-client compatibility."""
    timeout = conversation_run_timeout()
    poll_interval = remote_poll_interval()
    if poll_interval <= 0:
        raise ValueError("ASYNCODEBENCH_REMOTE_POLL_INTERVAL must be positive")
    configured_remote = configure_remote_status_polling(conversation, log)
    poll_status = getattr(conversation, "_poll_status_once", None)

    if configured_remote and callable(poll_status):
        for attempt in range(2):
            try:
                trigger_remote_run(conversation)
            except Exception as error:
                if not _is_request_timeout(error):
                    raise
                log(
                    "Remote /run acknowledgement is delayed; tracking the "
                    "accepted conversation without submitting duplicate work"
                )

            normalized_status = wait_for_remote_run_completion(
                conversation,
                log,
                timeout=timeout,
                poll_interval=poll_interval,
            )
            if normalized_status == "finished":
                return
            if attempt == 0:
                log(
                    "Conversation remained IDLE through the start grace period; "
                    "retrying the /run trigger once"
                )

        raise RuntimeError(
            "Remote conversation remained IDLE after two run triggers"
        )

    try:
        conversation.run(poll_interval=poll_interval, timeout=timeout)
        return
    except Exception as error:
        if not _is_ambiguous_run_trigger_timeout(error):
            raise

    wait_for_completion = getattr(conversation, "_wait_for_run_completion", None)
    if not callable(wait_for_completion) or not callable(poll_status):
        raise RuntimeError(
            "Remote conversation trigger timed out and this SDK cannot recover "
            "the accepted run"
        )

    log(
        "Remote /run trigger timed out after 30s; polling the same "
        "conversation because the server may already be running it"
    )
    wait_for_completion(poll_interval=poll_interval, timeout=timeout)

    # A request that never reached the server remains IDLE. Retry only the
    # trigger in that case; the original user message is already persisted.
    status = poll_status()
    status_value = getattr(status, "value", status)
    if str(status_value).lower() == "idle":
        log("Conversation remained IDLE; retrying the /run trigger once")
        conversation.run(poll_interval=poll_interval, timeout=timeout)


def reconcile_conversation_events(conversation, log):
    """Fetch events missed by the remote client's WebSocket cache."""
    events = getattr(getattr(conversation, "state", None), "events", None)
    if events is None:
        return 0
    reconcile = getattr(events, "reconcile", None)
    if not callable(reconcile):
        return 0
    try:
        added = reconcile()
    except Exception as error:
        log(f"Warning: failed to reconcile remote events: {error}")
        return 0
    if added:
        log(f"Reconciled {added} remote event(s) before metric extraction")
    return added


def latest_conversation_error(events):
    """Return the latest structured remote conversation error, if present."""
    for event in reversed(list(events)):
        if event.__class__.__name__ != "ConversationErrorEvent":
            continue
        code = str(getattr(event, "code", "") or "").strip()
        detail = str(getattr(event, "detail", "") or "").strip()
        if code and detail:
            return f"{code}: {detail}"
        return detail or code or None
    return None


def classify_conversation_termination(
    conversation,
    *,
    error=None,
    iterations=0,
    max_iterations=0,
    events=None,
):
    """Return a stable stop reason and whether the iteration cap was hit."""
    event_list = list(
        events
        if events is not None
        else getattr(getattr(conversation, "state", None), "events", [])
    )
    structured_error = (latest_conversation_error(event_list) or "").lower()
    error_text = f"{error or ''} {structured_error}".lower()
    status = _normalized_remote_status(
        getattr(getattr(conversation, "state", None), "execution_status", "")
    )

    if "maxiterationsreached" in error_text or "maximum iterations" in error_text:
        return "iteration_limit", True
    if "contextwindow" in error_text or "context window" in error_text:
        return "context_window_error", False
    if "stuck" in error_text or status == "stuck":
        return "stuck_detected", False
    if "timed out" in error_text or "timeout" in error_text:
        return "wall_clock_timeout", False
    if any(
        marker in error_text
        for marker in (
            "connection error",
            "serviceunavailable",
            "rate_limit",
            "ratelimit",
            "provider",
            "transport",
        )
    ):
        return "provider_or_transport_error", False
    if status == "finished":
        return "agent_finish", False
    if max_iterations and iterations >= max_iterations:
        return "iteration_limit", True
    if error_text.strip():
        return "execution_error", False
    return "completed_without_finish", False


_UNUSABLE_CONVERSATION_ERROR_MARKERS = (
    "got stuck",
    "maxiterationsreached",
    "remote conversation ended with error",
    "run timed out",
    "conversationrunerror",
)


def conversation_error_requires_fresh(error):
    """Return whether a remote conversation cannot safely be reused."""
    message = str(error or "").strip().lower()
    return bool(message) and (
        "timed out" in message
        or any(
            marker in message
            for marker in _UNUSABLE_CONVERSATION_ERROR_MARKERS
        )
    )


def result_requires_fresh_conversation(result):
    """Return whether a terminal remote state cannot accept another CAID round."""
    return conversation_error_requires_fresh(
        getattr(result, "error", "") if result is not None else ""
    )


class SubAgentRunner:
    def __init__(
        self,
        llm,
        workspace,
        subagent,
        prompts,
        task_module,
        max_iterations=50,
        max_rounds_chat=2,
        output_dir=None,
        output_logger=None,
    ):
        self.llm = llm
        self.workspace = workspace
        self.subagent = subagent
        self.prompts = prompts
        self.task_module = task_module
        self.max_iterations = max_iterations
        self.max_rounds_chat = max_rounds_chat
        self.output_dir = output_dir
        self.output_logger = output_logger
        self.agent = None
        self.conversation = None
        self.result = None
        self.instruction_time = None
        self.completed_rounds = 0
        self.last_result = None
        self.last_saved_event_count = 0
        self.conversation_round = None

    def log(self, message):
        print(f"[{self.subagent.engineer_id}] {message}")

    def can_accept_more_tasks(self):
        return self.completed_rounds < self.max_rounds_chat

    def update_task(self, new_subagent):
        self.log(f"Updating task for round {new_subagent.current_round}")
        self.log(f"  - New task: {new_subagent.task_id}")
        if new_subagent.file_path:
            self.log(f"  - New file: {new_subagent.file_path}")
        self.subagent = new_subagent
        self.result = None
        self.instruction_time = datetime.now()
        self.ensure_usable_conversation_for_round()

    def ensure_usable_conversation_for_round(self):
        """Replace terminal remote state once before a later CAID round."""
        current_round = self.subagent.current_round
        if (
            result_requires_fresh_conversation(self.last_result)
            and self.conversation_round != current_round
        ):
            self.log(
                "Previous conversation is terminal; starting a fresh "
                "conversation for this CAID round"
            )
            self.setup()

    def setup(self):
        self.log("Setting up subagent...")
        tools = get_default_tools(enable_browser=False)
        condenser_llm = self.llm.model_copy(update={"usage_id": "condenser"})
        condenser = LLMSummarizingCondenser(
            llm=condenser_llm,
            max_size=80,
            max_tokens=condenser_max_tokens(self.llm),
            keep_first=4,
        )
        self.agent = Agent(
            llm=self.llm,
            tools=tools,
            system_prompt_kwargs={"cli_mode": True},
            condenser=condenser,
        )
        self.conversation = Conversation(
            agent=self.agent,
            workspace=self.workspace,
            max_iteration_per_run=self.max_iterations,
            visualizer=PanelVisualizer(),
        )
        self.instruction_time = datetime.now()
        self.last_saved_event_count = 0
        self.conversation_round = self.subagent.current_round
        self.log("Subagent ready")

    def clone_for_subagent(self, subagent):
        """Create another runner with the same implementation and settings."""

        runner = type(self)(
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

    def create_result(self):
        if self.result is None:
            self.result = self.task_module.create_subagent_result(self.subagent)
        return self.result

    def build_first_round_prompt(self):
        return build_subagent_prompt(
            prompts=self.prompts,
            submission_path=self.subagent.worktree_path or self.subagent.submission_path,
            task_node_id=self.subagent.task_node_id,
            requirements=self.subagent.requirements,
            instruction=self.subagent.instruction,
            engineer_id=self.subagent.engineer_id,
            # commit0-specific fields (ignored by paperbench prompt via **kwargs)
            worktree_path=self.subagent.worktree_path or self.subagent.submission_path,
            file_path=self.subagent.file_path,
            functions=self.subagent.functions_to_implement,
            test_cmd=getattr(self.subagent, 'test_cmd', 'pytest'),
            test_dir=getattr(self.subagent, 'test_dir', 'tests/'),
        )

    def build_followup_prompt(self):
        template = self.prompts.get("followup_prompt", "")
        args = self.task_module.get_followup_prompt_args(self.subagent)
        prompt = template.format(**args)
        self.log(f"Round {self.subagent.current_round}: Sending follow-up instruction")
        return prompt

    def run(self):
        self.ensure_usable_conversation_for_round()
        result = self.create_result()
        start_time = datetime.now()
        result.start_time = start_time.isoformat()

        self.log("Starting implementation...")
        self.log(f"  - Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        for line in self.task_module.get_run_start_log_lines(self.subagent):
            self.log(line)

        cost_before = 0.0
        prompt_tokens_before = 0
        completion_tokens_before = 0
        iteration_before = 0

        run_error = None
        try:
            if self.subagent.current_round == 1:
                prompt = self.build_first_round_prompt()
            else:
                prompt = self.build_followup_prompt()

            max_retries = 3
            iteration_before = count_llm_iterations(self.conversation.state.events)

            metrics_before = extract_conversation_metrics(self.conversation)
            cost_before = metrics_before["cost"]
            prompt_tokens_before = metrics_before["prompt_tokens"]
            completion_tokens_before = metrics_before["completion_tokens"]

            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        if self.task_module.should_setup_on_retry:
                            self.log(f"Retry attempt {attempt + 1}/{max_retries}...")
                            self.setup()
                        else:
                            self.log(f"Retry attempt {attempt + 1}/{max_retries}, resuming conversation...")

                    if self.task_module.should_resend_on_retry or attempt == 0:
                        send_conversation_message(
                            self.conversation,
                            prompt,
                            self.log,
                        )
                    run_conversation_with_trigger_recovery(
                        self.conversation,
                        self.log,
                    )
                    break

                except Exception as llm_error:
                    error_str = str(llm_error)
                    retryable_errors = [
                        "invalid_encrypted_content",
                        "500 Internal Server Error",
                        "BadRequestError",
                        "rate_limit",
                    ]
                    if any(msg in error_str for msg in retryable_errors):
                        self.log(f"Transient LLM error: {error_str[:150]}")
                        if attempt < max_retries - 1:
                            import time
                            time.sleep(2 ** attempt)
                            continue
                    raise

            commit_info = self.get_commit_info()
            current_hash = commit_info.get("hash", "")
            base_commit = self.subagent.base_commit or ""
            base_short = base_commit[:8] if base_commit else ""

            if current_hash and base_short and current_hash == base_short:
                result.success = False
                result.error = "No new commit was made. Agent may have run out of iterations before committing."
                result.commit_hash = ""
                self.task_module.populate_no_commit_result(result)
                result.files_modified = []
                self.log(f"WARNING: No new commit detected (HEAD={current_hash} same as base)")
            else:
                self.task_module.populate_success_result(result, self, commit_info)
                self.print_summary(result, commit_info)

        except Exception as e:
            run_error = e
            result.success = False
            result.error = str(e)
            self.log(f"ERROR: {e}")

        if self.conversation:
            reconcile_conversation_events(self.conversation, self.log)
            if result.error and result.error.endswith(
                ": Remote conversation ended with error"
            ):
                structured_error = latest_conversation_error(
                    self.conversation.state.events
                )
                if structured_error:
                    result.error = structured_error
                    self.log(f"Remote error detail: {structured_error}")

        end_time = datetime.now()
        result.end_time = end_time.isoformat()
        duration = (end_time - start_time).total_seconds()
        result.duration_seconds = duration

        if self.conversation:
            metrics_after = extract_conversation_metrics(self.conversation)
            result.cost = metrics_after["cost"] - cost_before
            result.prompt_tokens = metrics_after["prompt_tokens"] - prompt_tokens_before
            result.completion_tokens = metrics_after["completion_tokens"] - completion_tokens_before
            result.total_tokens = result.prompt_tokens + result.completion_tokens
            result.actual_iterations = count_llm_iterations(self.conversation.state.events) - iteration_before
            result.max_iterations = self.max_iterations
            (
                result.termination_reason,
                result.iteration_cap_hit,
            ) = classify_conversation_termination(
                self.conversation,
                error=run_error or result.error,
                iterations=result.actual_iterations,
                max_iterations=result.max_iterations,
            )

            if self.output_logger:
                events = list(self.conversation.state.events)
                engineer_id = self.subagent.engineer_id
                new_events_start = self.last_saved_event_count
                new_events_count = len(events) - new_events_start
                self.log(f"Saving {new_events_count} new events (starting from {new_events_start}) to {engineer_id}_events.jsonl...")
                for idx in range(new_events_start, len(events)):
                    event = events[idx]
                    serialized = serialize_event(event, idx)
                    serialized["engineer_id"] = engineer_id
                    serialized["task_id"] = self.subagent.task_id
                    serialized["round_num"] = self.subagent.current_round
                    serialized.update(self.task_module.get_event_serialization_extras(self.subagent))
                    serialized["start_time"] = serialized.get("timestamp")
                    if idx + 1 < len(events):
                        next_ts = getattr(events[idx + 1], 'timestamp', None)
                        serialized["end_time"] = next_ts
                    else:
                        serialized["end_time"] = result.end_time
                    self.output_logger.log_agent_event(engineer_id, serialized)
                self.last_saved_event_count = len(events)

        self.completed_rounds += 1
        self.last_result = result

        self.log("Completed")
        self.log(f"  - Round: {self.subagent.current_round}/{self.max_rounds_chat}")
        self.log(f"  - End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.log(f"  - Duration: {duration:.1f}s")
        self.log(f"  - Iterations: {result.actual_iterations}/{result.max_iterations}")
        self.log(
            "  - Termination: "
            f"{result.termination_reason} (cap_hit={result.iteration_cap_hit})"
        )
        self.log(f"  - Cost: ${result.cost:.4f} ({result.total_tokens} tokens)")
        self.log(f"  - Can accept more tasks: {self.can_accept_more_tasks()}")

        return result

    async def run_async(self):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.run)

    def get_commit_info(self):
        worktree_path = self.subagent.worktree_path or self.subagent.submission_path
        if not worktree_path:
            return {"hash": "", "message": "", "author": ""}

        cmd = (
            f"cd {worktree_path} && "
            f"git log -1 --format='%H|%s|%an' 2>/dev/null || echo '||'"
        )
        result = self.workspace.execute_command(cmd, timeout=30)
        stdout = (result.stdout or "").strip()
        parts = stdout.split("|", 2)
        return {
            "hash": parts[0][:8] if len(parts) > 0 else "",
            "message": parts[1] if len(parts) > 1 else "",
            "author": parts[2] if len(parts) > 2 else "",
        }

    def get_git_diff(self):
        worktree_path = self.subagent.worktree_path or self.subagent.submission_path
        base_commit = self.subagent.base_commit

        if not worktree_path:
            return ""

        if base_commit:
            cmd = f"cd {worktree_path} && git diff {base_commit}..HEAD --no-color"
            result = self.workspace.execute_command(cmd, timeout=120)
            if result.exit_code == 0 and result.stdout.strip():
                return result.stdout.strip()

        cmd = (
            f"cd {worktree_path} && "
            f"git diff HEAD~1 HEAD --no-color 2>/dev/null || "
            f"git diff --cached --no-color"
        )
        result = self.workspace.execute_command(cmd, timeout=120)
        return result.stdout.strip() if result.exit_code == 0 else ""

    def get_modified_files(self):
        worktree_path = self.subagent.worktree_path or self.subagent.submission_path
        base_commit = self.subagent.base_commit

        if not worktree_path:
            return []

        if base_commit:
            cmd = (
                f"cd {worktree_path} && "
                f"git diff --name-only {base_commit}..HEAD 2>/dev/null || echo ''"
            )
        else:
            cmd = (
                f"cd {worktree_path} && "
                f"git diff --name-only HEAD~1 HEAD 2>/dev/null || echo ''"
            )

        result = self.workspace.execute_command(cmd, timeout=30)

        if result.exit_code == 0 and result.stdout.strip():
            return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
        return []

    def get_commit_count(self):
        """Count commits since base (paperbench-specific)."""
        worktree_path = self.subagent.worktree_path or self.subagent.submission_path
        base_commit = self.subagent.base_commit

        if not worktree_path:
            return 0

        if base_commit:
            cmd = f"cd {worktree_path} && git rev-list --count {base_commit}..HEAD 2>/dev/null || echo '0'"
        else:
            cmd = f"cd {worktree_path} && git rev-list --count HEAD 2>/dev/null || echo '0'"

        result = self.workspace.execute_command(cmd, timeout=30)
        try:
            return int(result.stdout.strip())
        except ValueError:
            return 0

    def check_submission_exists(self):
        """Check if submission directory has content (paperbench-specific)."""
        worktree_path = self.subagent.worktree_path or self.subagent.submission_path
        if not worktree_path:
            return False
        cmd = f"test -d {worktree_path} && ls {worktree_path} | head -1"
        result = self.workspace.execute_command(cmd, timeout=30)
        return result.exit_code == 0 and result.stdout.strip() != ""

    def check_reproduce_script_exists(self):
        """Check if reproduce.sh exists (paperbench-specific)."""
        worktree_path = self.subagent.worktree_path or self.subagent.submission_path
        if not worktree_path:
            return False
        cmd = f"test -f {worktree_path}/reproduce.sh && echo 'exists'"
        result = self.workspace.execute_command(cmd, timeout=30)
        return "exists" in result.stdout

    def print_summary(self, result, commit_info):
        self.log("=" * 60)
        self.log("Commit Summary")
        self.log("=" * 60)
        self.log(f"  Status: {'SUCCESS' if result.success else 'FAILED'}")
        self.log(f"  Branch: {self.subagent.branch_name}")

        if commit_info.get("hash"):
            self.log(f"  Commit: {commit_info['hash']}")
            self.log(f"  Message: {commit_info['message']}")

        for line in self.task_module.get_print_summary_lines(result, commit_info):
            self.log(line)

        self.log("=" * 60)

    def cleanup(self):
        if self.conversation:
            try:
                self.conversation.close()
            except Exception:
                pass


async def run_subagents_parallel(runners, manager=None, task_module=None, output_logger=None, enable_background_exploration=True, max_subagents=4):
    if not runners:
        print("[SubAgents] No subagents to run.")
        return []

    print(f"\n[SubAgents] Running {len(runners)} subagents in parallel...")
    for runner in runners:
        print(f"- {runner.subagent.engineer_id}: max_rounds={runner.max_rounds_chat}")

    # Track which agents have been onboarded and which have finished
    all_possible_agents = [f"engineer_{i+1}" for i in range(max_subagents)]
    active_engineer_ids = set(r.subagent.engineer_id for r in runners)
    finished_engineer_ids = set()

    async def run_single_runner(runner):
        engineer_id = runner.subagent.engineer_id
        round_num = runner.subagent.current_round
        print(f"\n[SubAgents] Starting {engineer_id} (round {round_num})...")
        try:
            result = await runner.run_async()
            return result
        except Exception as e:
            print(f"[SubAgents] ERROR running {engineer_id}: {e}")
            result = runner.create_result()
            result.success = False
            result.error = str(e)
            result.end_time = datetime.now().isoformat()
            return result

    tasks = {
        asyncio.create_task(run_single_runner(runner)): runner
        for runner in runners
    }

    results = []
    idle_runners = []
    exploration_task = None
    probe_logical_step = 0

    def next_probe_step():
        nonlocal probe_logical_step
        probe_logical_step += 1
        return probe_logical_step

    def is_commit0_probe_enabled():
        return (
            task_module is not None
            and hasattr(task_module, "config")
            and hasattr(task_module.config, "repo_name")
            and runners
            and getattr(runners[0], "output_dir", None)
        )

    def read_head(workspace, path):
        result = workspace.execute_command(
            f"cd {path} && git rev-parse --short HEAD",
            timeout=30,
        )
        return result.stdout.strip() if result.exit_code == 0 else None

    def write_probe(workspace, output_dir, repo_name, workspace_path, **kwargs):
        return write_dependency_probe_checkpoint(
            workspace=workspace,
            output_dir=output_dir,
            repo_name=repo_name,
            workspace_path=workspace_path,
            logical_step=next_probe_step(),
            metrics_path=task_metrics_manifest_path(task_module),
            **kwargs,
        )

    # Background exploration helpers (commit0-specific)
    def get_remaining_tasks():
        if manager and manager.delegation_plan:
            return manager.delegation_plan.remaining_tasks or []
        return []

    def get_running_agents_summary():
        running_info = []
        for task, runner in tasks.items():
            engineer_id = runner.subagent.engineer_id
            file_path = runner.subagent.file_path
            funcs = runner.subagent.functions_to_implement[:3]
            funcs_str = ", ".join(funcs) + ("..." if len(runner.subagent.functions_to_implement) > 3 else "")
            running_info.append(f"- {engineer_id}: {file_path} ({funcs_str})")
        return "\n".join(running_info) if running_info else "No engineers running"

    async def start_exploration_if_needed():
        nonlocal exploration_task
        if not enable_background_exploration or not manager:
            return None

        remaining = get_remaining_tasks()
        if not remaining:
            print("[Manager] No remaining tasks to explore")
            return None

        running_summary = get_running_agents_summary()
        manager.reset_exploration_cancel()
        print(f"[Manager] Starting background exploration for {len(remaining)} remaining tasks...")
        exploration_task = asyncio.create_task(
            manager.explore_background_async(remaining, running_summary)
        )
        return exploration_task

    if enable_background_exploration and manager and get_remaining_tasks():
        await start_exploration_if_needed()

    while tasks or idle_runners:
        if not tasks and idle_runners:
            print(f"\n[SubAgents] No active tasks, checking {len(idle_runners)} idle runners...")

            trigger_runner = idle_runners[0]
            running_agents = []
            idle_engineer_ids = [r.subagent.engineer_id for r in idle_runners]
            inactive_engineer_ids = [aid for aid in all_possible_agents if aid not in active_engineer_ids]

            assignment = manager.assign_task(
                completed_result=trigger_runner.last_result,
                all_completed=results,
                running_agents=running_agents,
                idle_agents=idle_engineer_ids,
                inactive_agents=inactive_engineer_ids,
                finished_agents=list(finished_engineer_ids),
            )

            idle_runners_by_id = {r.subagent.engineer_id: r for r in idle_runners}

            activated_any = False
            for new_subagent in assignment.get("assignments", []):
                target_engineer_id = new_subagent.engineer_id
                if target_engineer_id in idle_runners_by_id:
                    target_runner = idle_runners_by_id.pop(target_engineer_id)
                    new_subagent.current_round = target_runner.completed_rounds + 1

                    task_module.prepare_reuse_subagent(new_subagent, target_runner)

                    print(f"\n[SubAgents] Activating idle {target_engineer_id} with new task (round {new_subagent.current_round})")
                    print(f"- New task: {new_subagent.task_id}")
                    for line in task_module.get_new_task_print_lines(new_subagent):
                        print(line)

                    target_runner.update_task(new_subagent)

                    new_task = asyncio.create_task(run_single_runner(target_runner))
                    tasks[new_task] = target_runner
                    activated_any = True

                elif target_engineer_id in inactive_engineer_ids:
                    print(f"\n[SubAgents] Onboarding inactive engineer {target_engineer_id}...")

                    cmd_result = manager.workspace.execute_command(
                        f"cd {manager.repo_dir} && git rev-parse HEAD", timeout=30
                    )
                    base_commit = cmd_result.stdout.strip() if cmd_result.exit_code == 0 else ""

                    branch_name, worktree_name = task_module.get_onboard_names(target_engineer_id)
                    worktree_path = f"/workspace/{worktree_name}"

                    branch_cmd = (
                        f"cd {manager.repo_dir} && "
                        f"git branch {branch_name} {base_commit} 2>/dev/null || true"
                    )
                    manager.workspace.execute_command(branch_cmd, timeout=30)

                    worktree_cmd = (
                        f"cd {manager.repo_dir} && "
                        f"git worktree add {worktree_path} {branch_name}"
                    )
                    worktree_result = manager.workspace.execute_command(worktree_cmd, timeout=60)

                    if worktree_result.exit_code != 0:
                        print(f"[SubAgents] Failed to create worktree for {target_engineer_id}: {worktree_result.stderr}")
                        continue

                    new_subagent.branch_name = branch_name
                    new_subagent.worktree_path = worktree_path
                    new_subagent.base_commit = base_commit
                    task_module.post_onboard_subagent(new_subagent, manager.repo_dir)
                    new_subagent.current_round = 1

                    template_runner = trigger_runner
                    new_runner = template_runner.clone_for_subagent(new_subagent)

                    print(f"- Worktree: {worktree_path}")
                    print(f"- Branch: {branch_name}")
                    print(f"- Task: {new_subagent.task_id}")
                    for line in task_module.get_new_task_print_lines(new_subagent):
                        print(line)

                    new_task = asyncio.create_task(run_single_runner(new_runner))
                    tasks[new_task] = new_runner
                    active_engineer_ids.add(target_engineer_id)
                    activated_any = True
                    print(f"[SubAgents] {target_engineer_id} onboarded and added to task pool")

            idle_runners = list(idle_runners_by_id.values())

            if not activated_any and not tasks:
                print(f"[SubAgents] No more tasks can be assigned. {len(idle_runners)} agents remain idle.")
                break

            continue

        # Build the set of tasks to wait on (engineers + optional exploration)
        wait_tasks = set(tasks.keys())
        if exploration_task and not exploration_task.done():
            wait_tasks.add(exploration_task)

        done, _ = await asyncio.wait(
            wait_tasks,
            return_when=asyncio.FIRST_COMPLETED
        )

        # Separate exploration completion from engineer completion
        exploration_completed = False
        engineer_tasks_done = []
        for task in done:
            if task == exploration_task:
                exploration_completed = True
                print("[Manager] Background exploration completed")
                try:
                    explore_result = task.result()
                    if explore_result.get("cancelled"):
                        print("[Manager] Exploration was cancelled")
                except Exception as e:
                    print(f"[Manager] Exploration error: {e}")
                exploration_task = None
            else:
                engineer_tasks_done.append(task)

        # If only exploration completed (no engineers), just continue waiting
        if exploration_completed and not engineer_tasks_done and tasks:
            continue

        # Engineers completed - signal exploration to stop
        if engineer_tasks_done and exploration_task and not exploration_task.done():
            print("[Manager] Engineer finished - stopping exploration immediately...")
            if manager:
                manager.cancel_exploration()
            try:
                await exploration_task
            except Exception as error:
                print(f"[Manager] Exploration stopped with: {error}")
            exploration_task = None

        # Sort completed tasks by end_time to process in completion order
        completed_with_results = []
        for task in engineer_tasks_done:
            runner = tasks[task]
            try:
                result = task.result()
                end_time = result.end_time if result.end_time else datetime.now().isoformat()
                completed_with_results.append((task, result, end_time))
            except Exception as e:
                error_result = runner.create_result()
                error_result.success = False
                error_result.error = str(e)
                error_result.end_time = datetime.now().isoformat()
                completed_with_results.append((task, error_result, error_result.end_time))

        completed_with_results.sort(key=lambda x: x[2])

        for completed_task, result, _ in completed_with_results:
            runner = tasks.pop(completed_task)
            engineer_id = runner.subagent.engineer_id

            try:
                results.append(result)

                print(f"\n[SubAgents] {engineer_id} completed (round {result.round_num})")
                print(f"- Success: {result.success}")
                print(f"- Completed rounds: {runner.completed_rounds}/{runner.max_rounds_chat}")
                for line in task_module.get_completion_print_lines(result):
                    print(line)

                if output_logger:
                    log_kwargs = task_module.get_log_agent_response_kwargs(result)
                    output_logger.log_agent_response(**log_kwargs)

                if is_commit0_probe_enabled() and result.worktree_path:
                    write_probe(
                        workspace=runner.workspace,
                        output_dir=runner.output_dir,
                        repo_name=task_module.config.repo_name,
                        workspace_path=result.worktree_path,
                        checkpoint_id=f"agent_artifact:{result.engineer_id}:round{result.round_num}",
                        checkpoint_type="agent_artifact",
                        agent_id=result.engineer_id,
                        task_id=result.task_id,
                        workspace_kind="agent_workspace",
                        artifact_version=result.commit_hash or read_head(runner.workspace, result.worktree_path),
                    )

                if manager:
                    collect_result = manager.collect_and_merge(result, output_logger)
                    result.merged = collect_result.get("merged", False)
                    result.merge_method = collect_result.get("merge_method", "")
                    conflict_files = collect_result.get("conflict_files", [])

                    if is_commit0_probe_enabled():
                        write_probe(
                            workspace=manager.workspace,
                            output_dir=runner.output_dir,
                            repo_name=task_module.config.repo_name,
                            workspace_path=manager.repo_dir,
                            checkpoint_id=f"integration_after_merge:{result.engineer_id}:round{result.round_num}",
                            checkpoint_type="integration_after_merge",
                            agent_id=result.engineer_id,
                            task_id=result.task_id,
                            workspace_kind="integrated_workspace",
                            artifact_version=result.commit_hash,
                            integrated_workspace_version=read_head(manager.workspace, manager.repo_dir),
                        )

                    # Merge conflict: engineer must resolve it in their worktree
                    if result.merge_method == "conflict" and conflict_files:
                        if runner.can_accept_more_tasks():
                            print(f"\n[SubAgents] {engineer_id} has merge conflict - assigning conflict resolution task")
                            print(f"- Conflict files: {', '.join(conflict_files)}")

                            runner.result = None
                            runner.subagent.current_round = runner.completed_rounds + 1

                            conflict_args = task_module.get_conflict_instruction_args(
                                runner.subagent, conflict_files, manager.workspace, manager.repo_dir
                            )
                            conflict_template = runner.prompts.get("conflict_resolution", "")
                            runner.subagent.instruction = conflict_template.format(**conflict_args)

                            print(f"- Task: {runner.subagent.task_id} (conflict resolution)")
                            print(f"- Round: {runner.subagent.current_round}")

                            new_task = asyncio.create_task(run_single_runner(runner))
                            tasks[new_task] = runner
                            continue
                        else:
                            print(f"\n[SubAgents] {engineer_id} has merge conflict but no rounds left - deferring to manager final review")
                            result.conflict_files = conflict_files

                    # Auto-reassign if engineer didn't commit (merged=False)
                    if not result.merged and not conflict_files and runner.can_accept_more_tasks():
                        print(f"\n[SubAgents] {engineer_id} didn't commit - auto-reassigning same task to continue")

                        runner.result = None
                        runner.subagent.current_round = runner.completed_rounds + 1

                        reassign_args = task_module.get_auto_reassign_instruction_args(runner.subagent)
                        reassign_template = runner.prompts.get("auto_reassign", "")
                        runner.subagent.instruction = reassign_template.format(**reassign_args)

                        print(f"- Task: {runner.subagent.task_id}")
                        for line in task_module.get_new_task_print_lines(runner.subagent):
                            print(line)
                        print(f"- Round: {runner.subagent.current_round}")

                        new_task = asyncio.create_task(run_single_runner(runner))
                        tasks[new_task] = runner
                        continue

                    if runner.can_accept_more_tasks():
                        running_agents = [tasks[t].subagent.engineer_id for t in tasks]
                        idle_engineer_ids = [r.subagent.engineer_id for r in idle_runners]
                        inactive_engineer_ids = [aid for aid in all_possible_agents if aid not in active_engineer_ids]

                        assignment = manager.assign_task(
                            completed_result=result,
                            all_completed=results,
                            running_agents=running_agents,
                            idle_agents=idle_engineer_ids,
                            inactive_agents=inactive_engineer_ids,
                            finished_agents=list(finished_engineer_ids),
                        )

                        # Build a map of all available runners (completed + idle)
                        available_runners = {engineer_id: runner}
                        for idle_runner in idle_runners:
                            available_runners[idle_runner.subagent.engineer_id] = idle_runner

                        # Process all assignments from manager
                        assigned_engineer_ids = set()
                        for new_subagent in assignment.get("assignments", []):
                            target_engineer_id = new_subagent.engineer_id
                            if target_engineer_id in available_runners:
                                target_runner = available_runners[target_engineer_id]
                                new_subagent.current_round = target_runner.completed_rounds + 1

                                task_module.prepare_reuse_subagent(new_subagent, target_runner)

                                print(f"\n[SubAgents] Assigning {target_engineer_id} with new task (round {new_subagent.current_round})")
                                print(f"- New task: {new_subagent.task_id}")
                                for line in task_module.get_new_task_print_lines(new_subagent):
                                    print(line)

                                target_runner.update_task(new_subagent)

                                new_task = asyncio.create_task(run_single_runner(target_runner))
                                tasks[new_task] = target_runner
                                assigned_engineer_ids.add(target_engineer_id)
                                print(f"[SubAgents] {target_engineer_id} added back to task pool for round {new_subagent.current_round}")

                            elif target_engineer_id in inactive_engineer_ids:
                                print(f"\n[SubAgents] Onboarding inactive engineer {target_engineer_id}...")

                                cmd_result = manager.workspace.execute_command(
                                    f"cd {manager.repo_dir} && git rev-parse HEAD", timeout=30
                                )
                                base_commit = cmd_result.stdout.strip() if cmd_result.exit_code == 0 else ""

                                branch_name, worktree_name = task_module.get_onboard_names(target_engineer_id)
                                worktree_path = f"/workspace/{worktree_name}"

                                branch_cmd = (
                                    f"cd {manager.repo_dir} && "
                                    f"git branch {branch_name} {base_commit} 2>/dev/null || true"
                                )
                                manager.workspace.execute_command(branch_cmd, timeout=30)

                                worktree_cmd = (
                                    f"cd {manager.repo_dir} && "
                                    f"git worktree add {worktree_path} {branch_name}"
                                )
                                worktree_result = manager.workspace.execute_command(worktree_cmd, timeout=60)

                                if worktree_result.exit_code != 0:
                                    print(f"[SubAgents] Failed to create worktree for {target_engineer_id}: {worktree_result.stderr}")
                                    continue

                                new_subagent.branch_name = branch_name
                                new_subagent.worktree_path = worktree_path
                                new_subagent.base_commit = base_commit
                                task_module.post_onboard_subagent(new_subagent, manager.repo_dir)
                                new_subagent.current_round = 1

                                template_runner = runner
                                new_runner = template_runner.clone_for_subagent(
                                    new_subagent
                                )

                                print(f"- Worktree: {worktree_path}")
                                print(f"- Branch: {branch_name}")
                                print(f"- Task: {new_subagent.task_id}")
                                for line in task_module.get_new_task_print_lines(new_subagent):
                                    print(line)

                                new_task = asyncio.create_task(run_single_runner(new_runner))
                                tasks[new_task] = new_runner
                                assigned_engineer_ids.add(target_engineer_id)
                                active_engineer_ids.add(target_engineer_id)
                                print(f"[SubAgents] {target_engineer_id} onboarded and added to task pool")

                        # Move completed runner to idle if not assigned
                        if engineer_id not in assigned_engineer_ids:
                            print(f"[SubAgents] {engineer_id} moved to idle pool (waiting for dependencies)")
                            idle_runners.append(runner)

                        # Update idle_runners: remove those that got assigned
                        idle_runners = [r for r in idle_runners if r.subagent.engineer_id not in assigned_engineer_ids]
                    else:
                        print(f"[SubAgents] {engineer_id} reached max rounds ({runner.max_rounds_chat})")
                        finished_engineer_ids.add(engineer_id)
                        print(f"[SubAgents] {engineer_id} marked as finished")

            except Exception as e:
                print(f"[SubAgents] ERROR processing {engineer_id}: {e}")
                error_result = runner.create_result()
                error_result.success = False
                error_result.error = str(e)
                error_result.end_time = datetime.now().isoformat()
                results.append(error_result)

                if output_logger:
                    output_logger.log_agent_response(
                        engineer_id=error_result.engineer_id,
                        task_id=error_result.task_id,
                        success=False,
                        error=str(e),
                        round_num=error_result.round_num,
                    )

        # Status update for remaining active tasks
        if tasks:
            remaining_info = []
            for t in tasks:
                r = tasks[t]
                remaining_info.append(f"{r.subagent.engineer_id}(r{r.subagent.current_round})")
            idle_info = [r.subagent.engineer_id for r in idle_runners] if idle_runners else []
            print(f"\n[SubAgents] Active: {remaining_info}, Idle: {idle_info}")

    for line in task_module.get_execution_summary_lines(results):
        print(line)

    return results
