from __future__ import annotations

import asyncio
from typing import Any

from anytoolai_platform_core.actions.executor import ActionExecutorResponse
from anytoolai_platform_core.providers.models import ProviderCallStatus, ProviderResponse


class AlwaysFailFakeAdapter:
    async def complete(self, request: Any) -> Any:
        del request
        raise RuntimeError("provider exploded with secret_token=abc123")


class CancelledFakeAdapter:
    async def complete(self, request: Any) -> Any:
        del request
        raise asyncio.CancelledError()


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


class CountingFakeAdapter:
    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate
        self.call_count = 0

    async def complete(self, request: Any) -> Any:
        self.call_count += 1
        return await self._delegate.complete(request)


class InvalidStructuredOutputAdapter:
    async def complete(self, request: Any) -> ProviderResponse:
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            provider=request.provider,
            model=request.model,
            output_text="not-json",
            status=ProviderCallStatus.succeeded,
        )


class EmptyQuestionsFakeAdapter:
    """Simulates a provider reply with no actionable issues: a valid, successful empty
    `questions` array rather than the two-question default fixture."""

    async def complete(self, request: Any) -> ProviderResponse:
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            provider=request.provider,
            model=request.model,
            output_text='{"questions": []}',
            status=ProviderCallStatus.succeeded,
        )


class ComposeReplyOverLimitThenValidAdapter:
    """First reply violates the caller's constraints.max_length cross-validation rule;
    second is compliant."""

    def __init__(self) -> None:
        self.call_count = 0

    async def complete(self, request: Any) -> ProviderResponse:
        self.call_count += 1
        output_text = (
            '{"text": "This reply is far longer than the ten character limit."}'
            if self.call_count == 1
            else '{"text": "Short."}'
        )
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            provider=request.provider,
            model=request.model,
            output_text=output_text,
            status=ProviderCallStatus.succeeded,
        )


class SynthesizeAngleOutOfOptionsThenValidAdapter:
    """First angle violates the caller's options-membership cross-validation rule;
    second is compliant."""

    def __init__(self) -> None:
        self.call_count = 0

    async def complete(self, request: Any) -> ProviderResponse:
        self.call_count += 1
        output_text = (
            '{"angle": "Not one of the offered options", "rationale": "r"}'
            if self.call_count == 1
            else '{"angle": "Lead with urgency", "rationale": "r"}'
        )
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            provider=request.provider,
            model=request.model,
            output_text=output_text,
            status=ProviderCallStatus.succeeded,
        )
