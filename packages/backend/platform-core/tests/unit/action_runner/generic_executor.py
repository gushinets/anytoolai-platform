from __future__ import annotations

from typing import Any

from anytoolai_platform_core.actions.executor import ActionExecutorResponse


class GenericExecutor:
    executor_id = "structured_llm"

    def __init__(self, artifact_id: str = "artifact_generic") -> None:
        self._artifact_id = artifact_id

    async def execute(self, request: Any, *, session: Any) -> ActionExecutorResponse:
        del request, session
        return ActionExecutorResponse(
            structured_output={"title": "Generic Summary", "fields": ["budget"]},
            metadata={"structured_output_artifact_id": self._artifact_id},
        )
