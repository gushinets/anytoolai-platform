"""Strict V3 boundary validation, independently of storage and provider services."""

import io
import json
from unittest.mock import Mock

import pytest
from anytoolai_platform_api import paid_access
from anytoolai_platform_api.errors import ApiError
from anytoolai_platform_api.paid_access import AccessSnapshotClient
from anytoolai_platform_api.settings import Settings
from anytoolai_platform_core.quotas.models import ExecutionOwner, ExecutionOwnerKind
from pydantic import SecretStr

USER_ID = "00000000-0000-4000-8000-000000000001"


@pytest.mark.parametrize(
    "changes",
    [
        {"schema_version": 2},
        {"schema_version": True},
        {"schema_version": 3.0},
        {"consumer_id": "synthetic-summary"},
        {"consumer_policy_revision": True},
        {"consumer_policy_revision": 0},
        {"region": "us"},
        {"tenant_id": "foreign"},
        {"user_id": "00000000-0000-4000-8000-000000000002"},
        {"grants": [{"product_id": "a", "valid_until": None}]},
    ],
)
def test_snapshot_client_refuses_old_wire_foreign_identity_and_invalid_policy(
    changes: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = {
        "schema_version": 3,
        "consumer_id": "platform-kernel",
        "consumer_policy_revision": 1,
        "tenant_id": "anytoolai",
        "region": "ru",
        "user_id": USER_ID,
        "access_revision": 0,
        "refresh_after": "2026-11-11T04:01:00Z",
        "expires_at": "2026-11-11T04:04:55Z",
        "grants": [],
        "allowances": [],
    } | changes
    response = io.BytesIO(json.dumps(document).encode())
    response.status = 200
    opener = Mock()
    opener.open.return_value = response
    monkeypatch.setattr(paid_access, "build_opener", lambda *args: opener)
    client = AccessSnapshotClient(
        Settings(
            portal_base_url="http://127.0.0.1:8000",
            portal_access_service_token=SecretStr("synthetic-service-" + "s" * 32),
        )
    )
    owner = ExecutionOwner("anytoolai", "ru", ExecutionOwnerKind.portal_user, USER_ID)
    with pytest.raises(ApiError, match="unavailable"):
        client.fetch(owner)
