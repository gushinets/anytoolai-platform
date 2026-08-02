from __future__ import annotations

from http import HTTPStatus

from anytoolai_platform_api.routers.scenario_runtime import (
    SAFE_IDEMPOTENCY_KEY_INVALID_422_EXAMPLE,
    _status_code_for_platform_error,
)
from anytoolai_platform_core.scenarios.service import (
    IdempotencyKeyConflictError,
    IdempotencyKeyInvalidError,
)


def test_idempotency_conflict_maps_to_http_conflict() -> None:
    assert _status_code_for_platform_error(IdempotencyKeyConflictError()) == HTTPStatus.CONFLICT


def test_invalid_idempotency_key_openapi_example_matches_runtime_error() -> None:
    error = IdempotencyKeyInvalidError()

    assert SAFE_IDEMPOTENCY_KEY_INVALID_422_EXAMPLE["error"] == {
        "code": error.code,
        "message": str(error),
        "request_id": "req_123",
    }
