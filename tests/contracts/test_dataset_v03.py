from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from asyncodebench.dataset.annotation import finalize_task_record
from asyncodebench.dataset.cachetools_v03 import (
    build_adjudication_form,
    build_annotation_forms,
    build_quality_record,
    build_scenarios,
    build_task_record,
)
from asyncodebench.dataset.models import (
    AnnotationForm,
    ExecutionMode,
    QualificationStatus,
    TaskRecord,
)

CANDIDATE_FILE = Path(
    "manifests/candidates/commit0_public_candidates_v0.2.json"
)


def test_cachetools_task_remains_pending_human_annotation() -> None:
    task = build_task_record(CANDIDATE_FILE)

    assert task.qualification_status is (
        QualificationStatus.PENDING_INDEPENDENT_ANNOTATION
    )
    assert task.qualification_label is None
    assert task.inclusion_decision is None
    assert task.problem_statement.startswith(
        "Complete the unfinished public APIs"
    )
    assert task.quality_evidence_file is not None
    assert any(
        dependency.producer_subproblem == "key_construction"
        and dependency.consumer_subproblem == "decorator_factories"
        for dependency in task.dependency_annotations
    )


def test_pending_task_cannot_contain_final_outcome() -> None:
    task = build_task_record(CANDIDATE_FILE)
    payload = task.model_dump()
    payload["qualification_label"] = "partially_parallelizable"

    with pytest.raises(ValidationError, match="pending tasks"):
        TaskRecord.model_validate(payload)


def test_cachetools_has_four_execution_scenarios() -> None:
    scenarios = build_scenarios()

    assert {scenario.execution_mode for scenario in scenarios} == set(
        ExecutionMode
    )
    assert {
        scenario.execution_mode: scenario.concurrent_execution
        for scenario in scenarios
    } == {
        ExecutionMode.ITERATIVE_SINGLE: False,
        ExecutionMode.SERIAL_SPECIALISTS: False,
        ExecutionMode.ASYNC_PRIVATE: True,
        ExecutionMode.ASYNC_MESSAGE: True,
    }
    assert all(
        scenario.shared_agent_scaffold
        == "iterative-inspect-edit-test-repair"
        for scenario in scenarios
    )


def test_cachetools_quality_record_is_qualification_ready() -> None:
    quality = build_quality_record()

    assert quality.quality_status.value == "qualification_ready"
    assert quality.evaluation_snapshots[0].collected == 215
    assert quality.evaluation_snapshots[0].passed == 153
    assert quality.evaluation_snapshots[1].passed == 215
    assert quality.remaining_gates
    local_groups = [
        group
        for group in quality.test_groups
        if group.purpose.value == "specialist_local"
    ]
    assert {group.owner_subproblem for group in local_groups} == {
        "key_construction"
    }
    assert any(
        "no meaningful upstream test slice" in limitation
        for limitation in quality.known_limitations
    )


def test_annotation_forms_are_blank_and_independent() -> None:
    forms = build_annotation_forms(
        candidate_file=CANDIDATE_FILE,
        task_record_file=Path(
            "manifests/pilot/v0.3/tasks/commit0_cachetools.json"
        ),
    )

    assert {form.annotator_id for form in forms} == {
        "annotator_a",
        "annotator_b",
    }
    assert all(form.include is None for form in forms)
    assert all(form.parallelizability_label is None for form in forms)
    assert all(form.rationale is None for form in forms)
    assert all(form.task_id == "asyncodebench:cachetools" for form in forms)
    assert all(form.source_task_id == "commit0:cachetools" for form in forms)


def test_consistent_human_annotations_finalize_task() -> None:
    task = build_task_record(CANDIDATE_FILE)
    common = {
        "task_id": task.task_id,
        "candidate_evidence_file": str(CANDIDATE_FILE),
        "task_record_file": "task.json",
        "allowed_labels": tuple(task.proposed_parallelizability_label.__class__),
        "independence_instructions": ("Work independently.",),
        "include": True,
        "parallelizability_label": "partially_parallelizable",
        "rationale": "Natural key/decorator split with a shared API contract.",
    }
    annotations = (
        AnnotationForm(**common, annotator_id="human_a"),
        AnnotationForm(**common, annotator_id="human_b"),
    )

    finalized = finalize_task_record(task, annotations)

    assert finalized.qualification_status is QualificationStatus.FINALIZED
    assert finalized.inclusion_decision is True
    assert finalized.qualification_label is not None
    assert len(finalized.annotation_provenance) == 2


def test_disagreement_requires_complete_independent_adjudication() -> None:
    task = build_task_record(CANDIDATE_FILE)
    forms = build_annotation_forms(
        candidate_file=CANDIDATE_FILE,
        task_record_file=Path("task.json"),
    )
    first = forms[0].model_copy(
        update={
            "include": True,
            "parallelizability_label": "partially_parallelizable",
            "rationale": "Partially separable.",
        }
    )
    second = forms[1].model_copy(
        update={
            "include": True,
            "parallelizability_label": "parallelizable",
            "rationale": "Subproblems can proceed independently.",
        }
    )

    with pytest.raises(ValueError, match="requires adjudication"):
        finalize_task_record(task, (first, second))

    adjudication = build_adjudication_form().model_copy(
        update={
            "include": True,
            "parallelizability_label": "partially_parallelizable",
            "rationale": "The API contract creates a central bottleneck.",
        }
    )
    finalized = finalize_task_record(task, (first, second), adjudication)
    assert len(finalized.annotation_provenance) == 3
