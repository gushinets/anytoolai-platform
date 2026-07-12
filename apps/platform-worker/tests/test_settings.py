from __future__ import annotations

import pytest
from anytoolai_platform_worker.settings import (
    GENERIC_DATABASE_URL_ENV,
    POLL_INTERVAL_ENV,
    WorkerSettings,
)

POLL_INTERVAL_SECONDS = 0.25


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
