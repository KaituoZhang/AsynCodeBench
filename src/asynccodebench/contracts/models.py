"""Versioned public contracts for AsyncCodeBench v0.2."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "asynccodebench-v0.2"


class StringEnum(str, Enum):
    """String-valued enum with stable JSON serialization."""


class InformationProfile(StringEnum):
    STRICT_HIDDEN = "strict-hidden"
    SHARED_STATUS = "shared-status"
    MANAGER_MEDIATED = "manager-mediated"


class EventType(StringEnum):
    AGENT_ACTIVATED = "AgentActivated"
    LLM_JOB_STARTED = "LLMJobStarted"
    LLM_JOB_COMPLETED = "LLMJobCompleted"
    TOOL_JOB_STARTED = "ToolJobStarted"
    TOOL_JOB_COMPLETED = "ToolJobCompleted"
    PATCH_PRODUCED = "PatchProduced"
    PATCH_TRANSFERRED = "PatchTransferred"
    MESSAGE_SENT = "MessageSent"
    MESSAGE_DELIVERED = "MessageDelivered"
    MESSAGE_READ = "MessageRead"
    WORKSPACE_UPDATED = "WorkspaceUpdated"
    INTEGRATED_BRANCH_UPDATED = "IntegratedBranchUpdated"
    INTEGRATION_ATTEMPTED = "IntegrationAttempted"
    INTEGRATION_COMPLETED = "IntegrationCompleted"
    REVIEW_STARTED = "ReviewStarted"
    REVIEW_COMPLETED = "ReviewCompleted"
    ARTIFACT_INVALIDATED = "ArtifactInvalidated"
    RESOURCE_ACQUIRED = "ResourceAcquired"
    RESOURCE_RELEASED = "ResourceReleased"
    JOB_CANCELLED = "JobCancelled"
    TIMEOUT = "Timeout"
    SUBMISSION_CREATED = "SubmissionCreated"
    EPISODE_TERMINATED = "EpisodeTerminated"


class OperationType(StringEnum):
    INSPECT = "inspect"
    SEARCH = "search"
    READ = "read"
    EDIT = "edit"
    APPLY_PATCH = "apply_patch"
    RUN_TARGETED_TEST = "run_targeted_test"
    RUN_FULL_TEST = "run_full_test"
    BUILD = "build"
    LAUNCH_EXPERIMENT = "launch_experiment"
    INSPECT_EXPERIMENT = "inspect_experiment"
    REQUEST_STATUS = "request_status"
    REQUEST_ARTIFACT = "request_artifact"
    SEND_MESSAGE = "send_message"
    TRANSFER_ARTIFACT = "transfer_artifact"
    SYNCHRONIZE_WORKSPACE = "synchronize_workspace"
    VERIFY_ARTIFACT = "verify_artifact"
    REVIEW = "review"
    INTEGRATE = "integrate"
    REJECT = "reject"
    DEFER = "defer"
    WAIT = "wait"
    CANCEL_JOB = "cancel_job"
    SUBMIT = "submit"
    TERMINATE = "terminate"


class JobKind(StringEnum):
    LLM = "llm"
    TOOL = "tool"
    TEST = "test"
    BUILD = "build"
    EXPERIMENT = "experiment"
    REVIEW = "review"
    INTEGRATION = "integration"


class JobStatus(StringEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class ArtifactValidity(StringEnum):
    UNKNOWN = "unknown"
    VALID = "valid"
    INVALID = "invalid"
    SUPERSEDED = "superseded"


class ParallelizabilityLabel(StringEnum):
    PARALLELIZABLE = "parallelizable"
    PARTIALLY_PARALLELIZABLE = "partially_parallelizable"
    EFFECTIVELY_SERIAL = "effectively_serial"


class WorkspaceKind(StringEnum):
    INTEGRATED = "integrated"
    PRIVATE = "private"


class ContractModel(BaseModel):
    """Base model shared by strict public contracts."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["asynccodebench-v0.2"] = SCHEMA_VERSION


class EventRecord(ContractModel):
    event_id: str = Field(min_length=1)
    logical_time: float = Field(ge=0.0)
    wall_clock_time_if_live: float | None = Field(default=None, ge=0.0)
    event_type: EventType
    actor: str | None = None
    causal_parent_ids: tuple[str, ...] = ()
    visible_to: tuple[str, ...] = ()
    payload_reference: str | None = None

    @model_validator(mode="after")
    def validate_causal_parents(self) -> EventRecord:
        if self.event_id in self.causal_parent_ids:
            raise ValueError("An event cannot be its own causal parent")
        if len(set(self.causal_parent_ids)) != len(self.causal_parent_ids):
            raise ValueError("causal_parent_ids must be unique")
        return self


class ActionRequest(ContractModel):
    action_id: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    operation: OperationType
    requested_at: float = Field(ge=0.0)
    source_workspace_version: str = Field(min_length=1)
    triggering_event_id: str = Field(min_length=1)
    target_agent_ids: tuple[str, ...] = ()
    input_artifact_ids: tuple[str, ...] = ()
    parameters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_targets(self) -> ActionRequest:
        requires_target = {
            OperationType.REQUEST_STATUS,
            OperationType.REQUEST_ARTIFACT,
            OperationType.SEND_MESSAGE,
            OperationType.TRANSFER_ARTIFACT,
        }
        if self.operation in requires_target and not self.target_agent_ids:
            raise ValueError(f"{self.operation.value} requires a target agent")
        if self.agent_id in self.target_agent_ids:
            raise ValueError("An action cannot target its own actor")
        return self


