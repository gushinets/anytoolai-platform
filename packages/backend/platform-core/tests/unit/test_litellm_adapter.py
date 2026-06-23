from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.providers.adapters.litellm import (
    LiteLLMProviderAdapter,
    build_litellm_router,
    default_litellm_router_config_path,
    load_litellm_router_config,
)
from anytoolai_platform_core.providers.models import (
    ProviderMessage,
    ResolvedProviderRequest,
    StructuredOutputMode,
)


class RecordingRouter:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    async def acompletion(self, model: str, messages: list[dict[str, object]], **kwargs: object) -> object:
        self.calls.append({"model": model, "messages": messages, **kwargs})
        return self.response


def make_request(**overrides: object) -> ResolvedProviderRequest:
    values: dict[str, object] = {
        "provider_policy_id": "default_text_generation_v1",
        "provider": "litellm",
        "model": "anytoolai.default_text",
        "temperature": 0.3,
        "timeout_seconds": 60,
        "max_retries": 2,
        "structured_output_mode": StructuredOutputMode.json_schema,
        "tenant_id": "tenant_demo",
        "region": "eu-central",
        "product_id": "kernel_demo",
        "frontend_id": "kernel_demo_ce",
        "scenario_session_id": "scenario_session_demo",
        "job_id": "job_demo",
        "workflow_id": "workflow_demo",
        "step_id": "step_1",
        "action_run_id": "action_run_demo",
        "action_type": "text.extract_structured_fields",
        "action_config_id": "kernel_demo.extract_structured_fields_v1",
        "prompt": "hello world",
        "messages": (
            ProviderMessage(role="system", content="You are structured"),
            ProviderMessage(role="user", content="Return JSON"),
        ),
    }
    values.update(overrides)
    return ResolvedProviderRequest(**values)


def make_router_response(**overrides: object) -> object:
    hidden_params = {
        "custom_llm_provider": "openai",
        "model_id": "router-deployment-1",
        "response_cost": 0.0001,
    }
    hidden_params.update(overrides.pop("_hidden_params", {}))
    usage = {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16}
    usage.update(overrides.pop("usage", {}))
    values = {
        "choices": [
            {"message": {"content": '{"ok":true}'}},
        ],
        "usage": usage,
        "model": "openai/gpt-4.1-mini",
        "_hidden_params": hidden_params,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_litellm_adapter_maps_messages_to_router_acompletion() -> None:
    router = RecordingRouter(make_router_response())
    adapter = LiteLLMProviderAdapter(router)

    response = asyncio.run(adapter.complete(make_request()))

    assert response.provider == "openai"
    assert response.model == "openai/gpt-4.1-mini"
    assert response.usage.input_tokens == 12
    assert response.usage.output_tokens == 4
    assert response.estimated_cost == pytest.approx(0.0001)
    assert router.calls == [
        {
            "model": "anytoolai.default_text",
            "messages": [
                {"role": "system", "content": "You are structured"},
                {"role": "user", "content": "Return JSON"},
            ],
            "temperature": 0.3,
            "timeout": 60.0,
            "num_retries": 2,
        }
    ]


def test_litellm_adapter_falls_back_to_prompt_as_user_message() -> None:
    router = RecordingRouter(make_router_response())
    adapter = LiteLLMProviderAdapter(router)

    asyncio.run(adapter.complete(make_request(messages=())))

    assert router.calls[0]["messages"] == [{"role": "user", "content": "hello world"}]


def test_litellm_adapter_maps_json_schema_to_response_format() -> None:
    router = RecordingRouter(make_router_response())
    adapter = LiteLLMProviderAdapter(router)

    asyncio.run(
        adapter.complete(
            make_request(
                response_schema={
                    "type": "object",
                    "properties": {"ok": {"type": "boolean"}},
                    "required": ["ok"],
                    "additionalProperties": False,
                }
            )
        )
    )

    response_format = router.calls[0]["response_format"]
    assert response_format == {
        "type": "json_schema",
        "json_schema": {
            "name": "kernel_demo_extract_structured_fields_v1",
            "schema": {
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    }


def test_litellm_adapter_handles_response_content_lists() -> None:
    router = RecordingRouter(
        make_router_response(
            choices=[
                {
                    "message": {
                        "content": [
                            {"type": "output_text", "text": '{"ok":'},
                            {"type": "output_text", "text": "true}"},
                        ]
                    }
                }
            ]
        )
    )
    adapter = LiteLLMProviderAdapter(router)

    response = asyncio.run(adapter.complete(make_request()))

    assert response.output_text == '{"ok":true}'
    assert response.metadata["usage"]["total_tokens"] == 16
    assert response.metadata["litellm"]["model_id"] == "router-deployment-1"


def test_load_litellm_router_config_resolves_env_sentinels(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret-value")
    config_path = tmp_path / "litellm_router.yaml"
    config_path.write_text(
        "\n".join(
            [
                "model_list:",
                "  - model_name: anytoolai.default_text",
                "    litellm_params:",
                "      model: openai/gpt-4.1-mini",
                "      api_key: env/OPENAI_API_KEY",
                "router_settings:",
                "  routing_strategy: simple-shuffle",
            ]
        ),
        encoding="utf-8",
    )

    config = load_litellm_router_config(config_path)

    assert config["model_list"][0]["litellm_params"]["api_key"] == "secret-value"
    assert config["router_settings"]["routing_strategy"] == "simple-shuffle"


def test_load_litellm_router_config_rejects_missing_env_sentinel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config_path = tmp_path / "litellm_router.yaml"
    config_path.write_text(
        "\n".join(
            [
                "model_list:",
                "  - model_name: anytoolai.default_text",
                "    litellm_params:",
                "      model: openai/gpt-4.1-mini",
                "      api_key: env/OPENAI_API_KEY",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(PlatformError) as exc_info:
        load_litellm_router_config(config_path)

    assert exc_info.value.code == "provider_router_env_missing"


def test_build_litellm_router_uses_repo_default_config_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_path = Path(__file__).resolve().parents[5] / "configs" / "kernel" / "litellm_router.yaml"

    monkeypatch.setenv("OPENAI_API_KEY", "secret-value")

    assert default_litellm_router_config_path() == expected_path

    router = build_litellm_router()

    assert router is not None
