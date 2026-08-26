from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any, Mapping

import yaml
from litellm import Router

from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.providers.models import (
    ProviderCallStatus,
    ProviderMessage,
    ProviderResponse,
    ProviderUsage,
    ResolvedProviderRequest,
)
from anytoolai_platform_core.structured_output.schemas import normalize_schema_mapping

_ENV_SENTINEL_PREFIX = "env/"


class LiteLLMProviderAdapter:
    def __init__(self, router: Router) -> None:
        self._router = router

    async def complete(self, request: ResolvedProviderRequest) -> ProviderResponse:
        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": self._messages_for(request),
            "temperature": request.temperature,
            "timeout": float(request.timeout_seconds),
            "num_retries": request.retry_policy.transport.litellm_num_retries_per_attempt,
        }

        response = await self._router.acompletion(**kwargs)
        return _normalize_litellm_response(request, response)

    def _messages_for(self, request: ResolvedProviderRequest) -> list[dict[str, Any]]:
        messages = (
            [_serialize_message(message) for message in request.messages]
            if request.messages
            else [{"role": "user", "content": request.prompt}]
        )
        if request.response_schema is None:
            return messages
        return [_schema_guidance_message(request.response_schema), *messages]


def default_litellm_router_config_path(config_root: Path | None = None) -> Path:
    root = config_root or Path(__file__).resolve().parents[7] / "configs" / "kernel"
    return root / "litellm_router.yaml"


def load_litellm_router_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    if not isinstance(data, dict):
        raise ValueError(f"LiteLLM router config must be a mapping: {path}")

    model_list = data.get("model_list")
    if not isinstance(model_list, list) or not model_list:
        raise ValueError(f"LiteLLM router config requires a non-empty model_list: {path}")

    router_settings = data.get("router_settings", {})
    if not isinstance(router_settings, dict):
        raise ValueError(f"LiteLLM router_settings must be a mapping: {path}")

    return {
        "model_list": _resolve_env_sentinels(model_list),
        "router_settings": _resolve_env_sentinels(router_settings),
    }


def build_litellm_router(config_root: Path | None = None) -> Router:
    config = load_litellm_router_config(default_litellm_router_config_path(config_root))
    router_kwargs = {
        "model_list": config["model_list"],
        **config["router_settings"],
    }
    return Router(**router_kwargs)


