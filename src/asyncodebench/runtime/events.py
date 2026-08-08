"""Deterministic causal ordering for benchmark events.

This module deliberately stops at queue semantics.  It does not execute events
or mutate simulator, workspace, job, message, or resource state.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass

from asyncodebench.contracts import EventRecord


class EventQueueError(RuntimeError):
    """Base class for invalid event-queue operations."""


class DuplicateEventError(EventQueueError):
    """Raised when an event identifier is scheduled more than once."""


class CausalOrderError(EventQueueError):
    """Raised when an event has an unknown or non-preceding causal parent."""


class TemporalOrderError(EventQueueError):
    """Raised when an event is scheduled before already-consumed logical time."""


@dataclass(frozen=True)
class ScheduledEvent:
    """Public immutable scheduling metadata paired with a copied event record."""

    event: EventRecord
    priority: int
    sequence: int


@dataclass(frozen=True)
class _SerializedScheduledEvent:
    event_json: str
    priority: int
    sequence: int


@dataclass(frozen=True)
class EventQueueSnapshot:
    """Serialization-safe logical state required for deterministic continuation."""

    pending: tuple[_SerializedScheduledEvent, ...]
    processed: tuple[_SerializedScheduledEvent, ...]
    next_sequence: int
    last_logical_time: float | None


@dataclass(order=True, frozen=True)
class _HeapEntry:
    logical_time: float
    priority: int
    sequence: int
    event_id: str


class DeterministicEventQueue:
    """Stable priority queue with explicit causal validation.

    Ordering is lexicographic by ``(logical_time, priority, insertion_sequence)``.
    Lower integer priorities run first.  The insertion sequence makes equal-time,
    equal-priority ordering stable and reproducible across restore and fork.
    """

    def __init__(self) -> None:
        self._heap: list[_HeapEntry] = []
        self._events: dict[str, ScheduledEvent] = {}
        self._processed: list[ScheduledEvent] = []
        self._next_sequence = 0
        self._last_logical_time: float | None = None

    def __len__(self) -> int:
        return len(self._heap)

    def __bool__(self) -> bool:
        return bool(self._heap)

    @property
    def last_logical_time(self) -> float | None:
        return self._last_logical_time

    def schedule(self, event: EventRecord, *, priority: int = 0) -> ScheduledEvent:
        """Schedule one event after validating identity, time, and causal parents."""

        if event.event_id in self._events:
            raise DuplicateEventError(f"Duplicate event_id: {event.event_id}")
        if (
            self._last_logical_time is not None
            and event.logical_time < self._last_logical_time
        ):
            raise TemporalOrderError(
                f"Event {event.event_id} at {event.logical_time} precedes "
                f"consumed logical time {self._last_logical_time}"
            )

        sequence = self._next_sequence
        key = (event.logical_time, priority, sequence)
        processed_ids = {
            scheduled.event.event_id for scheduled in self._processed
        }
        for parent_id in event.causal_parent_ids:
            try:
                parent = self._events[parent_id]
            except KeyError as exc:
                raise CausalOrderError(
                    f"Unknown causal parent {parent_id!r} for {event.event_id}"
                ) from exc
            if parent_id in processed_ids:
                if parent.event.logical_time > event.logical_time:
                    raise CausalOrderError(
                        f"Causal parent {parent_id!r} occurs after "
                        f"{event.event_id}"
                    )
                continue
            parent_key = (
                parent.event.logical_time,
                parent.priority,
                parent.sequence,
            )
            if parent_key >= key:
                raise CausalOrderError(
                    f"Causal parent {parent_id!r} must precede {event.event_id}"
                )

        scheduled = ScheduledEvent(
            event=event.model_copy(deep=True),
            priority=priority,
            sequence=sequence,
        )
        self._events[event.event_id] = scheduled
        heapq.heappush(
            self._heap,
            _HeapEntry(
                logical_time=event.logical_time,
                priority=priority,
                sequence=sequence,
                event_id=event.event_id,
            ),
        )
        self._next_sequence += 1
        return self._copy_scheduled(scheduled)

    def peek(self) -> ScheduledEvent:
        """Return the next event without consuming it."""

        if not self._heap:
            raise IndexError("peek from an empty event queue")
        return self._copy_scheduled(self._events[self._heap[0].event_id])

    def pop(self) -> ScheduledEvent:
        """Consume and return the next event in deterministic order."""

        if not self._heap:
            raise IndexError("pop from an empty event queue")
        entry = heapq.heappop(self._heap)
        scheduled = self._events[entry.event_id]
        self._processed.append(scheduled)
        self._last_logical_time = scheduled.event.logical_time
        return self._copy_scheduled(scheduled)

    def pending(self) -> tuple[ScheduledEvent, ...]:
        """Return pending events in their future consumption order."""

        return tuple(
            self._copy_scheduled(self._events[entry.event_id])
            for entry in sorted(self._heap)
        )

    def processed(self) -> tuple[ScheduledEvent, ...]:
        """Return consumed events in consumption order."""

        return tuple(self._copy_scheduled(event) for event in self._processed)

    def visible_pending(self, observer_id: str) -> tuple[ScheduledEvent, ...]:
        """Return only pending events explicitly visible to ``observer_id``."""

        return tuple(
            event
            for event in self.pending()
            if observer_id in event.event.visible_to
        )

    def visible_processed(self, observer_id: str) -> tuple[ScheduledEvent, ...]:
        """Return only consumed events explicitly visible to ``observer_id``."""

        return tuple(
            event
            for event in self.processed()
            if observer_id in event.event.visible_to
        )

    def snapshot(self) -> EventQueueSnapshot:
        """Capture an immutable, visibility-preserving continuation snapshot."""

        return EventQueueSnapshot(
            pending=tuple(self._serialize(event) for event in self.pending()),
            processed=tuple(self._serialize(event) for event in self.processed()),
            next_sequence=self._next_sequence,
            last_logical_time=self._last_logical_time,
        )

    @classmethod
    def restore(cls, snapshot: EventQueueSnapshot) -> DeterministicEventQueue:
        """Restore a queue and validate that the snapshot is causally coherent."""

        queue = cls()
        all_states = (*snapshot.processed, *snapshot.pending)
        scheduled = tuple(cls._deserialize(state) for state in all_states)

        event_ids = [item.event.event_id for item in scheduled]
        sequences = [item.sequence for item in scheduled]
        if len(set(event_ids)) != len(event_ids):
            raise DuplicateEventError("Snapshot contains duplicate event IDs")
        if len(set(sequences)) != len(sequences):
            raise EventQueueError("Snapshot contains duplicate insertion sequences")
        if any(sequence < 0 for sequence in sequences):
            raise EventQueueError("Snapshot contains a negative insertion sequence")
        if snapshot.next_sequence < 0 or (
            sequences and snapshot.next_sequence <= max(sequences)
        ):
            raise EventQueueError("Snapshot next_sequence does not follow its events")

        queue._events = {item.event.event_id: item for item in scheduled}
        queue._processed = [
            cls._deserialize(state) for state in snapshot.processed
        ]
        queue._next_sequence = snapshot.next_sequence
        queue._last_logical_time = snapshot.last_logical_time
        queue._heap = [
            _HeapEntry(
                logical_time=item.event.logical_time,
                priority=item.priority,
                sequence=item.sequence,
                event_id=item.event.event_id,
            )
            for item in (cls._deserialize(state) for state in snapshot.pending)
        ]
        heapq.heapify(queue._heap)
        queue._validate_restored_state()
        return queue

    @classmethod
    def from_snapshot(cls, snapshot: EventQueueSnapshot) -> DeterministicEventQueue:
        """Alias for callers that prefer an explicit construction name."""

        return cls.restore(snapshot)

    def fork(self) -> DeterministicEventQueue:
        """Return an independent queue with the same deterministic continuation."""

        return self.restore(self.snapshot())

    def _validate_restored_state(self) -> None:
        processed_ids = {event.event.event_id for event in self._processed}
        pending_ids = {entry.event_id for entry in self._heap}
        if processed_ids & pending_ids:
            raise EventQueueError("Snapshot event is both processed and pending")

        processed_positions = {
            event.event.event_id: position
            for position, event in enumerate(self._processed)
        }
        processed_times = [
            event.event.logical_time for event in self._processed
        ]
        if processed_times != sorted(processed_times):
            raise EventQueueError(
                "Snapshot processed logical times are out of order"
            )
        if self._processed:
            expected_time = self._processed[-1].event.logical_time
            if self._last_logical_time != expected_time:
                raise EventQueueError("Snapshot last_logical_time is inconsistent")
        elif self._last_logical_time is not None:
            raise EventQueueError("Empty history cannot have a last logical time")

        for scheduled in self._events.values():
            child_key = (
                scheduled.event.logical_time,
                scheduled.priority,
                scheduled.sequence,
            )
            for parent_id in scheduled.event.causal_parent_ids:
                try:
                    parent = self._events[parent_id]
                except KeyError as exc:
                    raise CausalOrderError(
                        f"Snapshot event {scheduled.event.event_id} has unknown "
                        f"causal parent {parent_id!r}"
                    ) from exc
                if parent_id in processed_ids:
                    if scheduled.event.event_id in processed_ids:
                        if (
                            processed_positions[parent_id]
                            >= processed_positions[scheduled.event.event_id]
                        ):
                            raise CausalOrderError(
                                f"Snapshot causal parent {parent_id!r} was not "
                                f"processed before {scheduled.event.event_id}"
                            )
                    elif (
                        parent.event.logical_time
                        > scheduled.event.logical_time
                    ):
                        raise CausalOrderError(
                            f"Snapshot causal parent {parent_id!r} occurs after "
                            f"{scheduled.event.event_id}"
                        )
                    continue
                parent_key = (
                    parent.event.logical_time,
                    parent.priority,
                    parent.sequence,
                )
                if parent_key >= child_key:
                    raise CausalOrderError(
                        f"Snapshot causal parent {parent_id!r} does not precede "
                        f"{scheduled.event.event_id}"
                    )
                if scheduled.event.event_id in processed_ids:
                    raise CausalOrderError(
                        f"Processed event {scheduled.event.event_id} has pending "
                        f"causal parent {parent_id!r}"
                    )

        if self._last_logical_time is not None:
            for entry in self._heap:
                if entry.logical_time < self._last_logical_time:
                    raise TemporalOrderError(
                        "Snapshot has pending events before consumed logical time"
                    )

    @staticmethod
    def _copy_scheduled(scheduled: ScheduledEvent) -> ScheduledEvent:
        return ScheduledEvent(
            event=scheduled.event.model_copy(deep=True),
            priority=scheduled.priority,
            sequence=scheduled.sequence,
        )

    @staticmethod
    def _serialize(scheduled: ScheduledEvent) -> _SerializedScheduledEvent:
        return _SerializedScheduledEvent(
            event_json=scheduled.event.model_dump_json(),
            priority=scheduled.priority,
            sequence=scheduled.sequence,
        )

    @staticmethod
    def _deserialize(state: _SerializedScheduledEvent) -> ScheduledEvent:
        return ScheduledEvent(
            event=EventRecord.model_validate_json(state.event_json),
            priority=state.priority,
            sequence=state.sequence,
        )
