from __future__ import annotations

from typing import Any

from anytoolai_platform_core.providers.models import ProviderCallStatus, ProviderResponse


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
