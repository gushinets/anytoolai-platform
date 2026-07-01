from __future__ import annotations

from enum import StrEnum

from anytoolai_platform_sdk.contracts.base import ContractModel


class StructuredOutputMode(StrEnum):
    json_schema = "json_schema"


class ProviderTransportRetryPolicy(ContractModel):
    owner: str = "litellm"
    max_attempts: int = 1
    litellm_num_retries_per_attempt: int = 0


class ProviderValidationRetryPolicy(ContractModel):
    owner: str = "pydanticai"
    max_attempts: int = 1


class ProviderRetryHardLimits(ContractModel):
    max_physical_provider_calls_per_action: int = 1


class ProviderRetryPolicy(ContractModel):
    transport: ProviderTransportRetryPolicy = ProviderTransportRetryPolicy()
    validation: ProviderValidationRetryPolicy = ProviderValidationRetryPolicy()
    hard_limits: ProviderRetryHardLimits = ProviderRetryHardLimits()


class ProviderPolicy(ContractModel):
    provider_policy_ref: str
    provider: str
    model: str
    temperature: float = 0.3
    timeout_seconds: int = 60
    retry_policy: ProviderRetryPolicy = ProviderRetryPolicy()
    fallback_policy: str | None = None
    structured_output_mode: StructuredOutputMode = StructuredOutputMode.json_schema
