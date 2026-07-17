from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import date, datetime
from enum import Enum
import math
from typing import Any
from uuid import UUID

from anytoolai_platform_core.common.ids import new_ordered_id
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.envelope import EventEnvelope
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.events.taxonomy import PLATFORM_EVENTS

MAX_PROPERTY_DEPTH = 5
MAX_PROPERTY_ITEMS = 50
MAX_PROPERTY_STRING_LENGTH = 1024
REDACTED = "[REDACTED]"
UNSUPPORTED = "[UNSUPPORTED]"
TRUNCATED = "[TRUNCATED]"
SENSITIVE_KEY_PARTS = (
    "password",
    "secret",
    "token",
    "authorization",
    "cookie",
    "api_key",
    "apikey",
    "access_key",
    "private_key",
    "credential",
)
SAFE_NUMERIC_USAGE_COUNTER_KEYS = frozenset(
    {
        "input_tokens",
        "output_tokens",
        "total_tokens",
    }
)


class EventValidationError(ValueError):
    """Raised when an event cannot be emitted safely."""


class EventEmitter:
    def __init__(self, repository: EventLogRepository) -> None:
        self._repository = repository

    def emit(
        self,
        event_type: str,
        context: ExecutionContext,
        result_status: str | None = None,
        properties: dict[str, Any] | None = None,
        *,
        timestamp: datetime | None = None,
    ) -> EventEnvelope:
        self._validate_event_type(event_type)
        self._require_dimension(context.tenant_id, "tenant_id")
        self._require_dimension(context.region, "region")

        sanitized_properties = sanitize_event_properties(properties or {})
        error_code = _extract_error_code(sanitized_properties)
        envelope = EventEnvelope(
            event_id=new_ordered_id("event"),
            event_type=event_type,
            timestamp=timestamp or utc_now(),
            tenant_id=context.tenant_id,
            region=context.region,
            product_id=context.product_id,
            frontend_id=context.frontend_id,
            guest_id=context.guest_id,
            user_id=context.user_id,
            scenario_session_id=context.scenario_session_id,
            scenario_chain_id=context.scenario_chain_id,
            job_id=context.job_id,
            workflow_id=context.workflow_id,
            workflow_version=context.workflow_version,
            action_run_id=context.action_run_id,
            action_type=context.action_type,
            action_config_id=context.action_config_id,
            provider_policy_ref=context.provider_policy_ref,
            provider_call_id=context.provider_call_id,
            provider=context.provider,
            model=context.model,
            physical_call_index=context.physical_call_index,
            pydantic_run_id=context.pydantic_run_id,
            litellm_response_id=context.litellm_response_id,
            artifact_id=context.artifact_id,
            handoff_id=context.handoff_id,
            result_status=result_status,
            error_code=error_code,
            acquisition_source=context.acquisition_source,
            properties=sanitized_properties,
        )
        return self._repository.create(envelope)

    @staticmethod
    def _require_dimension(value: str | None, name: str) -> None:
        if value is None or not value.strip():
            raise EventValidationError(f"missing required event dimension: {name}")

    @staticmethod
    def _validate_event_type(event_type: str) -> None:
        if event_type not in PLATFORM_EVENTS:
            raise EventValidationError(f"unknown platform event type: {event_type}")


def enrich_event_context(
    context: ExecutionContext,
    **overrides: str | int | None,
) -> ExecutionContext:
    return replace(context, **overrides)


def sanitize_event_properties(
    properties: dict[str, Any],
    *,
    _depth: int = 0,
) -> dict[str, Any]:
    sanitized = _sanitize_mapping(properties, depth=_depth)
    if not isinstance(sanitized, dict):
        raise EventValidationError("event properties must sanitize to a JSON object")
    return sanitized


def _sanitize_value(value: Any, *, depth: int) -> Any:
    if depth > MAX_PROPERTY_DEPTH:
        return TRUNCATED
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, str):
        return _sanitize_string(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else UNSUPPORTED
    if isinstance(value, (datetime, date, UUID, Enum)):
        return str(value)
    if isinstance(value, Mapping):
        return _sanitize_mapping(value, depth=depth + 1)
    if isinstance(value, (list, tuple, set, frozenset)):
        return _sanitize_sequence(value, depth=depth + 1)
    return UNSUPPORTED


def _sanitize_mapping(value: Mapping[Any, Any], *, depth: int) -> dict[str, Any]:
    items = list(value.items())
    sanitized: dict[str, Any] = {}
    for raw_key, raw_value in items[:MAX_PROPERTY_ITEMS]:
        key = _sanitize_string(str(raw_key))
        if _is_safe_numeric_usage_counter(key, raw_value):
            sanitized[key] = raw_value
            continue
        if _is_sensitive_key(key):
            sanitized[key] = REDACTED
            continue
        sanitized[key] = _sanitize_value(raw_value, depth=depth)
    if len(items) > MAX_PROPERTY_ITEMS:
        sanitized["_truncated_items"] = len(items) - MAX_PROPERTY_ITEMS
    return sanitized


def _sanitize_sequence(values: list[Any] | tuple[Any, ...] | set[Any] | frozenset[Any], *, depth: int) -> list[Any]:
    items = list(values)
    sanitized = [_sanitize_value(item, depth=depth) for item in items[:MAX_PROPERTY_ITEMS]]
    if len(items) > MAX_PROPERTY_ITEMS:
        sanitized.append({"_truncated_items": len(items) - MAX_PROPERTY_ITEMS})
    return sanitized


def _sanitize_string(value: str) -> str:
    if len(value) <= MAX_PROPERTY_STRING_LENGTH:
        return value
    head_length = MAX_PROPERTY_STRING_LENGTH - len(TRUNCATED) - 1
    return f"{value[:head_length]} {TRUNCATED}"


def _is_sensitive_key(key: str) -> bool:
    normalized = key.casefold()
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def _is_safe_numeric_usage_counter(key: str, value: Any) -> bool:
    normalized = key.casefold()
    if normalized not in SAFE_NUMERIC_USAGE_COUNTER_KEYS:
        return False
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    return False


def _extract_error_code(properties: dict[str, Any]) -> str | None:
    error_code = properties.get("error_code")
    return error_code if isinstance(error_code, str) and error_code else None
