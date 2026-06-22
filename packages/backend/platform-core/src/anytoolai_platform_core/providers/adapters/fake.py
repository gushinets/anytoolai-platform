from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from anytoolai_platform_core.providers.models import (
    ProviderCallStatus,
    ProviderResponse,
    ProviderUsage,
    ResolvedProviderRequest,
)


class FakeProviderAdapter:
    def __init__(self, fixture_root: Path | None = None) -> None:
        self._fixture_root = fixture_root or self._default_fixture_root()

    async def complete(self, request: ResolvedProviderRequest) -> ProviderResponse:
        fixture_key = self._fixture_key_for(request)
        fixture = self._load_fixture(fixture_key)
        output_text = self._response_text(fixture)

        return ProviderResponse(
            provider_policy_id=request.provider_policy_id,
            provider=request.provider,
            model=request.model,
            output_text=output_text,
            status=ProviderCallStatus.succeeded,
            usage=ProviderUsage(
                input_tokens=int(fixture.get("input_tokens", 0)),
                output_tokens=int(fixture.get("output_tokens", 0)),
            ),
            latency_ms=int(fixture.get("latency_ms", 0)),
            estimated_cost=float(fixture.get("estimated_cost", 0.0)),
            metadata={
                "fixture_key": fixture_key,
                "fixture_metadata": fixture.get("metadata", {}),
            },
        )

    def _fixture_key_for(self, request: ResolvedProviderRequest) -> str:
        metadata_fixture_key = request.metadata.get("fixture_key")
        metadata_action_config_id = request.metadata.get("action_config_id")
        fixture_key = (
            request.fixture_key
            or (metadata_fixture_key if isinstance(metadata_fixture_key, str) else None)
            or request.action_config_id
            or (
                metadata_action_config_id
                if isinstance(metadata_action_config_id, str)
                else None
            )
        )
        if fixture_key is None:
            raise LookupError(
                "fake provider requires fixture_key or action_config_id metadata"
            )
        return fixture_key

    def _load_fixture(self, fixture_key: str) -> dict[str, Any]:
        fixture_path = self._fixture_root / f"{fixture_key}.json"
        if not fixture_path.exists():
            raise FileNotFoundError(f"fake provider fixture not found: {fixture_key}")
        with fixture_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"fake provider fixture must be a JSON object: {fixture_key}")
        return data

    def _response_text(self, fixture: dict[str, Any]) -> str:
        content = fixture.get("output_text")
        if isinstance(content, str):
            return content
        response_json = fixture.get("response_json")
        if response_json is not None:
            return json.dumps(response_json, sort_keys=True)
        raise ValueError(
            "fake provider fixture must define output_text or response_json"
        )

    def _default_fixture_root(self) -> Path:
        for parent in Path(__file__).resolve().parents:
            candidate = (
                parent / "tests" / "fixtures" / "provider" / "fake_provider_outputs"
            )
            if candidate.exists():
                return candidate
        raise FileNotFoundError("unable to locate fake provider fixture root")
