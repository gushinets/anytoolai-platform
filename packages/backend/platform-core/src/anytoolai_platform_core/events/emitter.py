from anytoolai_platform_core.events.envelope import EventEnvelope


class EventEmitter:
    def __init__(self) -> None:
        self._events: list[EventEnvelope] = []

    def emit(self, event: EventEnvelope) -> None:
        self._events.append(event)

    @property
    def events(self) -> tuple[EventEnvelope, ...]:
        return tuple(self._events)
