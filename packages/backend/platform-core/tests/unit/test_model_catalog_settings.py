from __future__ import annotations

from datetime import timedelta

import pytest
from anytoolai_platform_core.providers.catalog_settings import (
    ModelCatalogSettings,
    model_catalog_refresh_deadline_seconds,
)

DEFAULT_FETCH_TIMEOUT_SECONDS = 10.0
DEFAULT_REFRESH_DEADLINE_SECONDS = 27.0


def test_model_catalog_settings_have_named_operational_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "ANYTOOLAI_MODEL_CATALOG_ACCOUNT_SCOPE",
        "ANYTOOLAI_MODEL_CATALOG_TTL_SECONDS",
        "ANYTOOLAI_MODEL_CATALOG_REFRESH_COOLDOWN_SECONDS",
        "ANYTOOLAI_MODEL_CATALOG_LEASE_SECONDS",
        "ANYTOOLAI_MODEL_CATALOG_FETCH_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = ModelCatalogSettings.from_env()

    assert settings.account_scope == "openai-default"
    assert settings.ttl == timedelta(hours=24)
    assert settings.refresh_cooldown == timedelta(seconds=60)
    assert settings.lease_duration == timedelta(seconds=30)
    assert settings.fetch_timeout_seconds == DEFAULT_FETCH_TIMEOUT_SECONDS
    assert (
        model_catalog_refresh_deadline_seconds(settings.lease_duration)
        == DEFAULT_REFRESH_DEADLINE_SECONDS
    )


def test_model_catalog_settings_reject_non_positive_timing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANYTOOLAI_MODEL_CATALOG_TTL_SECONDS", "0")

    with pytest.raises(ValueError, match="TTL"):
        ModelCatalogSettings.from_env()


def test_model_catalog_settings_reject_lease_that_cannot_cover_both_fetches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANYTOOLAI_MODEL_CATALOG_LEASE_SECONDS", "20")
    monkeypatch.setenv("ANYTOOLAI_MODEL_CATALOG_FETCH_TIMEOUT_SECONDS", "10")

    with pytest.raises(ValueError, match="lease.*two upstream fetch deadlines"):
        ModelCatalogSettings.from_env()


def test_model_catalog_settings_reject_lease_whose_refresh_deadline_is_too_short(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANYTOOLAI_MODEL_CATALOG_LEASE_SECONDS", "20.5")
    monkeypatch.setenv("ANYTOOLAI_MODEL_CATALOG_FETCH_TIMEOUT_SECONDS", "10")

    with pytest.raises(ValueError, match="lease.*two upstream fetch deadlines"):
        ModelCatalogSettings.from_env()


def test_model_catalog_settings_reject_oversized_account_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANYTOOLAI_MODEL_CATALOG_ACCOUNT_SCOPE", "a" * 129)

    with pytest.raises(ValueError, match="128"):
        ModelCatalogSettings.from_env()
