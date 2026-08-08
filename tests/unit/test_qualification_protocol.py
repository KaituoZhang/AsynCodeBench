from __future__ import annotations

import pytest
from pydantic import ValidationError

from asyncodebench.contracts import ParallelizabilityLabel
from asyncodebench.qualification import (
    AdjudicationDecision,
    AnnotatorDecision,
    CandidateRecord,
    QualificationProtocolError,
    calculate_agreement,
    merge_qualification,
)


def make_candidate(task_id: str = "commit0:demo") -> CandidateRecord:
    return CandidateRecord(
        task_id=task_id,
        task_source="Commit0",
        upstream_version="abc123",
        issue_summary="Implement two public behaviors.",
        publicly_implicated_modules=("src/a.py", "src/b.py"),
        public_module_count=2,
        dependency_separability="Two modules share one public interface.",
        static_dependency_edges=(("src/b.py", "src/a.py"),),
        test_targets=("tests/test_a.py", "tests/test_b.py"),
        test_target_independence="Targets exercise distinct public behaviors.",
        measured_test_and_build_duration=2.5,
        measurement_command=("python", "-m", "pytest", "-q"),
        measurement_return_code=1,
        measurement_timed_out=False,
        measurement_environment={
            "python_version": "3.10.4",
            "platform": "linux",
        },
        candidate_parallel_subproblems=("behavior-a", "behavior-b"),
        cross_module_constraints=("shared return type",),
        expected_overlap_surface=("implementation-test",),
        expected_shared_resource_contention="Shared pytest worker only.",
        public_evidence_sources=("public issue", "commit0 ref", "test tree"),
    )


def make_decision(
    task_id: str,
    annotator_id: str,
    label: ParallelizabilityLabel,
    *,
    include: bool = True,
    exclusion_reason: str | None = None,
) -> AnnotatorDecision:
    return AnnotatorDecision(
        task_id=task_id,
        annotator_id=annotator_id,
        parallelizability_label=label,
        include=include,
        rationale=f"{annotator_id} reviewed the public evidence.",
        exclusion_reason=exclusion_reason,
    )


def test_candidate_rejects_duplicate_evidence_entries() -> None:
    with pytest.raises(ValidationError, match="test_targets"):
        CandidateRecord(
            **{
                **make_candidate().model_dump(
                    exclude={"protocol_version", "test_targets"}
                ),
                "test_targets": ("tests/test_a.py", "tests/test_a.py"),
            }
        )


def test_candidate_requires_explicit_rubric_measurements() -> None:
    with pytest.raises(ValidationError, match="public_module_count"):
        CandidateRecord(
            **{
                **make_candidate().model_dump(
                    exclude={
                        "protocol_version",
                        "public_module_count",
                    }
                ),
                "public_module_count": 99,
            }
        )


def test_excluded_annotation_requires_reason() -> None:
    with pytest.raises(ValidationError, match="require an exclusion reason"):
        make_decision(
            "commit0:demo",
            "annotator-a",
            ParallelizabilityLabel.EFFECTIVELY_SERIAL,
            include=False,
        )


def test_consensus_builds_card_without_adjudication() -> None:
    candidate = make_candidate()
    decisions = (
        make_decision(
            candidate.task_id,
            "annotator-b",
            ParallelizabilityLabel.PARTIALLY_PARALLELIZABLE,
        ),
        make_decision(
            candidate.task_id,
            "annotator-a",
            ParallelizabilityLabel.PARTIALLY_PARALLELIZABLE,
        ),
    )

    card, included = merge_qualification(candidate, decisions)

    assert included
    assert card.parallelizability_label is (
        ParallelizabilityLabel.PARTIALLY_PARALLELIZABLE
    )
    assert tuple(card.annotator_decisions) == ("annotator-a", "annotator-b")
    assert card.adjudication_result is None


def test_disagreement_requires_independent_adjudication() -> None:
    candidate = make_candidate()
    decisions = (
        make_decision(
            candidate.task_id,
            "annotator-a",
            ParallelizabilityLabel.PARALLELIZABLE,
        ),
        make_decision(
            candidate.task_id,
            "annotator-b",
            ParallelizabilityLabel.PARTIALLY_PARALLELIZABLE,
        ),
    )
    with pytest.raises(
        QualificationProtocolError,
        match="requires adjudication",
    ):
        merge_qualification(candidate, decisions)

    with pytest.raises(
        QualificationProtocolError,
        match="adjudicator must be independent",
    ):
        merge_qualification(
            candidate,
            decisions,
            AdjudicationDecision(
                task_id=candidate.task_id,
                adjudicator_id="annotator-a",
                parallelizability_label=(
                    ParallelizabilityLabel.PARTIALLY_PARALLELIZABLE
                ),
                include=True,
                rationale="Resolved after reviewing both rationales.",
            ),
        )


def test_adjudication_controls_final_label_and_exclusion() -> None:
    candidate = make_candidate()
    decisions = (
        make_decision(
            candidate.task_id,
            "annotator-a",
            ParallelizabilityLabel.PARALLELIZABLE,
        ),
        make_decision(
            candidate.task_id,
            "annotator-b",
            ParallelizabilityLabel.EFFECTIVELY_SERIAL,
            include=False,
            exclusion_reason="No independent executable targets.",
        ),
    )
    adjudication = AdjudicationDecision(
        task_id=candidate.task_id,
        adjudicator_id="adjudicator-c",
        parallelizability_label=ParallelizabilityLabel.EFFECTIVELY_SERIAL,
        include=False,
        rationale="The proposed subproblems cannot be evaluated independently.",
        exclusion_reason="Effectively serial and unsuitable for the pilot.",
    )

    card, included = merge_qualification(
        candidate,
        decisions,
        adjudication,
    )

    assert not included
    assert card.exclusion_reason == (
        "Effectively serial and unsuitable for the pilot."
    )
    assert "adjudicator=adjudicator-c" in (card.adjudication_result or "")


def test_agreement_reports_pre_adjudication_kappa() -> None:
    parallel = ParallelizabilityLabel.PARALLELIZABLE
    partial = ParallelizabilityLabel.PARTIALLY_PARALLELIZABLE
    serial = ParallelizabilityLabel.EFFECTIVELY_SERIAL
    task_decisions = (
        (
            "task-a",
            (
                make_decision("task-a", "ann-1", parallel),
                make_decision("task-a", "ann-2", parallel),
            ),
        ),
        (
            "task-b",
            (
                make_decision("task-b", "ann-1", partial),
                make_decision("task-b", "ann-2", serial),
            ),
        ),
        (
            "task-c",
            (
                make_decision("task-c", "ann-1", serial),
                make_decision("task-c", "ann-2", serial),
            ),
        ),
    )

    statistics = calculate_agreement(task_decisions)

    assert statistics.task_count == 3
    assert statistics.label_agreement_rate == pytest.approx(2 / 3)
    assert statistics.label_cohen_kappa == pytest.approx(0.5)
    assert statistics.inclusion_agreement_rate == 1.0
    assert statistics.inclusion_cohen_kappa == 1.0
    assert statistics.disagreement_task_ids == ("task-b",)
