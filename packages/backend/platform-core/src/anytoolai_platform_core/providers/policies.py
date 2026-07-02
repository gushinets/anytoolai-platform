from __future__ import annotations

from pathlib import Path

from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.providers.models import ProviderPolicy


class ProviderPolicyNotFoundError(LookupError):
    def __init__(self, provider_policy_ref: str) -> None:
        super().__init__(f"provider policy not found: {provider_policy_ref}")
        self.provider_policy_ref = provider_policy_ref


class ProviderPolicyResolver:
    def __init__(self, registry: ConfigRegistry) -> None:
        self._registry = registry

    @classmethod
    def from_config_root(cls, config_root: Path | None = None) -> "ProviderPolicyResolver":
        from anytoolai_platform_core.bootstrap.registry import build_config_registry

        return cls(build_config_registry(config_root))

    def resolve(self, provider_policy_ref: str) -> ProviderPolicy:
        policy = self._registry.get_provider_policy(provider_policy_ref)
        if policy is None:
            raise ProviderPolicyNotFoundError(provider_policy_ref)
        return policy
