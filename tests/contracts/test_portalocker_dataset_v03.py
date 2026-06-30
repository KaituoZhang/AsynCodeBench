from pathlib import Path

from asynccodebench.dataset.models import ExecutionMode
from asynccodebench.dataset.portalocker_v03 import (
    build_annotation_forms,
    build_quality_record,
    build_scenarios,
    build_task_record,
)

CANDIDATE_FILE = Path(
    "manifests/candidates/commit0_public_candidates_v0.2.json"
)


def test_portalocker_is_saved_as_qualification_ready_curated_task() -> None:
    task = build_task_record(CANDIDATE_FILE)
    quality = build_quality_record()

    assert task.task_id == "commit0:portalocker"
    assert task.quality_evidence_file is not None
    assert quality.quality_status.value == "qualification_ready"
    snapshots = {
        snapshot.snapshot_id: snapshot
        for snapshot in quality.evaluation_snapshots
    }
    assert snapshots["raw_commit0_collection"].collected == 0
    assert snapshots["raw_commit0_collection"].return_code == 4
    assert snapshots["curated_commit0_initial"].collected == 40
    assert snapshots["curated_commit0_initial"].passed == 8
    assert snapshots["curated_commit0_initial"].failed == 32
    assert "interface_dependency" in {
        tag.value for tag in quality.coordination_structure_tags
    }


def test_portalocker_draft_scenarios_use_two_natural_specialists() -> None:
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
        "backend_agent",
        "utilities_agent",
    ]


def test_portalocker_annotation_requires_explicit_inclusion_decision() -> None:
    forms = build_annotation_forms(
        candidate_file=CANDIDATE_FILE,
        task_record_file=Path(
            "manifests/pilot/v0.3/tasks/commit0_portalocker.json"
        ),
    )

    assert all(form.include is None for form in forms)
    assert all(
        any(
            "lock/unlock bootstrap" in instruction
            for instruction in form.independence_instructions
        )
        for form in forms
    )
