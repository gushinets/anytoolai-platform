from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "ProviderAdapter": ("anytoolai_platform_core.providers.adapters.base", "ProviderAdapter"),
    "ProviderGateway": ("anytoolai_platform_core.providers.gateway", "ProviderGateway"),
    "ProviderGatewayExecutionError": (
        "anytoolai_platform_core.providers.gateway",
        "ProviderGatewayExecutionError",
    ),
    "ProviderRequest": ("anytoolai_platform_core.providers.gateway", "ProviderRequest"),
    "ProviderResponse": ("anytoolai_platform_core.providers.gateway", "ProviderResponse"),
    "InternalProviderRequest": (
        "anytoolai_platform_core.providers.models",
        "ProviderRequest",
    ),
    "InternalProviderResponse": (
        "anytoolai_platform_core.providers.models",
        "ProviderResponse",
    ),
    "ProviderCallRecord": ("anytoolai_platform_core.providers.models", "ProviderCallRecord"),
    "ProviderCallStatus": ("anytoolai_platform_core.providers.models", "ProviderCallStatus"),
    "ProviderMessage": ("anytoolai_platform_core.providers.models", "ProviderMessage"),
    "ProviderPolicy": ("anytoolai_platform_core.providers.models", "ProviderPolicy"),
    "ProviderUsage": ("anytoolai_platform_core.providers.models", "ProviderUsage"),
    "ResolvedProviderRequest": (
        "anytoolai_platform_core.providers.models",
        "ResolvedProviderRequest",
    ),
    "StructuredOutputMode": (
        "anytoolai_platform_core.providers.models",
        "StructuredOutputMode",
    ),
    "ProviderPolicyNotFoundError": (
        "anytoolai_platform_core.providers.policies",
        "ProviderPolicyNotFoundError",
    ),
    "ProviderPolicyResolver": (
        "anytoolai_platform_core.providers.policies",
        "ProviderPolicyResolver",
    ),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:  # pragma: no cover - normal Python attribute fallback.
        raise AttributeError(name) from exc
    module = import_module(module_name)
    return getattr(module, attribute_name)
