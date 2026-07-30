from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from anytoolai_platform_core.providers.models import ProviderResponse, ResolvedProviderRequest

_SECRET_KEYS = {
    "api_key",
    "authorization",
    "cookie",
    "credential",
    "password",
    "secret",
    "token",
}
# Matches a secret key only as a whole, delimiter-bounded segment (e.g. "auth_token",
# "user_api_key") so plain substring occurrences like "total_tokens" or
# "prompt_tokens" are left untouched instead of being over-redacted.
_SECRET_KEY_PATTERN = re.compile(
    r"(?:^|[^a-z0-9])(?:"
    + "|".join(re.escape(secret_key) for secret_key in _SECRET_KEYS)
    + r")(?:[^a-z0-9]|$)"
)
_MAX_STRING_LENGTH = 500
_MAX_COLLECTION_ITEMS = 20
_MAX_NESTING_DEPTH = 4


def build_provider_call_metadata(
    request: ResolvedProviderRequest,
    *,
    response: ProviderResponse | None = None,
    error_type: str | None = None,
    error_code: str | None = None,
    error_message_safe: str | None = None,
    failure_kind: str | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "prompt_ref": request.prompt_ref,
        "request_id": request.request_id,
        "correlation_id": request.correlation_id,
        "fixture_key": request.fixture_key,
        "structured_output_mode": request.structured_output_mode.value,
        "temperature": request.temperature,
        "timeout": {"configured_seconds": request.timeout_seconds},
        "retry_policy": {
            "transport": {
                "owner": request.retry_policy.transport.owner,
                "max_attempts": request.retry_policy.transport.max_attempts,
                "litellm_num_retries_per_attempt": request.retry_policy.transport.litellm_num_retries_per_attempt,
            },
            "validation": {
                "owner": request.retry_policy.validation.owner,
                "max_attempts": request.retry_policy.validation.max_attempts,
            },
            "hard_limits": {
                "max_physical_provider_calls_per_action": request.retry_policy.hard_limits.max_physical_provider_calls_per_action,
            },
        },
        "attempts": {
            "semantic_attempt_index": request.semantic_attempt_index,
            "transport_attempt_index": request.transport_attempt_index,
            "physical_call_index": request.physical_call_index,
            "pydantic_run_id": request.pydantic_run_id,
        },
        "fallback_from_policy_ref": request.fallback_from_policy_ref,
        "request_payload": {
            "prompt_chars": len(request.prompt),
            "message_count": len(request.messages),
            "response_schema_present": request.response_schema is not None,
        },
        "request_metadata": sanitize_metadata(request.metadata),
    }
    if request.provider == "litellm":
        metadata["litellm"] = {"model_group": request.model}
    if response is not None:
        metadata["response_metadata"] = sanitize_metadata(response.metadata)
        metadata["response"] = {
            "http_status": response.http_status,
            "litellm_response_id": response.litellm_response_id,
            "total_tokens": response.usage.total_tokens,
        }
        litellm_metadata = response.metadata.get("litellm")
        if request.provider == "litellm" and isinstance(litellm_metadata, Mapping):
            metadata["litellm"] = {
                **metadata.get("litellm", {}),
                **sanitize_metadata(litellm_metadata),
            }
    if error_type is not None or error_message_safe is not None:
        metadata["error"] = {
            "type": error_type,
            "code": error_code,
            "message_safe": error_message_safe,
            "failure_kind": failure_kind,
        }
    return metadata


def sanitize_metadata(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    return {
        str(key): _sanitize_value(key=str(key), value=item, depth=0)
        for key, item in value.items()
    }


def _sanitize_value(*, key: str, value: Any, depth: int) -> Any:
    if _SECRET_KEY_PATTERN.search(key.lower()):
        return "[redacted]"
    if depth >= _MAX_NESTING_DEPTH:
        return "[truncated]"
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        return value[:_MAX_STRING_LENGTH]
    if isinstance(value, Mapping):
        items = list(value.items())[:_MAX_COLLECTION_ITEMS]
        return {
            str(child_key): _sanitize_value(
                key=str(child_key),
                value=child_value,
                depth=depth + 1,
            )
            for child_key, child_value in items
        }
    if isinstance(value, list | tuple):
        items = list(value)[:_MAX_COLLECTION_ITEMS]
        return [
            _sanitize_value(
                key=key,
                value=item,
                depth=depth + 1,
            )
            for item in items
        ]
    return str(value)[:_MAX_STRING_LENGTH]