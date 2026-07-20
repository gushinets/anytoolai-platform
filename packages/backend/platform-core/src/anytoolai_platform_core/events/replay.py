from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


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
