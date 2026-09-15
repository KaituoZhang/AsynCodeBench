from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from protocols.async_manager_v2 import POLICY
from protocols.async_manager_v2.manager import BudgetedOnlineManager, load_profile
from protocols.async_manager_v2.results import _budget_issues
from run_async_manager_v2 import (
    _error_classification,
    _write_partial_result,
    protocol_sources,
)


def bare_manager(tmp_path: Path) -> BudgetedOnlineManager:
    manager = BudgetedOnlineManager.__new__(BudgetedOnlineManager)
    manager.config = SimpleNamespace(output_dir=str(tmp_path))
    manager.manager_iterations_limit = 100
    manager.manager_tokens_limit = 8_000_000
    manager.manager_active_seconds_limit = 21_600.0
    manager.manager_event_seconds_limit = 7_200.0
    manager.manager_interventions_limit = 6
    manager.manager_shutdown_grace = 1.0
    manager.manager_iterations_total = 0
    manager.manager_budget_tokens_total = 0
    manager.manager_budget_active_seconds_total = 0.0
    manager.manager_interventions_executed = 0
    manager.intervention_sequence = 0
    manager.manager_budget_exhausted = False
    manager.manager_budget_reasons = []
    manager.manager_budget_phase = "test"
    manager.last_run_budget_interrupted = False
    manager.last_termination_reason = "unknown"
    manager.last_iteration_cap_hit = False
    manager.log = lambda _message: None
    return manager


def test_v2_profile_pins_task_level_budget():
    profile = load_profile()
    assert profile["policy"] == POLICY
    assert profile["manager_max_iterations_per_event"] == 30
    assert profile["manager_max_iterations_total"] == 100
    assert profile["manager_max_interventions"] == 6
    assert profile["budget_exhaustion_policy"].startswith("stop_manager_calls")


def test_v2_is_additive_in_official_registry():
    repository_root = Path(__file__).resolve().parents[3]
    registry = json.loads(
        (repository_root / "configs/evaluation/protocol_registry.v1.json").read_text()
    )
    profile = json.loads(
        (
            repository_root
            / "configs/evaluation/official_execution_profile.v4.json"
        ).read_text()
    )

    async_manager = registry["protocols"]["async_manager"]
    assert async_manager["policy"] == "async-manager-online-v1"
    assert async_manager["execution_profile"].endswith(
        "official_execution_profile.v3.json"
    )
    assert (
        async_manager["additional_policies"][POLICY]["runner"]
        == "reproductions/async-swe-agents/run_async_manager_v2.py"
    )
    assert profile["protocols"]["single"]["manager_max_iterations"] == 100
    assert profile["protocols"]["async_manager"]["manager_max_iterations"] == 30
    assert profile["manager_budget"]["manager_max_iterations_total"] == 100


def test_v2_policy_install_keeps_source_preflight_non_recursive(monkeypatch):
    monkeypatch.setattr("run_async_manager.protocol_sources", protocol_sources)

    sources = protocol_sources()

    assert Path(__file__).resolve().parents[1] / "run_async_manager_v2.py" in sources
    assert len(sources) == len(set(sources))


def test_task_level_iteration_budget_stops_before_another_remote_run(tmp_path):
    manager = bare_manager(tmp_path)
    manager.manager_iterations_total = 100

    assert manager.run_active_conversation() is None
    assert manager.last_termination_reason == "manager_budget_exhausted"
    assert manager.last_iteration_cap_hit is True
    state = json.loads((tmp_path / "manager_budget.json").read_text())
    assert state["exhausted"] is True
    assert state["exhaustion_reasons"] == ["manager_iterations_total"]


def test_remaining_iteration_budget_rotates_remote_transport(tmp_path, monkeypatch):
    manager = bare_manager(tmp_path)
    manager.manager_iterations_total = 95
    manager.config.manager_max_iterations = 30
    manager.conversation_needs_reset = False
    manager.conversation = SimpleNamespace(max_iteration_per_run=30)
    observed_caps = []

    def rotate():
        observed_caps.append(manager.config.manager_max_iterations)
        manager.conversation = SimpleNamespace(
            max_iteration_per_run=manager.config.manager_max_iterations
        )
        manager.conversation_needs_reset = False

    manager.ensure_usable_conversation = rotate
    monkeypatch.setattr(
        "protocols.async_manager_v2.manager.extract_conversation_metrics",
        lambda _conversation: {"total_tokens": 0},
    )

    def run_parent(_manager):
        assert manager.conversation.max_iteration_per_run == 5
        manager.manager_iterations_total += 5

    monkeypatch.setattr(
        "protocols.async_manager.manager.OnlineManager.run_active_conversation",
        run_parent,
    )

    manager.run_active_conversation()

    assert observed_caps == [5]
    assert manager.manager_iterations_total == 100
    assert manager.config.manager_max_iterations == 30


def test_shutdown_interrupts_running_remote_and_confirms_terminal_state(tmp_path):
    manager = bare_manager(tmp_path)

    class Conversation:
        def __init__(self):
            self.statuses = iter(["running", "running", "finished"])
            self.interrupted = False

        def _poll_status_once(self):
            return next(self.statuses)

        def interrupt(self):
            self.interrupted = True

    manager.conversation = Conversation()
    result = manager._interrupt_and_confirm("operator_cancelled")

    assert manager.conversation.interrupted is True
    assert result["attempted"] is True
    assert result["confirmed"] is True
    assert result["final_status"] == "finished"


def test_budget_validation_reports_missing_snapshot_and_unconfirmed_shutdown(
    tmp_path,
):
    (tmp_path / "manager_budget.json").write_text(
        json.dumps(
            {
                "policy": POLICY,
                "limits": {
                    "manager_iterations_total": 100,
                    "manager_tokens_total": 8_000_000,
                    "manager_active_seconds_total": 21_600,
                    "manager_interventions": 6,
                },
                "usage": {
                    "manager_iterations_total": 10,
                    "manager_tokens_total": 100,
                    "manager_active_seconds_total": 10,
                    "manager_interventions": 1,
                },
            }
        )
    )
    (tmp_path / "manager_shutdown.json").write_text(
        json.dumps({"confirmed": False})
    )

    issues = _budget_issues(tmp_path)

    assert "manager_shutdown_unconfirmed" in issues
    assert "invalid_or_missing_async_manager_profile_snapshot" in issues


def test_interrupted_run_writes_classified_partial_bundle(tmp_path):
    try:
        raise ConnectionError("[Errno 111] Connection refused")
    except ConnectionError as error:
        _write_partial_result(tmp_path, error)

    record = json.loads(
        (tmp_path / "async_manager_execution_error.json").read_text()
    )
    partial = json.loads((tmp_path / "partial_run_bundle.json").read_text())
    assert record["classification"] == "infrastructure_agent_server_unavailable"
    assert record["traceback"]
    assert partial["evaluation_complete"] is False
    assert "run_status.json" in partial["artifacts"]


def test_operator_cancellation_is_distinct_from_infrastructure_failure():
    assert _error_classification(KeyboardInterrupt()) == "operator_cancelled"
