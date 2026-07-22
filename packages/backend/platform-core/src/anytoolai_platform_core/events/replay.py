from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from anytoolai_platform_core.events.envelope import EventEnvelope

REPLAY_EVENT_ID_PREFIX = "event_replay_"


@dataclass
class ReplayTimestampSequencer:
    """Keep replayed event timestamps in the causal order they are emitted."""

    last_timestamp: datetime | None = None

    def next(self, preferred_timestamp: datetime) -> datetime:
        timestamp = preferred_timestamp
        if self.last_timestamp is not None and timestamp <= self.last_timestamp:
            timestamp = self.last_timestamp + timedelta(microseconds=1)
        self.last_timestamp = timestamp
        return timestamp

    def observe(self, timestamp: datetime) -> None:
        if self.last_timestamp is None or timestamp > self.last_timestamp:
            self.last_timestamp = timestamp


def is_replay_owned_event_id(event_id: str) -> bool:
    return event_id.startswith(REPLAY_EVENT_ID_PREFIX)


def sequence_existing_replay_event(
    event_log_repository: Any,
    timestamp_sequencer: ReplayTimestampSequencer,
    event: EventEnvelope,
) -> EventEnvelope:
    """Advance replay order and repair replay-owned timestamps when they regress."""

    sequenced_timestamp = timestamp_sequencer.next(event.timestamp)
    if sequenced_timestamp == event.timestamp:
        return event
    if not is_replay_owned_event_id(event.event_id):
        return event
    return event_log_repository.update_replay_event_timestamp(
        event.event_id,
        sequenced_timestamp,
    )
