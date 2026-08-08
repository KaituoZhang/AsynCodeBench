from __future__ import annotations

from asyncodebench.contracts import EventRecord, EventType
from asyncodebench.runtime import DeterministicEventQueue, WorkspaceStore


def test_workspace_versions_reference_causal_events() -> None:
    queue = DeterministicEventQueue()
    queue.schedule(
        EventRecord(
            event_id="event-initial",
            logical_time=0.0,
            event_type=EventType.INTEGRATED_BRANCH_UPDATED,
            visible_to=("coder", "reviewer"),
        )
    )
    queue.schedule(
        EventRecord(
            event_id="event-coder-activated",
            logical_time=1.0,
            event_type=EventType.AGENT_ACTIVATED,
            actor="coder",
            causal_parent_ids=("event-initial",),
            visible_to=("coder",),
        )
    )
    queue.schedule(
        EventRecord(
            event_id="event-patch-produced",
            logical_time=2.0,
            event_type=EventType.PATCH_PRODUCED,
            actor="coder",
            causal_parent_ids=("event-coder-activated",),
            visible_to=("coder",),
            payload_reference="artifact-patch",
        )
    )

    workspace = WorkspaceStore(
        {"src/a.py": "x = 1\n"},
        created_by_event_id="event-initial",
    )
    workspace.create_private("coder")
    private = workspace.commit_private(
        "coder",
        {"src/a.py": "x = 2\n"},
        author="coder",
        logical_time=2.0,
        created_by_event_id="event-patch-produced",
        source_artifact_ids=("artifact-patch",),
    )

    restored = DeterministicEventQueue.restore(queue.snapshot())

    assert private.created_by_event_id == "event-patch-produced"
    assert private.source_artifact_ids == ("artifact-patch",)
    assert [item.event.event_id for item in restored.visible_pending("reviewer")] == [
        "event-initial"
    ]
    assert [
        item.event.event_id for item in restored.visible_pending("coder")
    ] == [
        "event-initial",
        "event-coder-activated",
        "event-patch-produced",
    ]
