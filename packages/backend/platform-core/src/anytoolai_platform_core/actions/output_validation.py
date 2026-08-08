from __future__ import annotations

from typing import Any, Mapping, Protocol


class ActionOutputCrossValidator(Protocol):
    """Validates an action's structured output against its own input payload.

    Registered per action_type on the structured-LLM executor. Runs inside the
    same PydanticAI validation loop as static schema validation, so a failure
    here gets the same semantic retries and, on exhaustion, fails the run the
    same way a schema mismatch would. Injected as a pluggable per-action_type
    map so the executor itself stays atom-agnostic.
    """

    def validate(
        self,
        *,
        input_payload: Mapping[str, Any],
        output: Mapping[str, Any] | None,
    ) -> None: ...
