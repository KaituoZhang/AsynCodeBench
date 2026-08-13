import pytest
from core.subagent import (
    SubAgentRunner,
    _is_ambiguous_run_trigger_timeout,
    classify_conversation_termination,
    configure_remote_message_timeout,
    configure_remote_status_polling,
    conversation_error_requires_fresh,
    latest_conversation_error,
    reconcile_conversation_events,
    result_requires_fresh_conversation,
    run_conversation_with_trigger_recovery,
    send_conversation_message,
)


class FakeConversation:
    def __init__(self, statuses):
        self.statuses = iter(statuses)
        self.run_calls = 0
        self.wait_calls = []

    def run(self, poll_interval, timeout):
        self.run_calls += 1
        self.run_poll_interval = poll_interval
        self.run_timeout = timeout
        if self.run_calls == 1:
            raise RuntimeError("Conversation run failed for id=test: timed out")

    def _wait_for_run_completion(self, poll_interval, timeout):
        self.wait_calls.append((poll_interval, timeout))

    def _poll_status_once(self):
        return next(self.statuses)


def test_recovers_accepted_trigger_timeout(monkeypatch):
    monkeypatch.setenv("ASYNCODEBENCH_CONVERSATION_RUN_TIMEOUT", "7200")
    conversation = FakeConversation(["finished"])
    messages = []

    run_conversation_with_trigger_recovery(conversation, messages.append)

    assert conversation.run_calls == 1
    assert conversation.run_timeout == 7200.0
    assert conversation.run_poll_interval == 5.0
    assert conversation.wait_calls == [(5.0, 7200.0)]
    assert "polling the same conversation" in messages[0]


def test_retries_trigger_when_conversation_remains_idle():
    conversation = FakeConversation(["idle"])

    run_conversation_with_trigger_recovery(conversation, lambda _message: None)

    assert conversation.run_calls == 2


@pytest.mark.parametrize(
    "message",
    [
        "Conversation run failed for id=test: Run timed out after 3600 seconds",
        "Conversation run failed for id=test: Remote conversation ended with error",
        "LLMContextWindowExceedError: requested too many tokens",
    ],
)
def test_does_not_mask_terminal_failures(message):
    assert not _is_ambiguous_run_trigger_timeout(RuntimeError(message))


class FakeEvents(list):
    def __init__(self, events, added):
        super().__init__(events)
        self.added = added

    def reconcile(self):
        return self.added


class FakeState:
    def __init__(self, events):
        self.events = events


class FakeEventConversation:
    def __init__(self, events):
        self.state = FakeState(events)


def test_reconciles_remote_events_before_metrics():
    messages = []
    conversation = FakeEventConversation(FakeEvents([], added=7))

    added = reconcile_conversation_events(conversation, messages.append)

    assert added == 7
    assert "Reconciled 7 remote event(s)" in messages[0]


def test_extracts_latest_structured_remote_error():
    ErrorEvent = type("ConversationErrorEvent", (), {})
    older = ErrorEvent()
    older.code = "OlderError"
    older.detail = "old"
    latest = ErrorEvent()
    latest.code = "MaxIterationsReached"
    latest.detail = "Agent reached maximum iterations limit (2)."

    assert latest_conversation_error([older, latest]) == (
        "MaxIterationsReached: Agent reached maximum iterations limit (2)."
    )


def test_classifies_normal_agent_finish_without_cap_hit():
    conversation = FakeEventConversation([])
    conversation.state.execution_status = "finished"

    reason, cap_hit = classify_conversation_termination(
        conversation, iterations=18, max_iterations=100
    )

    assert reason == "agent_finish"
    assert cap_hit is False


def test_classifies_iteration_limit_as_cap_hit():
    ErrorEvent = type("ConversationErrorEvent", (), {})
    event = ErrorEvent()
    event.code = "MaxIterationsReached"
    event.detail = "Agent reached maximum iterations limit (100)."
    conversation = FakeEventConversation([event])
    conversation.state.execution_status = "error"

    reason, cap_hit = classify_conversation_termination(
        conversation, iterations=100, max_iterations=100
    )

    assert reason == "iteration_limit"
    assert cap_hit is True


