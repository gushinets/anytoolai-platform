from __future__ import annotations

from typing import Literal
from enum import StrEnum

from pydantic import Field

from anytoolai_platform_sdk.contracts.base import ContractModel


class StructuredOutputMode(StrEnum):
    json_schema = "json_schema"


class TransportRetryOwner(StrEnum):
    provider_gateway_litellm_sdk = "provider_gateway_litellm_sdk"


class ValidationRetryOwner(StrEnum):
    pydantic_ai = "pydantic_ai"


class ProviderTransportRetryPolicy(ContractModel):
    owner: TransportRetryOwner
    max_attempts: int = Field(ge=1)
    litellm_num_retries_per_attempt: Literal[0] = 0


class ProviderValidationRetryPolicy(ContractModel):
    owner: ValidationRetryOwner
    max_attempts: int = Field(ge=1)


class ProviderRetryHardLimits(ContractModel):
    max_physical_provider_calls_per_action: int = Field(ge=1)


class ProviderRetryPolicy(ContractModel):
    transport: ProviderTransportRetryPolicy
    validation: ProviderValidationRetryPolicy
    hard_limits: ProviderRetryHardLimits


class ProviderPolicy(ContractModel):
    provider_policy_id: str
    provider: str
    model: str
    temperature: float = 0.3
    timeout_seconds: int = 60
    retry_policy: ProviderRetryPolicy
    fallback_policy: str | None = None
    structured_output_mode: StructuredOutputMode = StructuredOutputMode.json_schema
