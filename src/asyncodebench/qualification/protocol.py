"""Merge independent qualification decisions under the v0.2 protocol."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence

from asyncodebench.contracts import QualificationCard
from asyncodebench.qualification.models import (
    AdjudicationDecision,
    AgreementStatistics,
    AnnotatorDecision,
    CandidateRecord,
)


class QualificationProtocolError(ValueError):
    """Raised when qualification evidence violates the frozen protocol."""


def _ordered_pair(
    task_id: str,
    decisions: Sequence[AnnotatorDecision],
) -> tuple[AnnotatorDecision, AnnotatorDecision]:
    if len(decisions) != 2:
        raise QualificationProtocolError(
            f"{task_id}: exactly two annotator decisions are required"
        )
    first, second = sorted(decisions, key=lambda item: item.annotator_id)
    if first.task_id != task_id or second.task_id != task_id:
        raise QualificationProtocolError(
            f"{task_id}: annotator decision references another task"
        )
    if first.annotator_id == second.annotator_id:
        raise QualificationProtocolError(
            f"{task_id}: annotator decisions must be independent"
        )
    return first, second


def _decisions_disagree(
    first: AnnotatorDecision,
    second: AnnotatorDecision,
) -> bool:
    if first.parallelizability_label != second.parallelizability_label:
        return True
    if first.include != second.include:
        return True
    return (
        not first.include
        and first.exclusion_reason != second.exclusion_reason
    )


def merge_qualification(
    candidate: CandidateRecord,
    decisions: Sequence[AnnotatorDecision],
    adjudication: AdjudicationDecision | None = None,
) -> tuple[QualificationCard, bool]:
    """Create one contract card and its final inclusion decision."""

    first, second = _ordered_pair(candidate.task_id, decisions)
    disagreement = _decisions_disagree(first, second)

    if disagreement and adjudication is None:
        raise QualificationProtocolError(
            f"{candidate.task_id}: disagreement requires adjudication"
        )
    if not disagreement and adjudication is not None:
        raise QualificationProtocolError(
            f"{candidate.task_id}: adjudication is only valid for a disagreement"
        )

    if adjudication is not None:
        if adjudication.task_id != candidate.task_id:
            raise QualificationProtocolError(
                f"{candidate.task_id}: adjudication references another task"
            )
        if adjudication.adjudicator_id in {
            first.annotator_id,
            second.annotator_id,
        }:
            raise QualificationProtocolError(
                f"{candidate.task_id}: adjudicator must be independent"
            )
        final_label = adjudication.parallelizability_label
        included = adjudication.include
        exclusion_reason = adjudication.exclusion_reason
        adjudication_result = (
            f"{'include' if included else 'exclude'}:{final_label.value};"
            f"adjudicator={adjudication.adjudicator_id};"
            f"rationale={adjudication.rationale}"
        )
    else:
        final_label = first.parallelizability_label
        included = first.include
        exclusion_reason = first.exclusion_reason
        adjudication_result = None

    card = QualificationCard(
        task_id=candidate.task_id,
        task_source=candidate.task_source,
        upstream_version=candidate.upstream_version,
        issue_summary=candidate.issue_summary,
        publicly_implicated_modules=candidate.publicly_implicated_modules,
        public_module_count=candidate.public_module_count,
        dependency_separability=candidate.dependency_separability,
        static_dependency_edges=candidate.static_dependency_edges,
        test_targets=candidate.test_targets,
        test_target_independence=candidate.test_target_independence,
        measured_test_and_build_duration=(
            candidate.measured_test_and_build_duration
        ),
        measurement_command=candidate.measurement_command,
        measurement_return_code=candidate.measurement_return_code,
        measurement_timed_out=candidate.measurement_timed_out,
        measurement_environment=candidate.measurement_environment,
        candidate_parallel_subproblems=(
            candidate.candidate_parallel_subproblems
        ),
        cross_module_constraints=candidate.cross_module_constraints,
        expected_overlap_surface=candidate.expected_overlap_surface,
        expected_shared_resource_contention=(
            candidate.expected_shared_resource_contention
        ),
        public_evidence_sources=candidate.public_evidence_sources,
        parallelizability_label=final_label,
        annotator_decisions={
            first.annotator_id: first.parallelizability_label,
            second.annotator_id: second.parallelizability_label,
        },
        adjudication_result=adjudication_result,
        gold_informed_secondary_label=(
            candidate.gold_informed_secondary_label
        ),
        exclusion_reason=exclusion_reason,
    )
    return card, included


def _cohen_kappa(
    first_values: Sequence[str],
    second_values: Sequence[str],
) -> float | None:
    if not first_values:
        return None
    observed = sum(
        first == second
        for first, second in zip(first_values, second_values, strict=True)
    ) / len(first_values)
    first_counts = Counter(first_values)
    second_counts = Counter(second_values)
    categories = set(first_counts) | set(second_counts)
    expected = sum(
        (first_counts[category] / len(first_values))
        * (second_counts[category] / len(second_values))
        for category in categories
    )
    if expected == 1.0:
        return 1.0 if observed == 1.0 else None
    return (observed - expected) / (1.0 - expected)


def calculate_agreement(
    decisions_by_task: Iterable[
        tuple[str, Sequence[AnnotatorDecision]]
    ],
) -> AgreementStatistics:
    """Calculate agreement before adjudication in deterministic task order."""

    pairs: list[
        tuple[str, AnnotatorDecision, AnnotatorDecision]
    ] = []
    for task_id, decisions in sorted(decisions_by_task, key=lambda item: item[0]):
        first, second = _ordered_pair(task_id, decisions)
        pairs.append((task_id, first, second))

    task_count = len(pairs)
    label_agreement_count = sum(
        first.parallelizability_label == second.parallelizability_label
        for _, first, second in pairs
    )
    inclusion_agreement_count = sum(
        first.include == second.include for _, first, second in pairs
    )
    exact_agreement_count = sum(
        not _decisions_disagree(first, second)
        for _, first, second in pairs
    )
    denominator = task_count or 1
    first_labels = [
        first.parallelizability_label.value for _, first, _ in pairs
    ]
    second_labels = [
        second.parallelizability_label.value for _, _, second in pairs
    ]
    first_inclusion = [str(first.include) for _, first, _ in pairs]
    second_inclusion = [str(second.include) for _, _, second in pairs]

    return AgreementStatistics(
        task_count=task_count,
        label_agreement_count=label_agreement_count,
        inclusion_agreement_count=inclusion_agreement_count,
        exact_agreement_count=exact_agreement_count,
        label_agreement_rate=label_agreement_count / denominator,
        inclusion_agreement_rate=inclusion_agreement_count / denominator,
        exact_agreement_rate=exact_agreement_count / denominator,
        label_cohen_kappa=_cohen_kappa(first_labels, second_labels),
        inclusion_cohen_kappa=_cohen_kappa(
            first_inclusion,
            second_inclusion,
        ),
        disagreement_task_ids=tuple(
            task_id
            for task_id, first, second in pairs
            if _decisions_disagree(first, second)
        ),
    )
