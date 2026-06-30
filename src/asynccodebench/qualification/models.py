"""Strict input and reporting models for task qualification."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from asynccodebench.contracts import ParallelizabilityLabel

QUALIFICATION_PROTOCOL_VERSION = "qualification-v0.2"


class QualificationModel(BaseModel):
    """Forbid undeclared fields in qualification inputs and outputs."""

    model_config = ConfigDict(extra="forbid")

    protocol_version: Literal["qualification-v0.2"] = (
        QUALIFICATION_PROTOCOL_VERSION
    )


class CandidateRecord(QualificationModel):
    """Agent-independent evidence recorded before outcome evaluation."""

    task_id: str = Field(min_length=1)
    task_source: str = Field(min_length=1)
    upstream_version: str = Field(min_length=1)
    issue_summary: str = Field(min_length=1)
    publicly_implicated_modules: tuple[str, ...]
    public_module_count: int = Field(ge=0)
    dependency_separability: str = Field(min_length=1)
    static_dependency_edges: tuple[tuple[str, str], ...]
    test_targets: tuple[str, ...]
    test_target_independence: str = Field(min_length=1)
    measured_test_and_build_duration: float = Field(ge=0.0)
    measurement_command: tuple[str, ...]
    measurement_return_code: int | None = None
    measurement_timed_out: bool
    measurement_environment: dict[str, str]
    candidate_parallel_subproblems: tuple[str, ...]
    cross_module_constraints: tuple[str, ...]
    expected_overlap_surface: tuple[str, ...]
    expected_shared_resource_contention: str = Field(min_length=1)
    public_evidence_sources: tuple[str, ...]
    gold_informed_secondary_label: str | None = None

    @model_validator(mode="after")
    def validate_unique_evidence(self) -> CandidateRecord:
        sequence_fields = (
            "publicly_implicated_modules",
            "test_targets",
            "candidate_parallel_subproblems",
            "cross_module_constraints",
            "expected_overlap_surface",
            "public_evidence_sources",
        )
        for field_name in sequence_fields:
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} must not contain duplicates")
        if self.public_module_count != len(self.publicly_implicated_modules):
            raise ValueError(
                "public_module_count must equal publicly_implicated_modules"
            )
        if any(
            len(edge) != 2 or edge[0] == edge[1]
            for edge in self.static_dependency_edges
        ):
            raise ValueError("static_dependency_edges must contain directed pairs")
        if len(self.static_dependency_edges) != len(set(self.static_dependency_edges)):
            raise ValueError("static_dependency_edges must not contain duplicates")
        return self


class AnnotatorDecision(QualificationModel):
    """One annotator's decision, stored independently of other decisions."""

    task_id: str = Field(min_length=1)
    annotator_id: str = Field(min_length=1)
    parallelizability_label: ParallelizabilityLabel
    include: bool = True
    rationale: str = Field(min_length=1)
    exclusion_reason: str | None = None

    @model_validator(mode="after")
    def validate_exclusion(self) -> AnnotatorDecision:
        if self.include and self.exclusion_reason is not None:
            raise ValueError("Included decisions cannot have an exclusion reason")
        if not self.include and not self.exclusion_reason:
            raise ValueError("Excluded decisions require an exclusion reason")
        return self


class AdjudicationDecision(QualificationModel):
    """Resolution for a disagreement between the two independent annotators."""

    task_id: str = Field(min_length=1)
    adjudicator_id: str = Field(min_length=1)
    parallelizability_label: ParallelizabilityLabel
    include: bool
    rationale: str = Field(min_length=1)
    exclusion_reason: str | None = None

    @model_validator(mode="after")
    def validate_exclusion(self) -> AdjudicationDecision:
        if self.include and self.exclusion_reason is not None:
            raise ValueError("Included adjudications cannot have an exclusion reason")
        if not self.include and not self.exclusion_reason:
            raise ValueError("Excluded adjudications require an exclusion reason")
        return self


class QualificationBatchInput(QualificationModel):
    """Complete, immutable input to one manifest build."""

    candidates: tuple[CandidateRecord, ...]
    annotator_decisions: tuple[AnnotatorDecision, ...]
    adjudications: tuple[AdjudicationDecision, ...] = ()

    @model_validator(mode="after")
    def validate_identifiers(self) -> QualificationBatchInput:
        candidate_ids = [candidate.task_id for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("Candidate task_id values must be unique")

        adjudication_ids = [
            adjudication.task_id for adjudication in self.adjudications
        ]
        if len(adjudication_ids) != len(set(adjudication_ids)):
            raise ValueError("At most one adjudication is allowed per task")
        return self


class CandidateInventory(QualificationModel):
    """Unlabelled public-evidence candidates prepared for independent review."""

    candidates: tuple[CandidateRecord, ...]

    @model_validator(mode="after")
    def validate_candidate_ids(self) -> CandidateInventory:
        task_ids = [candidate.task_id for candidate in self.candidates]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("Candidate task_id values must be unique")
        return self


class AgreementStatistics(QualificationModel):
    """Pre-adjudication agreement across the two annotators."""

    task_count: int = Field(ge=0)
    label_agreement_count: int = Field(ge=0)
    inclusion_agreement_count: int = Field(ge=0)
    exact_agreement_count: int = Field(ge=0)
    label_agreement_rate: float = Field(ge=0.0, le=1.0)
    inclusion_agreement_rate: float = Field(ge=0.0, le=1.0)
    exact_agreement_rate: float = Field(ge=0.0, le=1.0)
    label_cohen_kappa: float | None = Field(default=None, ge=-1.0, le=1.0)
    inclusion_cohen_kappa: float | None = Field(
        default=None,
        ge=-1.0,
        le=1.0,
    )
    disagreement_task_ids: tuple[str, ...]
