from pathlib import Path

from asyncodebench.dataset.chardet_v03 import (
    build_annotation_forms,
    build_metric_labels,
    build_quality_record,
    build_scenarios,
    build_task_record,
)
from asyncodebench.dataset.models import ExecutionMode

CANDIDATE_FILE = Path(
    "manifests/candidates/commit0_async_screening_v0.3.json"
)


def test_chardet_is_saved_as_qualification_ready_task() -> None:
    task = build_task_record(CANDIDATE_FILE)
    quality = build_quality_record()

    assert task.task_id == "commit0:chardet"
    assert task.upstream_version == "5539fa54d17ec61bacb4d3bb29ec6fba9dfcb882"
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
    assert initial.collected == 381
    assert initial.passed == 1
    assert initial.failed == 374
    assert initial.skipped == 6

    sanity = snapshots["complete_commit0_evaluator_sanity"]
    assert sanity.collected == 382
    assert sanity.passed == 377
    assert sanity.skipped == 5
    assert sanity.return_code == 0


def test_chardet_scenarios_use_natural_specialists() -> None:
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
        "detector_agent",
        "group_prober_agent",
        "multibyte_agent",
        "singlebyte_unicode_agent",
    ]


def test_chardet_annotation_requires_stripped_ref_review() -> None:
    forms = build_annotation_forms(
        candidate_file=CANDIDATE_FILE,
        task_record_file=Path("manifests/pilot/v0.3/tasks/commit0_chardet.json"),
    )

    assert all(form.include is None for form in forms)
    assert all(
        any(
            "origin/commit0_combined" in instruction
            for instruction in form.independence_instructions
        )
        for form in forms
    )


def test_chardet_metric_labels_include_primary_dependency() -> None:
    metrics = build_metric_labels()
    dependency = next(
        item
        for item in metrics["dependency_points"]
        if item["dependency_id"]
        == "chardet.probers_to_detector.input_state_confidence_contract"
    )

    assert dependency["producer_subproblem"] == "prober_base_and_grouping"
    assert dependency["consumer_subproblem"] == "public_api_and_detector_state"
    assert {"ADPR", "DRS", "CAIL", "SAD"}.issubset(
        set(dependency["metrics_enabled"])
    )
