from __future__ import annotations

from collections.abc import Sequence
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


class _FallbackFakeProviderAdapter(FakeProviderAdapter):
    """Tries each extra fixture root (e.g. a bundle-contributed product's own
    products/<name>/fixtures/ directory) before falling back to FakeProviderAdapter's own shared,
    kernel-level default fixture root. Generic and product-agnostic: knows nothing about any
    specific product or bundle, only about a list of directories a composition boundary passed
    in."""

    def __init__(self, extra_fixture_roots: Sequence[Path]) -> None:
        super().__init__()
        self._extra_fixture_roots = tuple(extra_fixture_roots)

    async def complete(self, request: ResolvedProviderRequest) -> ProviderResponse:
        for root in self._extra_fixture_roots:
            try:
                return await FakeProviderAdapter(root).complete(request)
            except FileNotFoundError:
                continue
        return await super().complete(request)


def build_default_provider_adapters(
    config_root: Path | None = None,
    *,
    extra_fake_fixture_roots: Sequence[Path] = (),
) -> dict[str, ProviderAdapter]:
    """Build production adapters without exposing concrete adapters to composition roots.

    `extra_fake_fixture_roots` lets a composition boundary (e.g. apps/platform-worker) register
    additional directories the `fake` adapter should also search before its own shared,
    kernel-level default -- e.g. a bundle-contributed product's own product-owned fixtures.
    Additive and backward-compatible: every existing caller that doesn't pass it gets the exact
    same `FakeProviderAdapter()` as before.
    """

    fake_adapter: ProviderAdapter = (
        _FallbackFakeProviderAdapter(extra_fake_fixture_roots)
        if extra_fake_fixture_roots
        else FakeProviderAdapter()
    )
    return {
        "fake": fake_adapter,
        "litellm": LazyLiteLLMProviderAdapter(config_root),
    }