class MessageProvenance(ContractModel):
    message_id: str = Field(min_length=1)
    sender: str = Field(min_length=1)
    receivers: tuple[str, ...]
    content: str
    source_workspace_version: str = Field(min_length=1)
    source_artifact_ids: tuple[str, ...] = ()
    send_event: str = Field(min_length=1)
    delivery_event: str | None = None
    read_event: str | None = None
    information_profile: InformationProfile

    @model_validator(mode="after")
    def validate_lifecycle(self) -> MessageProvenance:
        if not self.receivers:
            raise ValueError("A message requires at least one receiver")
        if self.sender in self.receivers:
            raise ValueError("A message cannot be sent to its sender")
        if len(set(self.receivers)) != len(self.receivers):
            raise ValueError("Message receivers must be unique")
        if self.read_event is not None and self.delivery_event is None:
            raise ValueError("A message cannot be read before delivery")
        return self


class ArtifactProvenance(ContractModel):
    artifact_id: str = Field(min_length=1)
    artifact_type: str = Field(min_length=1)
    producer: str = Field(min_length=1)
    source_workspace_version: str = Field(min_length=1)
    input_artifact_ids: tuple[str, ...] = ()
    read_set: tuple[str, ...] = ()
    write_set: tuple[str, ...] = ()
    tool_or_command: tuple[str, ...] = ()
    start_event: str = Field(min_length=1)
    finish_event: str | None = None
    delivery_event: str | None = None
    consumer_workspace_version: str | None = None
    validity_status: ArtifactValidity = ArtifactValidity.UNKNOWN
    invalidation_event: str | None = None

    @model_validator(mode="after")
    def validate_validity(self) -> ArtifactProvenance:
        if (
            self.validity_status is ArtifactValidity.INVALID
            and self.invalidation_event is None
        ):
            raise ValueError("Invalid artifacts require an invalidation event")
        return self


class JobRecord(ContractModel):
    job_id: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    kind: JobKind
    status: JobStatus
    input_snapshot_id: str = Field(min_length=1)
    start_event: str = Field(min_length=1)
    finish_event: str | None = None
    output_artifact_ids: tuple[str, ...] = ()
    resource_ids: tuple[str, ...] = ()
    command: tuple[str, ...] = ()
    failure: str | None = None

    @model_validator(mode="after")
    def validate_terminal_state(self) -> JobRecord:
        terminal = {
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
            JobStatus.TIMED_OUT,
        }
        if self.status in terminal and self.finish_event is None:
            raise ValueError("Terminal jobs require a finish event")
        if self.status is JobStatus.FAILED and not self.failure:
            raise ValueError("Failed jobs require failure details")
        return self


class ResourceRecord(ContractModel):
    resource_id: str = Field(min_length=1)
    resource_type: str = Field(min_length=1)
    capacity: float = Field(gt=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FileDeltaRecord(ContractModel):
    path: str = Field(min_length=1)
    change_type: Literal["added", "modified", "deleted"]
    before_digest: str | None = None
    after_digest: str | None = None


class WorkspaceVersionRecord(ContractModel):
    version_id: str = Field(min_length=1)
    content_digest: str = Field(min_length=1)
    parent_version_id: str | None = None
    workspace_kind: WorkspaceKind
    owner: str = Field(min_length=1)
    author: str = Field(min_length=1)
    logical_time: float = Field(ge=0.0)
    changed_paths: tuple[str, ...]
    source_artifact_ids: tuple[str, ...] = ()
    created_by_event_id: str = Field(min_length=1)
    message: str = ""


class WorkspaceStateRecord(ContractModel):
    integrated_version_id: str = Field(min_length=1)
    private_version_ids: dict[str, str]


class CapabilityCard(ContractModel):
    policy_id: str = Field(min_length=1)
    visible_state: tuple[str, ...]
    hidden_state: tuple[str, ...]
    allowed_actions: tuple[OperationType, ...]
    decomposition_input: str
    future_information: Literal["none", "completion_times", "outputs"]
    model_and_tools: dict[str, Any]
    budget: dict[str, float | int]
    runtime_protection: str


class BaselineSemanticCard(ContractModel):
    policy_id: str = Field(min_length=1)
    trigger_conditions: str
    visible_information: tuple[str, ...]
    message_policy: str
    workspace_policy: str
    conflict_policy: str
    invalidation_policy: str
    repair_policy: str
    waiting_policy: str
    integration_policy: str
    resource_policy: str


class QualificationCard(ContractModel):
    task_id: str = Field(min_length=1)
    task_source: str = Field(min_length=1)
    upstream_version: str = Field(min_length=1)
    issue_summary: str
    publicly_implicated_modules: tuple[str, ...]
    public_module_count: int = Field(ge=0)
    dependency_separability: str
    static_dependency_edges: tuple[tuple[str, str], ...]
    test_targets: tuple[str, ...]
    test_target_independence: str
    measured_test_and_build_duration: float = Field(ge=0.0)
    measurement_command: tuple[str, ...]
    measurement_return_code: int | None = None
    measurement_timed_out: bool
    measurement_environment: dict[str, str]
    candidate_parallel_subproblems: tuple[str, ...]
    cross_module_constraints: tuple[str, ...]
    expected_overlap_surface: tuple[str, ...]
    expected_shared_resource_contention: str
    public_evidence_sources: tuple[str, ...]
    parallelizability_label: ParallelizabilityLabel
    annotator_decisions: dict[str, ParallelizabilityLabel]
    adjudication_result: str | None = None
    gold_informed_secondary_label: str | None = None
    exclusion_reason: str | None = None

    @model_validator(mode="after")
    def validate_annotations(self) -> QualificationCard:
        if len(self.annotator_decisions) < 2:
            raise ValueError("Qualification requires at least two annotators")
        distinct = set(self.annotator_decisions.values())
        if len(distinct) > 1 and self.adjudication_result is None:
            raise ValueError("Disagreements require an adjudication result")
        return self