def _resolve_env_sentinels(value: Any) -> Any:
    if isinstance(value, str) and value.startswith(_ENV_SENTINEL_PREFIX):
        env_name = value[len(_ENV_SENTINEL_PREFIX) :]
        env_value = os.getenv(env_name)
        if env_value is None or env_value.strip() == "":
            raise PlatformError(
                "provider_router_env_missing",
                f"missing environment variable for LiteLLM router config: {env_name}",
            )
        return env_value
    if isinstance(value, Mapping):
        return {str(key): _resolve_env_sentinels(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_env_sentinels(item) for item in value]
    return value


def _serialize_message(message: ProviderMessage) -> dict[str, Any]:
    return {"role": message.role, "content": message.content}


def _schema_guidance_message(schema: Mapping[str, Any]) -> dict[str, str]:
    normalized_schema = normalize_schema_mapping(schema)
    if normalized_schema is None:  # pragma: no cover - defensive
        raise RuntimeError(
            "LiteLLM schema guidance requires a non-null response schema after normalization"
        )
    schema_json = json.dumps(normalized_schema, sort_keys=True, separators=(",", ":"))
    return {
        "role": "system",
        "content": (
            "Return JSON that matches this schema exactly. "
            "Do not wrap the JSON in markdown fences.\n"
            f"JSON Schema: {schema_json}"
        ),
    }


def _normalize_litellm_response(
    request: ResolvedProviderRequest,
    response: Any,
) -> ProviderResponse:
    usage = _mapping_like(_value_from(response, "usage"))
    hidden_params = _mapping_like(_value_from(response, "_hidden_params"))
    input_tokens = _int_like(
        _value_from(usage, "prompt_tokens") or _value_from(usage, "input_tokens")
    )
    output_tokens = _int_like(
        _value_from(usage, "completion_tokens") or _value_from(usage, "output_tokens")
    )
    # A missing/zero aggregate `total_tokens` doesn't mean no billable usage: the response can
    # report only per-role counts (`code review me #6`). Fall back to input+output so a call that
    # billed tokens is never mistaken for a genuinely free one just because the aggregate field
    # was absent.
    total_tokens = (
        _int_like(_value_from(usage, "total_tokens") or _value_from(usage, "totalTokens"))
        or input_tokens + output_tokens
    )

    def _positive_finite(value: float) -> bool:
        return math.isfinite(value) and value > 0

    primary_cost = _float_like(hidden_params.get("response_cost"), default=math.nan)
    fallback_cost = _float_like(
        _mapping_like(hidden_params.get("additional_headers")).get(
            "llm_provider-x-litellm-response-cost"
        ),
        default=math.nan,
    )
    # A missing/unparseable cost is NaN, not 0.0 (`code review team lead #1`): 0.0 reads
    # downstream (_safe_raw_cost()/_safe_step_cost()) as "known, free", letting a billed call
    # with no cost metadata pass the live-canary cost cap silently. NaN is non-finite, so those
    # same guards already convert it to math.inf and fail the run closed.
    #
    # A *present* but non-positive primary cost is equally untrustworthy when the call actually
    # billed tokens (`code review me #5`): LiteLLM can report a literal 0.0 for an unmapped/
    # custom model it can't price, and treating that as "known free" hid a positive real cost
    # sitting in the fallback header. So: prefer a positive-finite primary cost, then a
    # positive-finite fallback cost (`_positive_finite()`, not a bare `> 0`, so a corrupt `inf`
    # primary never wins over a good finite fallback -- `code review me #6`); only fall back to a
    # real 0.0 when there is no billable usage at all (total_tokens == 0) -- otherwise report NaN
    # (unknown, fail closed).
    if _positive_finite(primary_cost):
        estimated_cost = primary_cost
    elif _positive_finite(fallback_cost):
        estimated_cost = fallback_cost
    elif total_tokens > 0:
        estimated_cost = math.nan
    else:
        estimated_cost = 0.0
    actual_model = _string_like(
        _value_from(response, "model") or hidden_params.get("model")
    )
    actual_provider = _string_like(hidden_params.get("custom_llm_provider"))
    model_id = _string_like(hidden_params.get("model_id"))
    response_id = _string_like(
        _value_from(response, "id") or hidden_params.get("response_id")
    )
    http_status = _int_like(
        hidden_params.get("status_code")
        or hidden_params.get("http_status")
        or _value_from(response, "status_code")
    )
    content = _choice_content(response)

    return ProviderResponse(
        provider_policy_ref=request.provider_policy_ref,
        provider=actual_provider or request.provider,
        model=actual_model or request.model,
        output_text=content,
        status=ProviderCallStatus.succeeded,
        usage=ProviderUsage(input_tokens=input_tokens, output_tokens=output_tokens),
        estimated_cost=estimated_cost,
        http_status=http_status or None,
        litellm_response_id=response_id,
        metadata={
            "litellm": {
                "model_group": request.model,
                "actual_model": actual_model,
                "actual_provider": actual_provider,
                "model_id": model_id,
                "response_id": response_id,
                "http_status": http_status or None,
                "response_cost": estimated_cost if estimated_cost > 0 else None,
            },
            "usage": {"total_tokens": total_tokens},
        },
    )


def _choice_content(response: Any) -> str:
    choices = _value_from(response, "choices")
    if not isinstance(choices, list) or not choices:
        return ""

    message = _value_from(choices[0], "message")
    content = _value_from(message, "content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for item in content:
            text = _value_from(item, "text")
            if isinstance(text, str):
                text_parts.append(text)
        return "".join(text_parts)
    return ""


def _value_from(source: Any, key: str) -> Any:
    if isinstance(source, Mapping):
        return source.get(key)
    return getattr(source, key, None)


def _mapping_like(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        if isinstance(dumped, Mapping):
            return {str(key): item for key, item in dumped.items()}
    return {}


def _int_like(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float_like(value: Any, *, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _string_like(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None
