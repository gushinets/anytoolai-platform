from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta
from math import isfinite

ACCOUNT_SCOPE_ENV = "ANYTOOLAI_MODEL_CATALOG_ACCOUNT_SCOPE"
TTL_SECONDS_ENV = "ANYTOOLAI_MODEL_CATALOG_TTL_SECONDS"
REFRESH_COOLDOWN_SECONDS_ENV = "ANYTOOLAI_MODEL_CATALOG_REFRESH_COOLDOWN_SECONDS"
LEASE_SECONDS_ENV = "ANYTOOLAI_MODEL_CATALOG_LEASE_SECONDS"
FETCH_TIMEOUT_SECONDS_ENV = "ANYTOOLAI_MODEL_CATALOG_FETCH_TIMEOUT_SECONDS"
MAX_ACCOUNT_SCOPE_LENGTH = 128


@dataclass(frozen=True)
class ModelCatalogSettings:
    account_scope: str
    ttl: timedelta
    refresh_cooldown: timedelta
    lease_duration: timedelta
    fetch_timeout_seconds: float

    @classmethod
    def from_env(cls) -> ModelCatalogSettings:
        account_scope = os.getenv(ACCOUNT_SCOPE_ENV, "openai-default").strip()
        if not account_scope:
            raise ValueError(f"{ACCOUNT_SCOPE_ENV} must not be blank")
        if len(account_scope) > MAX_ACCOUNT_SCOPE_LENGTH:
            raise ValueError(
                f"{ACCOUNT_SCOPE_ENV} must not exceed {MAX_ACCOUNT_SCOPE_LENGTH} characters"
            )
        fetch_timeout_seconds = _positive_seconds(FETCH_TIMEOUT_SECONDS_ENV, 10, "fetch timeout")
        lease_duration = _positive_duration(LEASE_SECONDS_ENV, 30, "lease")
        if model_catalog_refresh_deadline_seconds(lease_duration) <= fetch_timeout_seconds * 2:
            raise ValueError("model catalog lease must exceed the two upstream fetch deadlines")
        return cls(
            account_scope=account_scope,
            ttl=_positive_duration(TTL_SECONDS_ENV, 24 * 60 * 60, "TTL"),
            refresh_cooldown=_positive_duration(
                REFRESH_COOLDOWN_SECONDS_ENV, 60, "refresh cooldown"
            ),
            lease_duration=lease_duration,
            fetch_timeout_seconds=fetch_timeout_seconds,
        )


def model_catalog_refresh_deadline_seconds(lease_duration: timedelta) -> float:
    lease_seconds = lease_duration.total_seconds()
    return max(lease_seconds * 0.9, lease_seconds - 1.0)


def _positive_duration(name: str, default: float, label: str) -> timedelta:
    return timedelta(seconds=_positive_seconds(name, default, label))


def _positive_seconds(name: str, default: float, label: str) -> float:
    value = float(os.getenv(name, str(default)))
    if not isfinite(value) or value <= 0:
        raise ValueError(f"model catalog {label} setting {name} must be greater than zero")
    return value
