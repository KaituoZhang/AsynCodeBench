from pathlib import Path

from asyncodebench.dataset.models import ExecutionMode
from asyncodebench.dataset.simpy_v03 import (
    build_annotation_forms,
    build_metric_labels,
    build_quality_record,
    build_scenarios,
    build_task_record,
)

CANDIDATE_FILE = Path(
    "manifests/candidates/commit0_async_screening_v0.3.json"
)


def test_simpy_is_saved_as_qualification_ready_task() -> None:
    task = build_task_record(CANDIDATE_FILE)
    quality = build_quality_record()

    assert task.task_id == "commit0:simpy"
    assert task.upstream_version == "25496719af798e5a276289279651873ea5b6e7d1"
    assert "origin/commit0_combined" in task.source_materialization
    assert quality.quality_status.value == "qualification_ready"
    assert {tag.value for tag in quality.coordination_structure_tags} == {
        "interface_dependency",
        "shared_abstraction",
    }
    assert quality.remaining_gates == (
        "two independent human inclusion/exclusion annotations",
    )

    snapshots = {
        snapshot.snapshot_id: snapshot
        for snapshot in quality.evaluation_snapshots
    }
    initial = snapshots["commit0_combined_initial_evaluator"]
    assert initial.collected == 139
    assert initial.passed == 82
    assert initial.failed == 57
    assert initial.errors == 0

    sanity = snapshots["complete_commit0_evaluator_sanity"]
    assert sanity.collected == 139
    assert sanity.passed == 139
    assert sanity.return_code == 0


def test_simpy_scenarios_use_natural_specialists() -> None:
    scenarios = build_scenarios()

    assert {scenario.execution_mode for scenario in scenarios} == set(
        ExecutionMode
    )
    specialists = next(
        scenario
        for scenario in scenarios
        if scenario.execution_mode is ExecutionMode.SERIAL_SPECIALISTS
    )
    assert [assignment.agent_id for assignment in specialists.assignments] == [
        "environment_agent",
        "event_agent",
        "resource_agent",
        "realtime_util_agent",
    ]


def test_simpy_annotation_requires_stripped_ref_review() -> None:
    forms = build_annotation_forms(
        candidate_file=CANDIDATE_FILE,
        task_record_file=Path("manifests/pilot/v0.3/tasks/commit0_simpy.json"),
    )

    assert all(form.include is None for form in forms)
    assert all(
        any(
            "origin/commit0_combined" in instruction
            for instruction in form.independence_instructions
        )
        for form in forms
    )


def test_simpy_metric_labels_include_primary_dependency() -> None:
    metrics = build_metric_labels()
    dependency = next(
        item
        for item in metrics["dependency_points"]
        if item["dependency_id"] == "simpy.environment_to_events.scheduling_contract"
    )

    assert dependency["producer_subproblem"] == "environment_core"
    assert dependency["consumer_subproblem"] == "event_lifecycle"
    assert {"ADPR", "DRS", "CAIL", "SAD"}.issubset(
        set(dependency["metrics_enabled"])
    )
