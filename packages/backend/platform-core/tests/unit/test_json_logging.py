from __future__ import annotations

import json
import logging

from anytoolai_platform_core.common.logging import JsonFormatter, REDACTED, sanitize


def test_sanitize_redacts_all_named_sensitive_categories() -> None:
    sensitive = {
        "credentials": "value",
        "authorization": "Bearer abc",
        "cookie": "session=value",
        "access_token": "value",
        "email": "person@example.com",
        "system_prompt": "secret prompt",
        "user_input": "private input",
        "handoff_token": "handoff",
        "raw_provider_output": "provider text",
    }

    assert sanitize(sensitive) == {key: REDACTED for key in sensitive}


def test_json_formatter_emits_parseable_correlation_fields_without_secrets() -> None:
    formatter = JsonFormatter("test-service")
    record = logging.LogRecord(
        "test",
        logging.INFO,
        __file__,
        1,
        "request complete for person@example.com",
        (),
        None,
    )
    record.event = "http.request_completed"
    record.fields = {
        "request_id": "req_123",
        "job_id": "job_123",
        "authorization": "Bearer abc",
    }

    payload = json.loads(formatter.format(record))

    assert payload["event"] == "http.request_completed"
    assert payload["request_id"] == "req_123"
    assert payload["job_id"] == "job_123"
    assert payload["authorization"] == REDACTED
    assert "person@example.com" not in payload["message"]
