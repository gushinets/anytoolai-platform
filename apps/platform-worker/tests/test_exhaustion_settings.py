"""Exhaustion transport is opt-in and never weakens the service credential boundary."""

from datetime import datetime, timedelta, timezone

import pytest
from anytoolai_platform_core.quotas.exhaustion import ExhaustionEvent
from anytoolai_platform_worker.exhaustion import ExhaustionSettings
from pydantic import SecretStr, ValidationError

TOKEN = "synthetic-exhaustion-service-" + "s" * 32


def test_exhaustion_delivery_defaults_off_and_requires_complete_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ANYTOOLAI_PORTAL_EXHAUSTION_DELIVERY_ENABLED", raising=False)
    assert ExhaustionSettings.from_env() is None
    monkeypatch.setenv("ANYTOOLAI_PORTAL_EXHAUSTION_DELIVERY_ENABLED", "true")
    monkeypatch.delenv("ANYTOOLAI_PORTAL_BASE_URL", raising=False)
    monkeypatch.delenv("ANYTOOLAI_PORTAL_ACCESS_SERVICE_TOKEN", raising=False)
    with pytest.raises(ValidationError):
        ExhaustionSettings.from_env()
    monkeypatch.setenv("ANYTOOLAI_PORTAL_BASE_URL", "https://portal.example.test")
    monkeypatch.setenv("ANYTOOLAI_PORTAL_ACCESS_SERVICE_TOKEN", TOKEN)
    assert ExhaustionSettings.from_env().service_token.get_secret_value() == TOKEN
    monkeypatch.setenv("ANYTOOLAI_PORTAL_CONSUMER_ID", "custom-kernel")
    assert ExhaustionSettings.from_env().consumer_id == "custom-kernel"
    monkeypatch.setenv("ANYTOOLAI_PORTAL_CONSUMER_ID", "invalid_consumer")
    with pytest.raises(ValidationError):
        ExhaustionSettings.from_env()
    monkeypatch.setenv("ANYTOOLAI_PORTAL_EXHAUSTION_DELIVERY_ENABLED", "maybe")
    with pytest.raises(ValueError):
        ExhaustionSettings.from_env()


@pytest.mark.parametrize(
    "url",
    [
        "http://remote.example.test",
        "https://name:secret@portal.example.test",
        "https://portal.example.test/path",
        "https://portal.example.test?secret=value",
        "https://portal.example.test#fragment",
        "http://127.0.0.1:9000",
        "https://portal.example.test:bad",
        "https://portal.example.test:0",
        "https://portal.example.test/\n",
    ],
)
def test_production_refuses_insecure_or_untrusted_origin(url: str) -> None:
    with pytest.raises(ValidationError):
        ExhaustionSettings(
            base_url=url,
            service_token=SecretStr(TOKEN),
            tenant_id="anytoolai",
            region="ru",
            app_env="production",
        )


def test_local_test_origin_and_secret_safe_validation() -> None:
    assert ExhaustionSettings(
        base_url="http://127.0.0.1:9000",
        service_token=SecretStr(TOKEN),
        tenant_id="anytoolai",
        region="ru",
        app_env="test",
    )
    with pytest.raises(ValidationError) as refused:
        ExhaustionSettings(
            base_url="https://portal.example.test",
            service_token=SecretStr("not-a-valid-secret"),
            tenant_id="anytoolai",
            region="ru",
        )
    assert "not-a-valid-secret" not in str(refused.value)


def test_exhaustion_wire_time_is_utc_independent_of_database_timezone() -> None:
    event = ExhaustionEvent(
        tenant_id="anytoolai",
        region="ru",
        user_id="00000000-0000-4000-8000-000000000001",
        allowance_id="00000000-0000-4000-8000-000000000002",
        product_id="synthetic_product",
        metric_key="synthetic_product.runs",
        unit="run",
        quantity=1,
        occurred_at=datetime(2026, 11, 11, 13, tzinfo=timezone(timedelta(hours=8))),
    )
    assert event.wire()["occurred_at"] == "2026-11-11T05:00:00+00:00"
