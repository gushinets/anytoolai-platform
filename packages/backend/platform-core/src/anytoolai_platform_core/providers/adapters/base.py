from __future__ import annotations

from typing import Protocol

from anytoolai_platform_core.providers.models import (
    ProviderResponse,
    ResolvedProviderRequest,
)


class ProviderAdapter(Protocol):
    async def complete(self, request: ResolvedProviderRequest) -> ProviderResponse: ...
