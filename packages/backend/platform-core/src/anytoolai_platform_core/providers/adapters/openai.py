from __future__ import annotations

from anytoolai_platform_core.providers.models import (
    ProviderResponse,
    ResolvedProviderRequest,
)


class OpenAIProviderAdapter:
    """Skeleton adapter. Implement real OpenAI client calls here only."""

    async def complete(self, request: ResolvedProviderRequest) -> ProviderResponse:
        del request
        raise NotImplementedError(
            "OpenAI adapter is intentionally not implemented in the current MVP slice"
        )
