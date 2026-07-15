from __future__ import annotations

import json
import logging
import re
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any, Mapping

REDACTED = "[REDACTED]"
SENSITIVE_KEY_PARTS = (
    "password",
    "secret",
    "credential",
    "authorization",
    "cookie",
    "token",
    "email",
    "prompt",
    "user_input",
    "input_text",
    "handoff",
    "raw_provider",
    "provider_output",
    "database_url",
)
IDENTIFIER_FIELDS = (
    "request_id",
    "scenario_session_id",
    "job_id",
    "workflow_id",
    "action_run_id",
    "provider_call_id",
)
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_LOG_CONTEXT: ContextVar[dict[str, Any]] = ContextVar("anytoolai_log_context", default={})


def sanitize(value: Any, *, key: str = "") -> Any:
    if _sensitive_key(key):
        return REDACTED
    if isinstance(value, Mapping):
        return {str(item_key): sanitize(item, key=str(item_key)) for item_key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        return _BEARER.sub(REDACTED, _EMAIL.sub(REDACTED, value))
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return sanitize(str(value), key=key)


def _sensitive_key(key: str) -> bool:
    normalized = key.casefold().replace("-", "_")
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def bind_log_context(**fields: Any) -> Token[dict[str, Any]]:
    current = dict(_LOG_CONTEXT.get())
    current.update({key: value for key, value in fields.items() if value is not None})
    return _LOG_CONTEXT.set(current)


def reset_log_context(token: Token[dict[str, Any]]) -> None:
    _LOG_CONTEXT.reset(token)


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        fields = record.__dict__.get("fields", {})
        payload: dict[str, Any] = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "level": record.levelname.lower(),
            "service": self.service,
            "logger": record.name,
            "event": record.__dict__.get("event", record.getMessage()),
            "message": record.getMessage(),
        }
        payload.update(_LOG_CONTEXT.get())
        if isinstance(fields, Mapping):
            payload.update(fields)
        if record.exc_info is not None:
            payload["exception_type"] = record.exc_info[0].__name__
        return json.dumps(sanitize(payload), sort_keys=True, separators=(",", ":"))


def configure_json_logging(service: str) -> None:
    root = logging.getLogger()
    for handler in root.handlers:
        if getattr(handler, "_anytoolai_json_handler", False):
            handler.setFormatter(JsonFormatter(service))
            return
    handler = logging.StreamHandler()
    handler._anytoolai_json_handler = True  # type: ignore[attr-defined]
    handler.setFormatter(JsonFormatter(service))
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    logger.info(event, extra={"event": event, "fields": fields})
