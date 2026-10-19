from __future__ import annotations

import functools
import json
from pathlib import Path

import httpx
import litellm
from anytoolai_platform_core.providers.adapters.litellm import (
    LiteLLMProviderAdapter,
    build_litellm_router,
)
from openai import AsyncOpenAI


def wire_adapter(
    config_root: Path, bodies: list[dict[str, object]], *, status_code: int = 200
) -> LiteLLMProviderAdapter:
    """The real adapter over the real LiteLLM SDK and the shipped router config, with only the HTTP
    transport mocked: every request body LiteLLM puts on the wire is appended to `bodies`, so a
    LiteLLM upgrade that rewrites or drops a parameter fails a test instead of the live provider.
    The router config's `env/OPENAI_API_KEY` must be set by the caller."""

    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        bodies.append(body)
        if status_code != 200:
            return httpx.Response(status_code, json={"error": {"message": "provider error"}})
        return httpx.Response(
            200,
            json={
                "id": "wire-response",
                "object": "chat.completion",
                "created": 1,
                "model": body["model"],
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": '{"ok":true}'},
                    }
                ],
                "usage": {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16},
            },
        )

    client = AsyncOpenAI(
        api_key="test-key",
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)),
    )
    router = build_litellm_router(config_root)
    router.acompletion = functools.partial(router.acompletion, client=client)
    return LiteLLMProviderAdapter(
        router,
        direct_completion=functools.partial(litellm.acompletion, client=client, api_key="test-key"),
    )
