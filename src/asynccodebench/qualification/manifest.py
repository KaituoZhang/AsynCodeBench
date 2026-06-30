"""Deterministic qualification manifest construction and serialization."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from asynccodebench.contracts import QualificationCard
from asynccodebench.qualification.models import (
    AdjudicationDecision,
    AgreementStatistics,
    AnnotatorDecision,
    CandidateRecord,
    QualificationBatchInput,
    QualificationModel,
)
from asynccodebench.qualification.protocol import (
    QualificationProtocolError,
    calculate_agreement,
    merge_qualification,
)


class QualificationManifestRecord(QualificationModel):
    candidate: CandidateRecord
    annotator_decisions: tuple[AnnotatorDecision, AnnotatorDecision]
    adjudication: AdjudicationDecision | None = None
    qualification_card: QualificationCard
    included: bool


class QualificationManifest(QualificationModel):
    manifest_type: Literal["pilot-task-qualification"] = (
        "pilot-task-qualification"
    )
    records: tuple[QualificationManifestRecord, ...]
    agreement: AgreementStatistics
    candidate_count: int = Field(ge=0)
    included_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> QualificationManifest:
        if self.candidate_count != len(self.records):
            raise ValueError("candidate_count does not match records")
        actual_included = sum(record.included for record in self.records)
        if self.included_count != actual_included:
            raise ValueError("included_count does not match records")
        if self.excluded_count != len(self.records) - actual_included:
            raise ValueError("excluded_count does not match records")
        return self


def build_manifest(batch: QualificationBatchInput) -> QualificationManifest:
    """Validate a complete batch and return a task-id-sorted manifest."""

    decisions_by_task: dict[str, list[AnnotatorDecision]] = defaultdict(list)
    for decision in batch.annotator_decisions:
        decisions_by_task[decision.task_id].append(decision)
    adjudications_by_task = {
        adjudication.task_id: adjudication
        for adjudication in batch.adjudications
    }
    candidate_ids = {candidate.task_id for candidate in batch.candidates}
    unexpected_decisions = set(decisions_by_task) - candidate_ids
    unexpected_adjudications = set(adjudications_by_task) - candidate_ids
    if unexpected_decisions:
        raise QualificationProtocolError(
            "Decisions reference unknown tasks: "
            + ", ".join(sorted(unexpected_decisions))
        )
    if unexpected_adjudications:
        raise QualificationProtocolError(
            "Adjudications reference unknown tasks: "
            + ", ".join(sorted(unexpected_adjudications))
        )

    records: list[QualificationManifestRecord] = []
    agreement_input: list[
        tuple[str, tuple[AnnotatorDecision, ...]]
    ] = []
    for candidate in sorted(batch.candidates, key=lambda item: item.task_id):
        task_decisions = tuple(decisions_by_task[candidate.task_id])
        agreement_input.append((candidate.task_id, task_decisions))
        card, included = merge_qualification(
            candidate,
            task_decisions,
            adjudications_by_task.get(candidate.task_id),
        )
        ordered_decisions = tuple(
            sorted(task_decisions, key=lambda item: item.annotator_id)
        )
        records.append(
            QualificationManifestRecord(
                candidate=candidate,
                annotator_decisions=ordered_decisions,
                adjudication=adjudications_by_task.get(candidate.task_id),
                qualification_card=card,
                included=included,
            )
        )

    agreement = calculate_agreement(agreement_input)
    included_count = sum(record.included for record in records)
    return QualificationManifest(
        records=tuple(records),
        agreement=agreement,
        candidate_count=len(records),
        included_count=included_count,
        excluded_count=len(records) - included_count,
    )


def write_manifest_json(
    manifest: QualificationManifest,
    output_path: Path,
) -> Path:
    """Write stable, human-readable JSON."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        manifest.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def _json_cell(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def write_manifest_csv(
    manifest: QualificationManifest,
    output_path: Path,
) -> Path:
    """Write one deterministic, analysis-friendly row per candidate."""

    fieldnames = (
        "task_id",
        "task_source",
        "upstream_version",
        "included",
        "parallelizability_label",
        "annotator_ids",
        "annotator_labels",
        "annotator_inclusion",
        "adjudicator_id",
        "adjudication_result",
        "exclusion_reason",
        "publicly_implicated_modules",
        "public_module_count",
        "static_dependency_edges",
        "test_targets",
        "test_target_independence",
        "measured_test_and_build_duration",
        "measurement_command",
        "measurement_return_code",
        "measurement_timed_out",
        "measurement_environment",
        "candidate_parallel_subproblems",
        "cross_module_constraints",
        "expected_overlap_surface",
        "expected_shared_resource_contention",
        "public_evidence_sources",
        "gold_informed_secondary_label",
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for record in manifest.records:
            candidate = record.candidate
            decisions = record.annotator_decisions
            card = record.qualification_card
            writer.writerow(
                {
                    "task_id": candidate.task_id,
                    "task_source": candidate.task_source,
                    "upstream_version": candidate.upstream_version,
                    "included": str(record.included).lower(),
                    "parallelizability_label": (
                        card.parallelizability_label.value
                    ),
                    "annotator_ids": _json_cell(
                        [decision.annotator_id for decision in decisions]
                    ),
                    "annotator_labels": _json_cell(
                        [
                            decision.parallelizability_label.value
                            for decision in decisions
                        ]
                    ),
                    "annotator_inclusion": _json_cell(
                        [decision.include for decision in decisions]
                    ),
                    "adjudicator_id": (
                        record.adjudication.adjudicator_id
                        if record.adjudication
                        else ""
                    ),
                    "adjudication_result": card.adjudication_result or "",
                    "exclusion_reason": card.exclusion_reason or "",
                    "publicly_implicated_modules": _json_cell(
                        candidate.publicly_implicated_modules
                    ),
                    "public_module_count": candidate.public_module_count,
                    "static_dependency_edges": _json_cell(
                        candidate.static_dependency_edges
                    ),
                    "test_targets": _json_cell(candidate.test_targets),
                    "test_target_independence": (
                        candidate.test_target_independence
                    ),
                    "measured_test_and_build_duration": (
                        candidate.measured_test_and_build_duration
                    ),
                    "measurement_command": _json_cell(
                        candidate.measurement_command
                    ),
                    "measurement_return_code": (
                        candidate.measurement_return_code
                        if candidate.measurement_return_code is not None
                        else ""
                    ),
                    "measurement_timed_out": str(
                        candidate.measurement_timed_out
                    ).lower(),
                    "measurement_environment": _json_cell(
                        candidate.measurement_environment
                    ),
                    "candidate_parallel_subproblems": _json_cell(
                        candidate.candidate_parallel_subproblems
                    ),
                    "cross_module_constraints": _json_cell(
                        candidate.cross_module_constraints
                    ),
                    "expected_overlap_surface": _json_cell(
                        candidate.expected_overlap_surface
                    ),
                    "expected_shared_resource_contention": (
                        candidate.expected_shared_resource_contention
                    ),
                    "public_evidence_sources": _json_cell(
                        candidate.public_evidence_sources
                    ),
                    "gold_informed_secondary_label": (
                        candidate.gold_informed_secondary_label or ""
                    ),
                }
            )
    return output_path
