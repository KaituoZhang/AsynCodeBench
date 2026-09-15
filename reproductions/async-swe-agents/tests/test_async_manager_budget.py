from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from asyncodebench_harness.protocol_registry import protocol_registry_path
from asyncodebench_harness.results import _async_manager_validator
from protocols.async_manager import LEGACY_POLICY, POLICY
from protocols.async_manager.budget import BudgetedOnlineManager, load_profile
from protocols.async_manager.results import _budget_issues, validate
from run_async_manager import (
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


def test_canonical_profile_pins_task_level_budget():
    profile = load_profile()
    assert profile["policy"] == POLICY
    assert profile["manager_max_iterations_per_event"] == 30
    assert profile["manager_max_iterations_total"] == 100
    assert profile["manager_max_interventions"] == 6
    assert profile["candidate_patch_validation"] == {
        "enabled": True,
        "mode": "affected_dependency_selectors_no_regression",
        "timeout_seconds": 600,
        "max_selectors": 40,
        "require_all_selectors_collected": True,
        "require_no_regression": True,
    }
    assert profile["budget_exhaustion_policy"].startswith("stop_manager_calls")


def test_candidate_selector_cap_covers_every_current_task_manifest():
    root = Path(__file__).resolve().parents[3]
    maximum = 0
    for path in (root / "manifests").glob("**/*_async_metrics.json"):
        metrics = json.loads(path.read_text(encoding="utf-8"))
        selectors = {
            selector
            for dependency in metrics.get("dependency_points", [])
            for selector in dependency.get("integrated_probe_tests", [])
        }
        maximum = max(maximum, len(selectors))

    assert maximum == 38
    assert load_profile()["candidate_patch_validation"]["max_selectors"] >= maximum


def test_budgeted_policy_is_canonical_in_current_registry():
    repository_root = Path(__file__).resolve().parents[3]
    registry = json.loads(
        (repository_root / "configs/evaluation/protocol_registry.v2.json").read_text()
    )
    profile = json.loads(
        (
            repository_root
            / "configs/evaluation/official_execution_profile.v4.json"
        ).read_text()
    )

    async_manager = registry["protocols"]["async_manager"]
    assert async_manager["policy"] == POLICY
    assert async_manager["execution_profile"].endswith(
        "official_execution_profile.v4.json"
    )
    assert (
        async_manager["runner"]
        == "reproductions/async-swe-agents/run_async_manager.py"
    )
    assert profile["protocols"]["single"]["manager_max_iterations"] == 100
    assert profile["protocols"]["async_manager"]["manager_max_iterations"] == 30
    assert profile["manager_budget"]["manager_max_iterations_total"] == 100


def test_registry_v1_remains_immutable_for_historical_bundles():
    assert (
        hashlib.sha256(
            protocol_registry_path(
                "configs/evaluation/protocol_registry.v1.json"
            ).read_bytes()
        ).hexdigest()
        == "5f3d0799608ad05f28c4ca4110912b9ea296255955238438027a0cf91f222b6a"
    )


def test_common_validator_dispatches_both_async_manager_policies():
    assert _async_manager_validator(POLICY).__module__ == (
        "protocols.async_manager.results"
    )
    assert _async_manager_validator(LEGACY_POLICY).__module__ == (
        "protocols.async_manager.legacy_results"
    )
    assert _async_manager_validator("unknown") is None


def test_protocol_source_inventory_is_unique():
    sources = protocol_sources()

    assert Path(__file__).resolve().parents[1] / "run_async_manager.py" in sources
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
    old_conversation = SimpleNamespace(max_iteration_per_run=30, messages=[])
    manager.conversation = old_conversation
    observed_caps = []

    def rotate():
        observed_caps.append(manager.config.manager_max_iterations)
        manager.conversation = SimpleNamespace(
            max_iteration_per_run=manager.config.manager_max_iterations,
            messages=[],
        )
        manager.conversation_needs_reset = False

    manager.ensure_usable_conversation = rotate
    monkeypatch.setattr(
        "protocols.async_manager.budget.extract_conversation_metrics",
        lambda _conversation: {"total_tokens": 0},
    )

    def run_parent(_manager):
        assert manager.conversation.max_iteration_per_run == 5
        manager.manager_iterations_total += 5

    monkeypatch.setattr(
        "protocols.async_manager.manager.OnlineManager.run_active_conversation",
        run_parent,
    )
    monkeypatch.setattr(
        "protocols.async_manager.manager.OnlineManager.send_message",
        lambda current, message: current.conversation.messages.append(message),
    )

    manager._prepare_budgeted_conversation()
    manager.send_message("CURRENT CHECKPOINT INSTRUCTION")
    manager.run_active_conversation()

    assert observed_caps == [5]
    assert old_conversation.messages == []
    assert manager.conversation.messages == ["CURRENT CHECKPOINT INSTRUCTION"]
    assert manager.manager_iterations_total == 100
    assert manager.config.manager_max_iterations == 30


def test_phase_prepares_session_before_metric_baseline(tmp_path, monkeypatch):
    manager = bare_manager(tmp_path)
    manager.manager_iterations_total = 95
    manager.config.manager_max_iterations = 30
    manager.conversation_needs_reset = False
    old_conversation = SimpleNamespace(
        max_iteration_per_run=30, messages=[], total_tokens=500
    )
    manager.conversation = old_conversation

    def rotate():
        manager.conversation = SimpleNamespace(
            max_iteration_per_run=manager.config.manager_max_iterations,
            messages=[],
            total_tokens=0,
        )
        manager.conversation_needs_reset = False

    manager.ensure_usable_conversation = rotate
    monkeypatch.setattr(
        "protocols.async_manager.budget.extract_conversation_metrics",
        lambda conversation: {"total_tokens": conversation.total_tokens},
    )
    monkeypatch.setattr(
        "protocols.async_manager.manager.OnlineManager.send_message",
        lambda current, message: current.conversation.messages.append(message),
    )

    def run_parent(current):
        current.conversation.total_tokens += 25
        current.manager_iterations_total += 5

    monkeypatch.setattr(
        "protocols.async_manager.manager.OnlineManager.run_active_conversation",
        run_parent,
    )

    def assign_parent(current, *_args, **_kwargs):
        before = current.conversation.total_tokens
        current.send_message("ASSIGNMENT CHECKPOINT")
        current.run_active_conversation()
        return {"token_delta": current.conversation.total_tokens - before}

    monkeypatch.setattr(
        "protocols.async_manager.manager.OnlineManager.assign_task",
        assign_parent,
    )

    result = manager.assign_task(None, None, None)

    assert result["token_delta"] == 25
    assert old_conversation.messages == []
    assert manager.conversation.messages == ["ASSIGNMENT CHECKPOINT"]


def test_smaller_phase_cap_is_not_expanded_by_budget_guard(tmp_path, monkeypatch):
    manager = bare_manager(tmp_path)
    manager.config.manager_max_iterations = 30
    manager.conversation_needs_reset = False
    manager.conversation = SimpleNamespace(max_iteration_per_run=10)
    monkeypatch.setattr(
        "protocols.async_manager.budget.extract_conversation_metrics",
        lambda _conversation: {"total_tokens": 0},
    )
    observed_caps = []
    monkeypatch.setattr(
        "protocols.async_manager.manager.OnlineManager.run_active_conversation",
        lambda current: observed_caps.append(
            current.conversation.max_iteration_per_run
        ),
    )

    manager.run_active_conversation()

    assert observed_caps == [10]


def test_iteration_limit_is_not_recorded_as_runtime_failure(tmp_path, monkeypatch):
    manager = bare_manager(tmp_path)
    manager.config.manager_max_iterations = 30
    manager.conversation_needs_reset = False
    manager.conversation = SimpleNamespace(max_iteration_per_run=30)
    monkeypatch.setattr(
        "protocols.async_manager.budget.extract_conversation_metrics",
        lambda _conversation: {"total_tokens": 0},
    )

    def reach_cap(current):
        current.last_termination_reason = "iteration_limit"
        current.last_iteration_cap_hit = True
        raise RuntimeError("MaxIterationsReached: maximum iterations reached")

    monkeypatch.setattr(
        "protocols.async_manager.manager.OnlineManager.run_active_conversation",
        reach_cap,
    )

    with pytest.raises(RuntimeError, match="MaxIterationsReached"):
        manager.run_active_conversation()

    assert not (tmp_path / "manager_runtime_errors.jsonl").exists()


def test_runtime_error_record_stringifies_conversation_uuid(tmp_path):
    manager = bare_manager(tmp_path)
    conversation_id = uuid.uuid4()
    manager.conversation = SimpleNamespace(id=conversation_id)

    manager._record_runtime_error(RuntimeError("original manager failure"))

    record = json.loads(
        (tmp_path / "manager_runtime_errors.jsonl").read_text(encoding="utf-8")
    )
    assert record["conversation_id"] == str(conversation_id)
    assert record["detail"] == "original manager failure"


def test_async_manager_event_logging_normalizes_sdk_json_types():
    manager = BudgetedOnlineManager.__new__(BudgetedOnlineManager)
    response_id = uuid.uuid4()
    action_id = uuid.uuid4()
    event = SimpleNamespace(
        timestamp=datetime(2026, 9, 15, tzinfo=timezone.utc),
        llm_response_id=response_id,
        action=SimpleNamespace(
            action="file_editor",
            args={"request_id": action_id},
            thought=None,
        ),
        observation=None,
        llm_message=None,
        thought=None,
        reasoning_content=None,
    )
    captured = []
    manager.conversation = SimpleNamespace(
        state=SimpleNamespace(events=[event])
    )
    manager.output_logger = SimpleNamespace(
        log_agent_event=lambda agent_id, payload: captured.append(
            (agent_id, payload)
        )
    )
    manager.log = lambda _message: None

    manager.save_events("online_intervention_1")

    assert captured[0][0] == "manager"
    payload = captured[0][1]
    assert payload["timestamp"] == "2026-09-15T00:00:00+00:00"
    assert payload["llm_response_id"] == str(response_id)
    assert payload["action"]["args"]["request_id"] == str(action_id)
    json.dumps(payload)


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


def test_new_profile_requires_auditable_candidate_validation(
    tmp_path, monkeypatch
):
    artifact = tmp_path / "manager_candidate_validations/0001/validation.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text('{"passed": true}\n', encoding="utf-8")
    (tmp_path / "async_manager_profile_snapshot.json").write_text(
        json.dumps(
            {
                "candidate_patch_validation": {
                    "enabled": True,
                    "mode": "affected_dependency_selectors_no_regression",
                }
            }
        ),
        encoding="utf-8",
    )
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
                    "manager_iterations_total": 30,
                    "manager_tokens_total": 100,
                    "manager_active_seconds_total": 10,
                    "manager_interventions": 1,
                },
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "manager_shutdown.json").write_text(
        json.dumps({"confirmed": True}), encoding="utf-8"
    )
    validation = {
        "required": True,
        "passed": True,
        "mode": "affected_dependency_selectors_no_regression",
        "artifact": artifact.relative_to(tmp_path).as_posix(),
        "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
    }
    record = {
        "status": "accepted",
        "accepted": True,
        "candidate_validation": validation,
    }
    monkeypatch.setattr(
        "protocols.async_manager.results.v1_results.validate",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        "protocols.async_manager.results.v1_results._load_interventions",
        lambda *_args, **_kwargs: [record],
    )

    assert validate(tmp_path, verify_inventory=False) == []

    artifact.write_text('{"passed": false}\n', encoding="utf-8")
    assert "candidate_validation_artifact_checksum_mismatch" in validate(
        tmp_path, verify_inventory=False
    )
    artifact.write_text('{"passed": true}\n', encoding="utf-8")
    record.pop("candidate_validation")
    assert "accepted_candidate_validation_missing_or_failed" in validate(
        tmp_path, verify_inventory=False
    )


def test_historical_profile_does_not_retroactively_require_candidate_gate(
    tmp_path, monkeypatch
):
    (tmp_path / "async_manager_profile_snapshot.json").write_text(
        json.dumps({"active_time_overrun_tolerance_seconds": 30}),
        encoding="utf-8",
    )
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
                    "manager_iterations_total": 30,
                    "manager_tokens_total": 100,
                    "manager_active_seconds_total": 10,
                    "manager_interventions": 1,
                },
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "manager_shutdown.json").write_text(
        json.dumps({"confirmed": True}), encoding="utf-8"
    )
    monkeypatch.setattr(
        "protocols.async_manager.results.v1_results.validate",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        "protocols.async_manager.results.v1_results._load_interventions",
        lambda *_args, **_kwargs: [{"status": "accepted", "accepted": True}],
    )

    assert validate(tmp_path, verify_inventory=False) == []


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
