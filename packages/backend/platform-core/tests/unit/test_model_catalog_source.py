from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from anytoolai_platform_core.providers.adapters.litellm import (
    LiteLLMModelCatalogSource,
    parse_litellm_model_metadata_payload,
    parse_openai_models_payload,
)


def test_openai_models_parser_accepts_complete_list_response() -> None:
    payload = json.dumps(
        {
            "object": "list",
            "data": [
                {"id": "gpt-one", "object": "model", "created": 1, "owned_by": "openai"},
                {"id": "gpt-two", "object": "model", "created": 2, "owned_by": "openai"},
            ],
        }
    ).encode()

    assert parse_openai_models_payload(payload) == ("gpt-one", "gpt-two")


@pytest.mark.parametrize(
    "payload",
    [
        b"not json",
        b"{}",
        b'{"object":"list","data":[{"id":1,"object":"model"}]}',
    ],
)
def test_openai_models_parser_rejects_invalid_or_partial_responses(payload: bytes) -> None:
    with pytest.raises(ValueError, match="OpenAI models"):
        parse_openai_models_payload(payload)


def test_litellm_metadata_parser_rejects_invalid_json_and_non_model_entries() -> None:
    with pytest.raises(ValueError, match="LiteLLM metadata"):
        parse_litellm_model_metadata_payload(b"not json")
    with pytest.raises(ValueError, match="LiteLLM metadata"):
        parse_litellm_model_metadata_payload(b'{"gpt-one": []}')
    with pytest.raises(ValueError, match="supports_reasoning"):
        parse_litellm_model_metadata_payload(b'{"gpt-one":{"supports_reasoning":"yes"}}')


def test_litellm_metadata_parser_keeps_valid_model_mapping() -> None:
    payload = json.dumps(
        {
            "gpt-one": {
                "litellm_provider": "openai",
                "mode": "chat",
                "supported_output_modalities": ["text"],
                "reasoning_effort_levels": ["minimal", "low", "medium", "high"],
                "supports_low_reasoning_effort": True,
            }
        }
    ).encode()

    assert parse_litellm_model_metadata_payload(payload)["gpt-one"]["mode"] == "chat"


def test_catalog_source_rejects_oversized_response() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * (32 * 1024 * 1024 + 1))

    source = LiteLLMModelCatalogSource(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ValueError, match="exceeds the size limit"):
        asyncio.run(source.fetch_openai_model_ids())


def test_catalog_source_cancels_underlying_request_at_total_deadline() -> None:
    cancelled = asyncio.Event()

    async def handler(_request: httpx.Request) -> httpx.Response:
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return httpx.Response(200, json={"object": "list", "data": []})

    async def exercise() -> None:
        source = LiteLLMModelCatalogSource(
            api_key="test-key",
            timeout_seconds=0.01,
            transport=httpx.MockTransport(handler),
        )
        with pytest.raises(TimeoutError):
            await source.fetch_openai_model_ids()
        assert cancelled.is_set()

    asyncio.run(exercise())
