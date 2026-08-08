from __future__ import annotations

from typing import Any, Mapping, Protocol


class ActionInputValidator(Protocol):
    """Validates an action's input payload before any provider call is made.

    Registered per action_type on `ActionRunner`, runs after static JSON Schema
    validation and before the executor is invoked, so a failure here never
    consumes a provider call or a semantic retry. Reserved for semantic input
    defects the static schema cannot express (for example uniqueness across a
    dynamic array), not for anything an LLM could resolve by retrying.
    """

    def validate(self, *, input_payload: Mapping[str, Any]) -> None: ...