class FakePollResponse:
    def __init__(self, status="running"):
        self.status_code = 200
        self.status = status

    def raise_for_status(self):
        return None

    def json(self):
        return {"execution_status": self.status}


class FakePollClient:
    def __init__(self, statuses=None):
        self.calls = []
        self.statuses = iter(statuses or ["running"])

    def get(self, path, timeout):
        self.calls.append((path, timeout))
        return FakePollResponse(next(self.statuses))

    def post(self, path, timeout):
        self.calls.append((path, timeout))
        return FakePollResponse()


class FakeRemoteConversation:
    def __init__(self, statuses=None):
        self._client = FakePollClient(statuses)
        self._id = "conversation-id"

    def _poll_status_once(self):
        raise AssertionError("legacy fixed-timeout poll should be replaced")


class FakeMessageConversation:
    def __init__(self):
        self._client = FakePollClient()
        self.messages = []

    def send_message(self, message):
        self.messages.append((message, self._client.timeout.read))


def test_configures_long_remote_message_timeout(monkeypatch):
    monkeypatch.setenv("ASYNCODEBENCH_REMOTE_MESSAGE_TIMEOUT", "900")
    messages = []
    conversation = FakeMessageConversation()

    assert configure_remote_message_timeout(conversation, messages.append)
    send_conversation_message(conversation, "next task", messages.append)

    assert conversation.messages == [("next task", 900.0)]
    assert messages == ["Configured remote message request timeout: 900.0s"]


def test_rejects_nonpositive_remote_message_timeout(monkeypatch):
    monkeypatch.setenv("ASYNCODEBENCH_REMOTE_MESSAGE_TIMEOUT", "0")

    with pytest.raises(ValueError, match="must be positive"):
        configure_remote_message_timeout(
            FakeMessageConversation(),
            lambda _message: None,
        )


def test_configures_long_remote_status_poll_timeout(monkeypatch):
    monkeypatch.setenv("ASYNCODEBENCH_REMOTE_POLL_TIMEOUT", "900")
    messages = []
    conversation = FakeRemoteConversation()

    assert configure_remote_status_polling(conversation, messages.append)
    assert conversation._poll_status_once() == "running"
    assert conversation._client.calls == [
        ("/api/conversations/conversation-id", 900.0)
    ]
    assert "request_timeout=900.0s" in messages[0]


def test_rejects_nonpositive_remote_poll_timeout(monkeypatch):
    monkeypatch.setenv("ASYNCODEBENCH_REMOTE_POLL_TIMEOUT", "0")

    with pytest.raises(ValueError, match="must be positive"):
        configure_remote_status_polling(FakeRemoteConversation(), lambda _message: None)


class FakeManagedRemoteConversation(FakeRemoteConversation):
    def __init__(self, statuses=None):
        super().__init__(statuses or ["finished"])


def test_remote_trigger_uses_managed_request_without_sdk_run(monkeypatch):
    monkeypatch.setenv("ASYNCODEBENCH_REMOTE_TRIGGER_TIMEOUT", "45")
    monkeypatch.setenv("ASYNCODEBENCH_REMOTE_TERMINAL_CONFIRM_SECONDS", "0")
    conversation = FakeManagedRemoteConversation()

    run_conversation_with_trigger_recovery(conversation, lambda _message: None)

    assert conversation._client.calls == [
        ("/api/conversations/conversation-id/run", 45.0),
        ("/api/conversations/conversation-id", 900.0),
    ]


