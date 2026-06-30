from pathlib import Path

from asynccodebench.dataset.models import ExecutionMode
from asynccodebench.dataset.tinydb_v03 import (
    build_annotation_forms,
    build_quality_record,
    build_scenarios,
    build_task_record,
)

CANDIDATE_FILE = Path(
    "manifests/candidates/commit0_public_candidates_v0.2.json"
)


def test_tinydb_is_saved_as_qualification_ready_curated_task() -> None:
    task = build_task_record(CANDIDATE_FILE)
    quality = build_quality_record()

    assert task.task_id == "commit0:tinydb"
    assert task.quality_evidence_file is not None
    assert quality.quality_status.value == "qualification_ready"
    snapshots = {
        snapshot.snapshot_id: snapshot
        for snapshot in quality.evaluation_snapshots
    }
    assert snapshots["raw_commit0_collection"].collected == 0
    assert snapshots["raw_commit0_collection"].return_code == 4
    assert snapshots["curated_commit0_initial"].collected == 201
    assert snapshots["curated_commit0_initial"].passed == 5
    assert snapshots["curated_commit0_initial"].return_code == 1
    assert {tag.value for tag in quality.coordination_structure_tags} == {
        "interface_dependency",
        "shared_abstraction",
    }


def test_tinydb_draft_scenarios_use_two_natural_specialists() -> None:
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
        "query_agent",
        "state_agent",
    ]


def test_tinydb_annotation_requires_explicit_inclusion_decision() -> None:
    forms = build_annotation_forms(
        candidate_file=CANDIDATE_FILE,
        task_record_file=Path(
            "manifests/pilot/v0.3/tasks/commit0_tinydb.json"
        ),
    )

    assert all(form.include is None for form in forms)
    assert all(
        any(
            "import bootstrap" in instruction
            for instruction in form.independence_instructions
        )
        for form in forms
    )
