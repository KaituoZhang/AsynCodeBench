from __future__ import annotations

from pathlib import Path

from asyncodebench.dataset.deprecated_v03 import (
    build_annotation_forms,
    build_quality_record,
    build_scenarios,
    build_task_record,
)
from asyncodebench.dataset.models import (
    ExecutionMode,
    QualificationStatus,
)

CANDIDATE_FILE = Path(
    "manifests/candidates/commit0_public_candidates_v0.2.json"
)


def test_deprecated_task_preserves_human_qualification_gate() -> None:
    task = build_task_record(CANDIDATE_FILE)

    assert task.task_id == "commit0:deprecated"
    assert task.qualification_status is (
        QualificationStatus.PENDING_INDEPENDENT_ANNOTATION
    )
    assert task.qualification_label is None
    assert task.inclusion_decision is None
    assert task.problem_statement.startswith(
        "Complete the unfinished public APIs"
    )
    assert task.quality_evidence_file is not None
    assert task.natural_subproblems["classic_warning_core"][0] == (
        "deprecated/classic.py"
    )
    assert any(
        dependency.producer_subproblem == "classic_warning_core"
        and dependency.consumer_subproblem == "sphinx_directive_layer"
        for dependency in task.dependency_annotations
    )


def test_deprecated_has_same_four_condition_protocol() -> None:
    scenarios = build_scenarios()

    assert {scenario.execution_mode for scenario in scenarios} == set(
        ExecutionMode
    )
    assert all(
        scenario.shared_agent_scaffold
        == "iterative-inspect-edit-test-repair"
        for scenario in scenarios
    )
    serial = next(
        scenario
        for scenario in scenarios
        if scenario.execution_mode is ExecutionMode.SERIAL_SPECIALISTS
    )
    assert serial.assignments[0].agent_id == "classic_agent"
    assert serial.assignments[1].agent_id == "sphinx_agent"
    classic_tests = serial.assignments[0].primary_test_targets
    sphinx_tests = serial.assignments[1].primary_test_targets
    assert "tests/test_sphinx_metaclass.py" in classic_tests
    assert "tests/test_sphinx_metaclass.py" not in sphinx_tests


def test_deprecated_quality_record_is_qualification_ready() -> None:
    quality = build_quality_record()

    assert quality.quality_status.value == "qualification_ready"
    assert quality.evaluation_snapshots[0].collected == 171
    assert quality.evaluation_snapshots[0].passed == 17
    assert quality.evaluation_snapshots[1].passed == 171
    assert quality.remaining_gates
    local_groups = {
        group.owner_subproblem
        for group in quality.test_groups
        if group.purpose.value == "specialist_local"
    }
    assert local_groups == {
        "classic_warning_core",
        "sphinx_directive_layer",
    }


def test_deprecated_annotation_forms_are_blank() -> None:
    forms = build_annotation_forms(
        candidate_file=CANDIDATE_FILE,
        task_record_file=Path(
            "manifests/pilot/v0.3/tasks/commit0_deprecated.json"
        ),
    )

    assert {form.annotator_id for form in forms} == {
        "annotator_a",
        "annotator_b",
    }
    assert all(form.include is None for form in forms)
    assert all(form.parallelizability_label is None for form in forms)
