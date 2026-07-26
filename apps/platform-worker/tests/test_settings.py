from __future__ import annotations

import pytest
from anytoolai_platform_core.storage.db import (
    POSTGRES_DB_ENV,
    POSTGRES_PASSWORD_ENV,
    POSTGRES_USER_ENV,
)
from anytoolai_platform_worker.settings import (
    GENERIC_DATABASE_URL_ENV,
    PROJECT_DATABASE_URL_ENV,
    POLL_INTERVAL_ENV,
    WorkerSettings,
)

POLL_INTERVAL_SECONDS = 0.25


def _clear_database_url_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for env_var in (
        PROJECT_DATABASE_URL_ENV,
        GENERIC_DATABASE_URL_ENV,
        POSTGRES_USER_ENV,
        POSTGRES_PASSWORD_ENV,
        POSTGRES_DB_ENV,
    ):
        monkeypatch.delenv(env_var, raising=False)


@pytest.mark.parametrize("interval", ["nan", "inf", "-inf", "0", "-1"])
def test_worker_settings_reject_non_finite_or_non_positive_poll_intervals(
    monkeypatch: pytest.MonkeyPatch,
    interval: str,
) -> None:
    monkeypatch.setenv(GENERIC_DATABASE_URL_ENV, "sqlite://")
    monkeypatch.setenv(POLL_INTERVAL_ENV, interval)

    with pytest.raises(ValueError, match=f"{POLL_INTERVAL_ENV} must be greater than zero"):
        WorkerSettings.from_env()


def test_worker_settings_accepts_positive_finite_poll_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(GENERIC_DATABASE_URL_ENV, "sqlite://")
    monkeypatch.setenv(POLL_INTERVAL_ENV, str(POLL_INTERVAL_SECONDS))

    settings = WorkerSettings.from_env()

    assert settings.poll_interval_seconds == POLL_INTERVAL_SECONDS


def test_worker_settings_raises_without_any_database_url_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_database_url_env(monkeypatch)

    with pytest.raises(RuntimeError):
        WorkerSettings.from_env()


def test_worker_settings_error_mentions_all_three_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_database_url_env(monkeypatch)

    with pytest.raises(RuntimeError) as exc_info:
        WorkerSettings.from_env()

    message = str(exc_info.value)
    assert PROJECT_DATABASE_URL_ENV in message
    assert GENERIC_DATABASE_URL_ENV in message
    assert POSTGRES_USER_ENV in message
    assert POSTGRES_PASSWORD_ENV in message
    assert POSTGRES_DB_ENV in message


def test_worker_settings_build_database_url_from_postgres_components(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_database_url_env(monkeypatch)
    monkeypatch.setenv(POSTGRES_USER_ENV, "produser")
    monkeypatch.setenv(POSTGRES_PASSWORD_ENV, "p@ss:w/rd#1%2")
    monkeypatch.setenv(POSTGRES_DB_ENV, "proddb")

    settings = WorkerSettings.from_env()

    assert settings.database_url == (
        "postgresql+psycopg://produser:p%40ss%3Aw%2Frd%231%252@postgres:5432/proddb"
    )
