from pathlib import Path

from asyncodebench.dataset.dulwich_v03 import (
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


def test_dulwich_is_saved_as_qualification_ready_task() -> None:
    task = build_task_record(CANDIDATE_FILE)
    quality = build_quality_record()

    assert task.task_id == "commit0:dulwich"
    assert task.quality_evidence_file is not None
    assert quality.quality_status.value == "qualification_ready"
    assert {tag.value for tag in quality.coordination_structure_tags} == {
        "interface_dependency",
        "shared_abstraction",
    }
    snapshots = {
        snapshot.snapshot_id: snapshot
        for snapshot in quality.evaluation_snapshots
    }
    initial = snapshots["commit0_initial_core_subset"]
    assert initial.collected == 540
    assert initial.passed == 526
    assert initial.failed == 2
    assert initial.errors == 0
    assert quality.remaining_gates == (
        "two independent human inclusion/exclusion annotations",
    )
    assert any(
        "Completed-version evaluator sanity is unavailable" in limitation
        for limitation in quality.known_limitations
    )


def test_dulwich_scenarios_use_natural_specialists() -> None:
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
        "config_agent",
        "repo_refs_agent",
        "pack_agent",
        "object_store_agent",
    ]


def test_dulwich_annotation_requires_dependency_metric_review() -> None:
    forms = build_annotation_forms(
        candidate_file=CANDIDATE_FILE,
        task_record_file=Path(
            "manifests/pilot/v0.3/tasks/commit0_dulwich.json"
        ),
    )

    assert all(form.include is None for form in forms)
    assert all(
        any(
            "dependency-metric" in instruction
            for instruction in form.independence_instructions
        )
        for form in forms
    )


def test_dulwich_metric_labels_include_primary_dependency() -> None:
    metrics = build_metric_labels()
    dependency = next(
        item
        for item in metrics["dependency_points"]
        if item["dependency_id"]
        == "dulwich.config_to_repo_refs.default_backend_contract"
    )

    assert dependency["producer_subproblem"] == "config_defaults"
    assert dependency["consumer_subproblem"] == "repo_refs_integration"
    assert {
        "ADPR",
        "DRS",
        "CAIL",
        "SAD",
    }.issubset(set(dependency["metrics_enabled"]))
