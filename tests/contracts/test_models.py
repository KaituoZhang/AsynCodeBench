from __future__ import annotations

import pytest
from pydantic import ValidationError

from asyncodebench.contracts import (
    SCHEMA_VERSION,
    ActionRequest,
    ArtifactProvenance,
    ArtifactValidity,
    EventRecord,
    EventType,
    InformationProfile,
    JobKind,
    JobRecord,
    JobStatus,
    MessageProvenance,
    OperationType,
    ParallelizabilityLabel,
    QualificationCard,
)


def test_event_vocabulary_matches_specification_v02() -> None:
    assert {event.value for event in EventType} == {
        "AgentActivated",
        "LLMJobStarted",
        "LLMJobCompleted",
        "ToolJobStarted",
        "ToolJobCompleted",
        "PatchProduced",
        "PatchTransferred",
        "MessageSent",
        "MessageDelivered",
        "MessageRead",
        "WorkspaceUpdated",
        "IntegratedBranchUpdated",
        "IntegrationAttempted",
        "IntegrationCompleted",
        "ReviewStarted",
        "ReviewCompleted",
        "ArtifactInvalidated",
        "ResourceAcquired",
        "ResourceReleased",
        "JobCancelled",
        "Timeout",
        "SubmissionCreated",
        "EpisodeTerminated",
    }


def test_event_rejects_self_causation() -> None:
    with pytest.raises(ValidationError, match="own causal parent"):
        EventRecord(
            event_id="event-1",
            logical_time=0.0,
            event_type=EventType.AGENT_ACTIVATED,
            causal_parent_ids=("event-1",),
        )


def test_actions_are_concrete_operations() -> None:
    action = ActionRequest(
        action_id="action-1",
        agent_id="coder",
        operation=OperationType.RUN_TARGETED_TEST,
        requested_at=1.0,
        source_workspace_version="workspace-1",
        triggering_event_id="event-1",
        parameters={"target": "tests/test_keys.py"},
    )
    assert action.schema_version == SCHEMA_VERSION
    assert action.operation is OperationType.RUN_TARGETED_TEST

    with pytest.raises(ValidationError, match="requires a target agent"):
        ActionRequest(
            action_id="action-2",
            agent_id="coder",
            operation=OperationType.SEND_MESSAGE,
            requested_at=1.0,
            source_workspace_version="workspace-1",
            triggering_event_id="event-1",
        )


def test_message_lifecycle_requires_delivery_before_read() -> None:
    with pytest.raises(ValidationError, match="before delivery"):
        MessageProvenance(
            message_id="message-1",
            sender="coder",
            receivers=("reviewer",),
            content="Please review artifact-1",
            source_workspace_version="workspace-1",
            source_artifact_ids=("artifact-1",),
            send_event="event-send",
            read_event="event-read",
            information_profile=InformationProfile.STRICT_HIDDEN,
        )


def test_invalid_artifact_requires_invalidation_event() -> None:
    with pytest.raises(ValidationError, match="invalidation event"):
        ArtifactProvenance(
            artifact_id="artifact-1",
            artifact_type="patch",
            producer="coder",
            source_workspace_version="workspace-1",
            start_event="event-start",
            validity_status=ArtifactValidity.INVALID,
        )


def test_terminal_job_requires_finish_event() -> None:
    with pytest.raises(ValidationError, match="finish event"):
        JobRecord(
            job_id="job-1",
            owner="tester",
            kind=JobKind.TEST,
            status=JobStatus.COMPLETED,
            input_snapshot_id="snapshot-1",
            start_event="event-start",
        )


def test_qualification_requires_independent_annotation_and_adjudication() -> None:
    common = {
        "task_id": "commit0:cachetools",
        "task_source": "Commit0",
        "upstream_version": "abc123",
        "issue_summary": "Implement missing cache key behavior.",
        "publicly_implicated_modules": ("cachetools.keys", "cachetools.func"),
        "public_module_count": 2,
        "dependency_separability": "partially separable",
        "static_dependency_edges": (("cachetools.func", "cachetools.keys"),),
        "test_targets": ("tests/test_keys.py", "tests/test_func.py"),
        "test_target_independence": "Two separately executable test modules.",
        "measured_test_and_build_duration": 1.0,
        "measurement_command": ("python", "-m", "pytest", "-q"),
        "measurement_return_code": 1,
        "measurement_timed_out": False,
        "measurement_environment": {
            "python_version": "3.10.4",
            "platform": "linux",
        },
        "candidate_parallel_subproblems": ("keys", "decorators"),
        "cross_module_constraints": ("key contract",),
        "expected_overlap_surface": ("implementation-test",),
        "expected_shared_resource_contention": "Shared pytest worker.",
        "public_evidence_sources": ("public issue", "commit0 ref"),
        "parallelizability_label": (
            ParallelizabilityLabel.PARTIALLY_PARALLELIZABLE
        ),
    }

    with pytest.raises(ValidationError, match="at least two annotators"):
        QualificationCard(
            **common,
            annotator_decisions={
                "annotator-a": ParallelizabilityLabel.PARTIALLY_PARALLELIZABLE
            },
        )

    with pytest.raises(ValidationError, match="adjudication"):
        QualificationCard(
            **common,
            annotator_decisions={
                "annotator-a": ParallelizabilityLabel.PARTIALLY_PARALLELIZABLE,
                "annotator-b": ParallelizabilityLabel.PARALLELIZABLE,
            },
        )

    card = QualificationCard(
        **common,
        annotator_decisions={
            "annotator-a": ParallelizabilityLabel.PARTIALLY_PARALLELIZABLE,
            "annotator-b": ParallelizabilityLabel.PARALLELIZABLE,
        },
        adjudication_result="partially_parallelizable",
    )
    assert card.parallelizability_label is (
        ParallelizabilityLabel.PARTIALLY_PARALLELIZABLE
    )
