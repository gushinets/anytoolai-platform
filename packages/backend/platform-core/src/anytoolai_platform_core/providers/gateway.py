from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProviderRequest:
    prompt: str
    model: str
    response_schema: dict | None = None


@dataclass(frozen=True)
class ProviderResponse:
    content: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    estimated_cost: float = 0.0


class ProviderAdapter(Protocol):
    def complete(self, request: ProviderRequest) -> ProviderResponse: ...


class ProviderGateway:
    def __init__(self, adapters: dict[str, ProviderAdapter]) -> None:
        self._adapters = adapters

    def complete(self, provider: str, request: ProviderRequest) -> ProviderResponse:
        adapter = self._adapters[provider]
        return adapter.complete(request)
