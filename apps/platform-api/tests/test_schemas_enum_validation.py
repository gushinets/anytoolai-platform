from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from anytoolai_platform_api.routers.identity_quota import _quota_state_payload
from anytoolai_platform_api.schemas import (
    ClientEventResponse,
    HandoffCreateResponse,
    HandoffPreviewResponse,
    QuotaStateResponse,
    RuntimeFrontendResponse,
    RuntimeQuotaSummaryResponse,
    ScenarioSessionResponse,
    ScenarioStartResponse,
)
from anytoolai_platform_core.quotas.models import (
    QuotaDimension,
    QuotaPeriod,
    QuotaState,
    QuotaUnit,
)

_EXPIRES_AT = datetime(2026, 1, 1, tzinfo=UTC)


def test_runtime_frontend_response_rejects_an_off_enum_type() -> None:
    with pytest.raises(ValidationError):
        RuntimeFrontendResponse(frontend_id="f1", type="mobile_app", enabled=True)


def test_runtime_quota_summary_response_rejects_off_enum_unit_period_dimension() -> None:
    with pytest.raises(ValidationError):
        RuntimeQuotaSummaryResponse(
            quota_policy_id="p1", unit="monthly_run", limit_count=3, period="lifetime", dimension="product"
        )
    with pytest.raises(ValidationError):
        RuntimeQuotaSummaryResponse(
            quota_policy_id="p1", unit="scenario_run", limit_count=3, period="monthly", dimension="product"
        )
    with pytest.raises(ValidationError):
        RuntimeQuotaSummaryResponse(
            quota_policy_id="p1", unit="scenario_run", limit_count=3, period="lifetime", dimension="tenant"
        )


def test_quota_state_response_rejects_off_enum_unit_period_dimension() -> None:
    base = {
        "guest_id": "g1",
        "product_id": "p1",
        "quota_policy_id": "p1",
        "dimension_key": "p1",
        "limit_count": 3,
        "used_count": 0,
        "remaining_count": 3,
        "exhausted": False,
    }
    with pytest.raises(ValidationError):
        QuotaStateResponse(**base, quota_dimension="tenant", unit="scenario_run", period="lifetime")
    with pytest.raises(ValidationError):
        QuotaStateResponse(**base, quota_dimension="product", unit="monthly_run", period="lifetime")
    with pytest.raises(ValidationError):
        QuotaStateResponse(**base, quota_dimension="product", unit="scenario_run", period="monthly")


def test_client_event_response_rejects_an_off_enum_event_type() -> None:
    with pytest.raises(ValidationError):
        ClientEventResponse(event_id="web_evt_1", event_type="client.result_copied")


def test_scenario_start_response_rejects_an_off_enum_status() -> None:
    with pytest.raises(ValidationError):
        ScenarioStartResponse(scenario_session_id="s1", job_id="j1", status="cancelled")


def test_scenario_session_response_rejects_an_off_enum_status() -> None:
    with pytest.raises(ValidationError):
        ScenarioSessionResponse(scenario_session_id="s1", job_id="j1", status="cancelled")


def test_handoff_create_response_rejects_an_off_enum_status() -> None:
    with pytest.raises(ValidationError):
        HandoffCreateResponse(
            handoff_id="h1", handoff_token="t1", status="pending", expires_at=_EXPIRES_AT
        )


def test_handoff_preview_response_rejects_an_off_enum_status() -> None:
    with pytest.raises(ValidationError):
        HandoffPreviewResponse(
            handoff_id="h1",
            status="pending",
            source_product_id="p1",
            source_product_display_name="P1",
            target_product_id="p2",
            target_product_display_name="P2",
            target_scenario_id="s1",
            preview={},
            expires_at=_EXPIRES_AT,
        )


def test_quota_state_payload_exposes_resets_at_and_hides_period_key() -> None:
    state = QuotaState(
        guest_id="g1",
        product_id="p1",
        quota_policy_id="p1",
        quota_dimension=QuotaDimension.product,
        dimension_key="p1",
        scenario_id=None,
        unit=QuotaUnit.scenario_run,
        period=QuotaPeriod.calendar_day,
        period_key="day:2026-09-30",
        limit_count=3,
        used_count=0,
        remaining_count=3,
        exhausted=False,
        resets_at=datetime(2026, 10, 1, tzinfo=UTC),
    )
    body = QuotaStateResponse(**_quota_state_payload(state)).model_dump(mode="json")
    assert body["resets_at"] == "2026-10-01T00:00:00Z"
    assert body["period"] == "calendar_day"
    assert "period_key" not in body
