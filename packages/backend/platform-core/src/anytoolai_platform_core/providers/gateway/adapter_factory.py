from __future__ import annotations

from pathlib import Path

from anytoolai_platform_core.providers.adapters.base import ProviderAdapter
from anytoolai_platform_core.providers.adapters.fake import FakeProviderAdapter
from anytoolai_platform_core.providers.adapters.litellm import (
    LiteLLMProviderAdapter,
    build_litellm_router,
)
from anytoolai_platform_core.providers.models import ProviderResponse, ResolvedProviderRequest


class LazyLiteLLMProviderAdapter:
    """Delay router/env resolution until a LiteLLM-backed job actually runs."""

    def __init__(self, config_root: Path | None = None) -> None:
        self._config_root = config_root
        self._adapter: LiteLLMProviderAdapter | None = None

    async def complete(self, request: ResolvedProviderRequest) -> ProviderResponse:
        if self._adapter is None:
            self._adapter = LiteLLMProviderAdapter(build_litellm_router(self._config_root))
        return await self._adapter.complete(request)


def build_default_provider_adapters(
    config_root: Path | None = None,
) -> dict[str, ProviderAdapter]:
    """Build production adapters without exposing concrete adapters to composition roots."""

    return {
        "fake": FakeProviderAdapter(),
        "litellm": LazyLiteLLMProviderAdapter(config_root),
    }
