from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderPolicy:
    provider_policy_id: str
    provider: str
    model: str
    temperature: float = 0.3
    timeout_seconds: int = 60
    max_retries: int = 2
    fallback_policy: str | None = None
    structured_output_mode: str = "json_schema"
