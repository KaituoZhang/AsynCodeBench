"""Strict v0.3 task, scenario, and annotation records."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from asyncodebench.contracts import ParallelizabilityLabel

DATASET_SCHEMA_VERSION = "0.3"


class DatasetModel(BaseModel):
    """Forbid undeclared fields in released dataset records."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["0.3"] = DATASET_SCHEMA_VERSION


class QualificationStatus(str, Enum):
    PENDING_INDEPENDENT_ANNOTATION = "pending_independent_annotation"
    PENDING_ADJUDICATION = "pending_adjudication"
    FINALIZED = "finalized"


class ExecutionMode(str, Enum):
    ITERATIVE_SINGLE = "iterative_single"
    SERIAL_SPECIALISTS = "serial_specialists"
    ASYNC_PRIVATE = "async_private"
    ASYNC_MESSAGE = "async_message"


class DatasetQualityStatus(str, Enum):
    NEEDS_REVISION = "needs_revision"
    QUALIFICATION_READY = "qualification_ready"
    RELEASE_READY = "release_ready"


class CoordinationStructureTag(str, Enum):
    INTERFACE_DEPENDENCY = "interface_dependency"
    SHARED_ABSTRACTION = "shared_abstraction"
    CONTROL = "control"


class TestGroupPurpose(str, Enum):
    ENVIRONMENT_CONTROL = "environment_control"
    SPECIALIST_LOCAL = "specialist_local"
    CROSS_SUBPROBLEM = "cross_subproblem"
    FULL_EVALUATOR = "full_evaluator"


class DependencyAnnotation(DatasetModel):
    """Publicly justified semantic dependency between natural subproblems."""

    producer_subproblem: str = Field(min_length=1)
    consumer_subproblem: str = Field(min_length=1)
    dependency_type: Literal[
        "import",
        "api_contract",
        "test_contract",
        "integration",
    ]
    description: str = Field(min_length=1)
    evidence_paths: tuple[str, ...] = ()

    @model_validator(mode="after")
    def reject_self_dependency(self) -> DependencyAnnotation:
        if self.producer_subproblem == self.consumer_subproblem:
            raise ValueError("dependency must connect distinct subproblems")
        return self


class AgentAssignment(DatasetModel):
    """One agent role and its natural task ownership."""

    agent_id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    subproblem_id: str = Field(min_length=1)
    writable_paths: tuple[str, ...]
    primary_test_targets: tuple[str, ...]


class TaskRecord(DatasetModel):
    """Frozen upstream task data, independent of agent organization."""

    task_id: str = Field(min_length=1)
    task_source: str = Field(min_length=1)
    upstream_version: str = Field(min_length=1)
    repository: str = Field(min_length=1)
    source_materialization: str = Field(min_length=1)
    problem_statement: str = Field(min_length=1)
    evaluator_command: tuple[str, ...]
    test_targets: tuple[str, ...]
    publicly_implicated_modules: tuple[str, ...]
    natural_subproblems: dict[str, tuple[str, ...]]
    dependency_annotations: tuple[DependencyAnnotation, ...]
    qualification_status: QualificationStatus
    proposed_parallelizability_label: ParallelizabilityLabel | None = None
    qualification_label: ParallelizabilityLabel | None = None
    inclusion_decision: bool | None = None
    annotation_provenance: tuple[str, ...] = ()
    candidate_evidence_file: str = Field(min_length=1)
    quality_evidence_file: str | None = None
    notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_qualification_state(self) -> TaskRecord:
        finalized = self.qualification_status is QualificationStatus.FINALIZED
        if finalized and (
            self.qualification_label is None
            or self.inclusion_decision is None
            or len(self.annotation_provenance) < 2
        ):
            raise ValueError(
                "finalized tasks require a label, inclusion decision, "
                "and at least two annotation provenance records"
            )
        if not finalized and (
            self.qualification_label is not None
            or self.inclusion_decision is not None
        ):
            raise ValueError(
                "pending tasks cannot contain finalized qualification outcomes"
            )
        return self


class TaskTestGroup(DatasetModel):
    """One explicit evaluator slice used for qualification or competence."""

    group_id: str = Field(min_length=1)
    purpose: TestGroupPurpose
    owner_subproblem: str | None = None
    command: tuple[str, ...]
    description: str = Field(min_length=1)
    prerequisites: tuple[str, ...] = ()


class EvaluationSnapshot(DatasetModel):
    """Observed evaluator behavior in a controlled, non-agent workspace."""

    snapshot_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    evidence_scope: Literal[
        "public_initial_state",
        "evaluator_sanity_only",
    ]
    command: tuple[str, ...]
    python_version: str = Field(min_length=1)
    dependency_versions: dict[str, str]
    collected: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    errors: int = Field(ge=0)
    skipped: int = Field(ge=0)
    return_code: int
    duration_seconds: float = Field(gt=0)
    notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_test_accounting(self) -> EvaluationSnapshot:
        accounted = self.passed + self.failed + self.errors + self.skipped
        if accounted != self.collected:
            raise ValueError(
                "passed + failed + errors + skipped must equal collected"
            )
        return self


