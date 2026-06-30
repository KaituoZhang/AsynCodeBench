from __future__ import annotations

from dataclasses import replace

import pytest

from asynccodebench.contracts import EventRecord, EventType
from asynccodebench.runtime.events import (
    CausalOrderError,
    DeterministicEventQueue,
    DuplicateEventError,
    EventQueueError,
    TemporalOrderError,
)


def event(
    event_id: str,
    logical_time: float,
    *,
    parents: tuple[str, ...] = (),
    visible_to: tuple[str, ...] = (),
) -> EventRecord:
    return EventRecord(
        event_id=event_id,
        logical_time=logical_time,
        event_type=EventType.AGENT_ACTIVATED,
        causal_parent_ids=parents,
        visible_to=visible_to,
    )


def test_orders_by_time_priority_and_stable_insertion_sequence() -> None:
    queue = DeterministicEventQueue()
    queue.schedule(event("late", 2.0))
    queue.schedule(event("equal-first", 1.0), priority=1)
    queue.schedule(event("equal-priority", 1.0), priority=0)
    queue.schedule(event("equal-second", 1.0), priority=1)

    assert [queue.pop().event.event_id for _ in range(4)] == [
        "equal-priority",
        "equal-first",
        "equal-second",
        "late",
    ]


def test_rejects_duplicate_unknown_and_nonpreceding_causal_events() -> None:
    queue = DeterministicEventQueue()
    queue.schedule(event("parent", 1.0), priority=1)

    with pytest.raises(DuplicateEventError):
        queue.schedule(event("parent", 2.0))
    with pytest.raises(CausalOrderError, match="Unknown causal parent"):
        queue.schedule(event("unknown-child", 2.0, parents=("missing",)))
    with pytest.raises(CausalOrderError, match="must precede"):
        queue.schedule(
            event("priority-child", 1.0, parents=("parent",)),
            priority=0,
        )


def test_parent_at_equal_time_precedes_child_by_stable_sequence() -> None:
    queue = DeterministicEventQueue()
    queue.schedule(event("parent", 1.0))
    queue.schedule(event("child", 1.0, parents=("parent",)))

    assert queue.pop().event.event_id == "parent"
    assert queue.pop().event.event_id == "child"


def test_consumed_parent_can_spawn_higher_priority_child_at_same_time() -> None:
    queue = DeterministicEventQueue()
    queue.schedule(event("parent", 1.0), priority=10)
    assert queue.pop().event.event_id == "parent"

    queue.schedule(event("child", 1.0, parents=("parent",)), priority=-10)

    assert queue.pop().event.event_id == "child"


def test_cannot_schedule_into_consumed_logical_past() -> None:
    queue = DeterministicEventQueue()
    queue.schedule(event("now", 2.0))
    queue.pop()

    with pytest.raises(TemporalOrderError):
        queue.schedule(event("past", 1.0))


def test_snapshot_restore_reproduces_continuation_and_visibility() -> None:
    queue = DeterministicEventQueue()
    queue.schedule(event("public-to-a", 1.0, visible_to=("agent-a",)))
    queue.schedule(event("private-to-b", 2.0, visible_to=("agent-b",)))
    queue.schedule(
        event(
            "child-for-a",
            3.0,
            parents=("public-to-a",),
            visible_to=("agent-a",),
        )
    )
    assert queue.pop().event.event_id == "public-to-a"

    restored = DeterministicEventQueue.restore(queue.snapshot())

    assert [item.event.event_id for item in restored.visible_processed("agent-a")] == [
        "public-to-a"
    ]
    assert [item.event.event_id for item in restored.visible_pending("agent-a")] == [
        "child-for-a"
    ]
    assert [item.event.event_id for item in restored.visible_pending("agent-b")] == [
        "private-to-b"
    ]
    assert [queue.pop().event.event_id for _ in range(2)] == [
        restored.pop().event.event_id,
        restored.pop().event.event_id,
    ]


def test_snapshot_is_detached_from_mutable_event_models() -> None:
    queue = DeterministicEventQueue()
    original = event("event", 1.0, visible_to=("agent-a",))
    queue.schedule(original)
    snapshot = queue.snapshot()

    original.visible_to = ("agent-b",)
    popped = DeterministicEventQueue.restore(snapshot).pop()

    assert popped.event.visible_to == ("agent-a",)


def test_fork_has_independent_pending_state_and_preserves_sequence() -> None:
    queue = DeterministicEventQueue()
    queue.schedule(event("first", 1.0))
    branch = queue.fork()

    branch.schedule(event("branch-only", 1.0))

    assert [item.event.event_id for item in queue.pending()] == ["first"]
    assert [item.event.event_id for item in branch.pending()] == [
        "first",
        "branch-only",
    ]
    assert branch.pop().event.event_id == "first"
    assert branch.pop().event.event_id == "branch-only"


def test_restore_rejects_incoherent_snapshot_sequence() -> None:
    queue = DeterministicEventQueue()
    queue.schedule(event("event", 1.0))
    snapshot = queue.snapshot()

    with pytest.raises(EventQueueError, match="next_sequence"):
        DeterministicEventQueue.restore(replace(snapshot, next_sequence=0))