def test_remote_trigger_waits_through_running_state(monkeypatch):
    monkeypatch.setenv("ASYNCODEBENCH_REMOTE_TERMINAL_CONFIRM_SECONDS", "0")
    monkeypatch.setattr("core.subagent.time.sleep", lambda _seconds: None)
    conversation = FakeManagedRemoteConversation(["running", "finished"])
    messages = []

    run_conversation_with_trigger_recovery(conversation, messages.append)

    assert len(conversation._client.calls) == 3


def test_remote_trigger_timeout_is_recovered_without_sdk_error_log(monkeypatch):
    monkeypatch.setenv("ASYNCODEBENCH_REMOTE_TERMINAL_CONFIRM_SECONDS", "0")
    conversation = FakeManagedRemoteConversation()
    messages = []

    def delayed_post(_path, timeout):
        assert timeout == 30.0
        raise TimeoutError("timed out")

    conversation._client.post = delayed_post
    run_conversation_with_trigger_recovery(conversation, messages.append)

    assert any("acknowledgement is delayed" in message for message in messages)


def test_remote_trigger_retries_only_after_idle_grace(monkeypatch):
    monkeypatch.setenv("ASYNCODEBENCH_REMOTE_START_GRACE_SECONDS", "0")
    monkeypatch.setenv("ASYNCODEBENCH_REMOTE_TERMINAL_CONFIRM_SECONDS", "0")
    conversation = FakeManagedRemoteConversation(["idle", "finished"])

    run_conversation_with_trigger_recovery(conversation, lambda _message: None)

    post_calls = [
        call for call in conversation._client.calls if call[0].endswith("/run")
    ]
    assert len(post_calls) == 2


def test_rejects_nonpositive_remote_trigger_timeout(monkeypatch):
    monkeypatch.setenv("ASYNCODEBENCH_REMOTE_TRIGGER_TIMEOUT", "0")

    with pytest.raises(ValueError, match="must be positive"):
        run_conversation_with_trigger_recovery(
            FakeManagedRemoteConversation(),
            lambda _message: None,
        )


@pytest.mark.parametrize(
    "error",
    [
        "Remote conversation got stuck",
        "MaxIterationsReached: Agent reached maximum iterations limit (30).",
        "ConversationRunError: Run timed out after 3600 seconds",
        "Remote conversation ended with error",
    ],
)
def test_terminal_result_requires_fresh_conversation(error):
    result = type("Result", (), {"error": error})()

    assert result_requires_fresh_conversation(result)


def test_terminal_error_requires_fresh_conversation():
    assert conversation_error_requires_fresh(
        "Conversation run failed: Run timed out after 3600 seconds"
    )
    assert not conversation_error_requires_fresh("No new commit was made")


def test_ordinary_task_failure_keeps_reusable_conversation():
    result = type(
        "Result",
        (),
        {"error": "No new commit was made. Agent may have run out of iterations."},
    )()

    assert not result_requires_fresh_conversation(result)


def test_update_task_restarts_only_terminal_conversation(monkeypatch):
    runner = SubAgentRunner.__new__(SubAgentRunner)
    runner.subagent = type("SubAgent", (), {"engineer_id": "engineer_1"})()
    runner.last_result = type(
        "Result",
        (),
        {"error": "MaxIterationsReached: maximum iterations reached"},
    )()
    runner.result = object()
    runner.conversation_round = 1
    setup_calls = []
    monkeypatch.setattr(
        runner,
        "setup",
        lambda: (
            setup_calls.append(True),
            setattr(runner, "conversation_round", runner.subagent.current_round),
        ),
    )
    monkeypatch.setattr(runner, "log", lambda _message: None)
    new_subagent = type(
        "SubAgent",
        (),
        {
            "engineer_id": "engineer_1",
            "current_round": 2,
            "task_id": "round-2-task",
            "file_path": "module.py",
        },
    )()

    runner.update_task(new_subagent)

    assert setup_calls == [True]
    assert runner.subagent is new_subagent
    assert runner.result is None

    runner.ensure_usable_conversation_for_round()
    assert setup_calls == [True]
