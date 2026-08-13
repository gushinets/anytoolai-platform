from __future__ import annotations

from typing import Any

from anytoolai_platform_core.providers.models import ProviderCallStatus, ProviderResponse


class InvalidStructuredOutputAdapter:
    async def complete(self, request: Any) -> ProviderResponse:
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            provider=request.provider,
            model=request.model,
            output_text="not-json",
            status=ProviderCallStatus.succeeded,
        )
