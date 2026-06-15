from __future__ import annotations

from enum import StrEnum

from anytoolai_platform_sdk.contracts.base import ContractModel


class StructuredOutputMode(StrEnum):
    json_schema = "json_schema"


class ProviderPolicy(ContractModel):
    provider_policy_id: str
    provider: str
    model: str
    temperature: float = 0.3
    timeout_seconds: int = 60
    max_retries: int = 2
    fallback_policy: str | None = None
    structured_output_mode: StructuredOutputMode = StructuredOutputMode.json_schema