class TaskQualityRecord(DatasetModel):
    """Release-facing evidence that a generated task is executable and scoped."""

    task_id: str = Field(min_length=1)
    quality_status: DatasetQualityStatus
    coordination_structure_tags: tuple[CoordinationStructureTag, ...] = ()
    structure_rationale: str | None = None
    public_statement_sources: tuple[str, ...]
    environment_requirements: tuple[str, ...]
    test_groups: tuple[TaskTestGroup, ...]
    evaluation_snapshots: tuple[EvaluationSnapshot, ...]
    known_limitations: tuple[str, ...] = ()
    remaining_gates: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_release_ready(self) -> TaskQualityRecord:
        if (
            self.quality_status is DatasetQualityStatus.RELEASE_READY
            and self.remaining_gates
        ):
            raise ValueError("release-ready records cannot have remaining gates")
        return self


class ScenarioRecord(DatasetModel):
    """One execution organization for an unchanged upstream task."""

    scenario_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    execution_mode: ExecutionMode
    agent_count: int = Field(ge=1)
    assignments: tuple[AgentAssignment, ...]
    dependency_annotations: tuple[DependencyAnnotation, ...]
    information_profile: Literal["complete-task", "private-workspace"]
    concurrent_execution: bool
    communication_condition: Literal[
        "not_applicable",
        "completed_artifact_handoff",
        "none_in_flight",
        "structured_message_and_artifact",
    ]
    message_delivery_policy: str = Field(min_length=1)
    integration_policy: str = Field(min_length=1)
    shared_agent_scaffold: Literal["iterative-inspect-edit-test-repair"]
    competence_gate_required: bool = True
    step_budget_per_agent: int = Field(gt=0)
    token_budget_per_agent: int = Field(gt=0)
    test_budget_per_agent: int = Field(gt=0)
    wall_clock_budget_seconds: int = Field(gt=0)
    official_result_eligible: bool = False

    @model_validator(mode="after")
    def validate_execution_shape(self) -> ScenarioRecord:
        if self.agent_count != len(self.assignments):
            raise ValueError("agent_count must equal assignments length")
        async_mode = self.execution_mode in {
            ExecutionMode.ASYNC_PRIVATE,
            ExecutionMode.ASYNC_MESSAGE,
        }
        if self.concurrent_execution != async_mode:
            raise ValueError(
                "concurrent_execution must be true only for async scenarios"
            )
        return self


class AnnotationForm(DatasetModel):
    """Answer-free form assigned to one genuinely independent human."""

    task_id: str = Field(min_length=1)
    annotator_id: str = Field(min_length=1)
    candidate_evidence_file: str = Field(min_length=1)
    task_record_file: str = Field(min_length=1)
    allowed_labels: tuple[ParallelizabilityLabel, ...]
    independence_instructions: tuple[str, ...]
    include: bool | None = None
    parallelizability_label: ParallelizabilityLabel | None = None
    rationale: str | None = None
    exclusion_reason: str | None = None

    @model_validator(mode="after")
    def validate_blank_or_complete(self) -> AnnotationForm:
        decision_fields = (
            self.include,
            self.parallelizability_label,
            self.rationale,
        )
        is_blank = all(value is None for value in decision_fields)
        is_complete = all(value is not None for value in decision_fields)
        if not is_blank and not is_complete:
            raise ValueError("annotation decision must be blank or complete")
        if self.include is True and self.exclusion_reason is not None:
            raise ValueError("included tasks cannot have exclusion_reason")
        if self.include is False and not self.exclusion_reason:
            raise ValueError("excluded tasks require exclusion_reason")
        return self


class AdjudicationForm(DatasetModel):
    """Independent resolution used only when two annotators disagree."""

    task_id: str = Field(min_length=1)
    adjudicator_id: str = Field(min_length=1)
    annotator_ids: tuple[str, str]
    include: bool | None = None
    parallelizability_label: ParallelizabilityLabel | None = None
    rationale: str | None = None
    exclusion_reason: str | None = None

    @model_validator(mode="after")
    def validate_adjudication(self) -> AdjudicationForm:
        if len(set(self.annotator_ids)) != 2:
            raise ValueError("adjudication requires two distinct annotators")
        decision_fields = (
            self.include,
            self.parallelizability_label,
            self.rationale,
        )
        is_blank = all(value is None for value in decision_fields)
        is_complete = all(value is not None for value in decision_fields)
        if not is_blank and not is_complete:
            raise ValueError("adjudication must be blank or complete")
        if self.adjudicator_id in self.annotator_ids:
            raise ValueError("adjudicator must be independent")
        if self.include is True and self.exclusion_reason is not None:
            raise ValueError("included tasks cannot have exclusion_reason")
        if self.include is False and not self.exclusion_reason:
            raise ValueError("excluded tasks require exclusion_reason")
        return self
