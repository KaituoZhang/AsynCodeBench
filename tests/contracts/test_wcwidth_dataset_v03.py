from pathlib import Path

from asynccodebench.dataset.models import ExecutionMode
from asynccodebench.dataset.wcwidth_v03 import (
    build_annotation_forms,
    build_quality_record,
    build_scenarios,
    build_task_record,
)

CANDIDATE_FILE = Path(
    "manifests/candidates/commit0_public_candidates_v0.2.json"
)


def test_wcwidth_is_saved_as_qualification_ready_task() -> None:
    task = build_task_record(CANDIDATE_FILE)
    quality = build_quality_record()

    assert task.task_id == "commit0:wcwidth"
    assert task.quality_evidence_file is not None
    assert quality.quality_status.value == "qualification_ready"
    assert {tag.value for tag in quality.coordination_structure_tags} == {
        "interface_dependency"
    }
    snapshots = {
        snapshot.snapshot_id: snapshot
        for snapshot in quality.evaluation_snapshots
    }
    assert snapshots["commit0_initial_core"].collected == 38
    assert snapshots["commit0_initial_core"].failed == 37
    assert snapshots["commit0_initial_core"].skipped == 1
    assert snapshots["completed_evaluator_sanity_core"].passed == 37
    assert snapshots["completed_evaluator_sanity_core"].return_code == 0


def test_wcwidth_draft_scenarios_use_two_natural_specialists() -> None:
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
        "version_agent",
        "width_agent",
    ]


def test_wcwidth_annotation_requires_explicit_inclusion_decision() -> None:
    forms = build_annotation_forms(
        candidate_file=CANDIDATE_FILE,
        task_record_file=Path(
            "manifests/pilot/v0.3/tasks/commit0_wcwidth.json"
        ),
    )

    assert all(form.include is None for form in forms)
    assert all(
        any(
            "package metadata" in instruction
            for instruction in form.independence_instructions
        )
        for form in forms
    )
