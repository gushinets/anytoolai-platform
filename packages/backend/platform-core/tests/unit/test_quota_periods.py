from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from anytoolai_platform_core.bootstrap.registry import build_config_registry
from anytoolai_platform_core.quotas.models import QuotaPeriod, QuotaUsageRecord
from anytoolai_platform_core.quotas.periods import (
    UnsupportedQuotaPeriodError,
    resolve_quota_period,
)
from anytoolai_platform_core.quotas.service import GuestQuotaService

REPO_ROOT = Path(__file__).resolve().parents[5]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"


def _utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


@pytest.mark.parametrize(
    ("period", "now", "key", "starts_at", "ends_at"),
    [
        (QuotaPeriod.lifetime, _utc(2026, 9, 30, 12), "lifetime", None, None),
        (
            QuotaPeriod.calendar_day,
            _utc(2026, 9, 29, 23, 59, 59, 999000),
            "day:2026-09-29",
            _utc(2026, 9, 29),
            _utc(2026, 9, 30),
        ),
        (  # month rollover
            QuotaPeriod.calendar_day,
            _utc(2026, 9, 30, 5),
            "day:2026-09-30",
            _utc(2026, 9, 30),
            _utc(2026, 10, 1),
        ),
        (  # year rollover
            QuotaPeriod.calendar_day,
            _utc(2026, 12, 31, 23),
            "day:2026-12-31",
            _utc(2026, 12, 31),
            _utc(2027, 1, 1),
        ),
        (  # Wednesday, ISO week 40
            QuotaPeriod.calendar_week,
            _utc(2026, 9, 30, 12),
            "week:2026-W40",
            _utc(2026, 9, 28),
            _utc(2026, 10, 5),
        ),
        (  # ISO week-year differs from calendar year
            QuotaPeriod.calendar_week,
            _utc(2021, 1, 1),
            "week:2020-W53",
            _utc(2020, 12, 28),
            _utc(2021, 1, 4),
        ),
        (  # Sunday is the last instant of its week
            QuotaPeriod.calendar_week,
            _utc(2026, 10, 4, 23, 59, 59),
            "week:2026-W40",
            _utc(2026, 9, 28),
            _utc(2026, 10, 5),
        ),
        (
            QuotaPeriod.calendar_month,
            _utc(2026, 9, 15),
            "month:2026-09",
            _utc(2026, 9, 1),
            _utc(2026, 10, 1),
        ),
        (  # leap-year February
            QuotaPeriod.calendar_month,
            _utc(2028, 2, 29, 12),
            "month:2028-02",
            _utc(2028, 2, 1),
            _utc(2028, 3, 1),
        ),
        (  # 31-day month must not skip the next one
            QuotaPeriod.calendar_month,
            _utc(2026, 1, 31),
            "month:2026-01",
            _utc(2026, 1, 1),
            _utc(2026, 2, 1),
        ),
        (  # year rollover
            QuotaPeriod.calendar_month,
            _utc(2026, 12, 31, 23),
            "month:2026-12",
            _utc(2026, 12, 1),
            _utc(2027, 1, 1),
        ),
    ],
)
def test_resolve_quota_period(
    period: QuotaPeriod,
    now: datetime,
    key: str,
    starts_at: datetime | None,
    ends_at: datetime | None,
) -> None:
    resolved = resolve_quota_period(period, now)
    assert (resolved.period, resolved.period_key) == (period, key)
    assert (resolved.starts_at, resolved.ends_at) == (starts_at, ends_at)


def test_aware_non_utc_datetime_is_normalized_to_utc_first() -> None:
    # 2026-10-01 01:30 +03:00 is still 2026-09-30 in UTC.
    now = datetime(2026, 10, 1, 1, 30, tzinfo=timezone(timedelta(hours=3)))
    resolved = resolve_quota_period(QuotaPeriod.calendar_day, now)
    assert resolved.period_key == "day:2026-09-30"
    assert resolved.ends_at == _utc(2026, 10, 1)


def test_naive_datetime_is_rejected() -> None:
    with pytest.raises(ValueError):
        resolve_quota_period(QuotaPeriod.calendar_day, datetime(2026, 9, 30))


def test_unsupported_period_is_rejected() -> None:
    with pytest.raises(UnsupportedQuotaPeriodError):
        resolve_quota_period("bogus", _utc(2026, 9, 30))  # type: ignore[arg-type]


# --- service-level boundary regressions on in-memory doubles (no PostgreSQL) ---


class _FakeQuotaRepo:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, ...], QuotaUsageRecord] = {}

    def get_by_dimension(self, **k: Any) -> QuotaUsageRecord | None:
        return self.rows.get(self._key(k))

    def ensure_usage(self, **k: Any) -> QuotaUsageRecord:
        key = self._key(k)
        if key not in self.rows:
            self.rows[key] = QuotaUsageRecord(
                **{n: k[n] for n in k if n != "metadata"}  # same fields as the real insert
            )
        return self.rows[key]

    def consume_if_available(self, record: QuotaUsageRecord) -> QuotaUsageRecord | None:
        if record.used_count >= record.limit_count:
            return None
        updated = replace(record, used_count=record.used_count + 1)
        self.rows[self._key(vars(record))] = updated
        return updated

    def get(self, usage_id: str) -> QuotaUsageRecord | None:
        return next((r for r in self.rows.values() if r.id == usage_id), None)

    @staticmethod
    def _key(k: dict[str, Any]) -> tuple[str, ...]:
        return tuple(
            str(k[n])
            for n in (
                "guest_id",
                "product_id",
                "quota_policy_id",
                "quota_dimension",
                "dimension_key",
                "period_key",
            )
        )


class _FakeGuests:
    def get(self, guest_id: str, **_: Any) -> object:
        return object()


@dataclass
class _FakeEmitter:
    events: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def emit(
        self,
        event_type: str,
        context: Any,
        result_status: Any = None,
        properties: Any = None,
        **_: Any,
    ) -> None:
        self.events.append((event_type, properties))


class _Clock:
    def __init__(self, *values: datetime) -> None:
        self._values = list(values)
        self.reads = 0

    def __call__(self) -> datetime:
        self.reads += 1
        return self._values.pop(0)


def _service(clock: _Clock) -> tuple[GuestQuotaService, _FakeQuotaRepo, _FakeEmitter]:
    registry = build_config_registry(CONFIG_ROOT)
    policy = registry.get_quota_policy("kernel_demo.guest_quota_v1")
    assert policy is not None
    registry = replace(
        registry,
        quotas={
            **dict(registry.quotas),
            policy.quota_policy_id: replace(
                policy, period=QuotaPeriod.calendar_day, limit_count=10
            ),
        },
    )
    repo, emitter = _FakeQuotaRepo(), _FakeEmitter()
    service = GuestQuotaService(
        config_registry=registry,
        quota_repository=repo,  # type: ignore[arg-type]
        guest_repository=_FakeGuests(),  # type: ignore[arg-type]
        event_emitter=emitter,  # type: ignore[arg-type]
        clock=clock,
    )
    return service, repo, emitter


def test_consume_uses_window_resolved_at_validation() -> None:
    clock = _Clock(_utc(2026, 9, 30, 23, 59, 59, 999000), _utc(2026, 10, 1))
    service, repo, emitter = _service(clock)
    validation = service.validate_accepted_start(
        tenant_id="t", region="r", product_id="kernel_demo", guest_id="g", scenario_id="s"
    )
    assert validation is not None
    state = service.consume_for_accepted_start(
        tenant_id="t",
        region="r",
        product_id="kernel_demo",
        frontend_id="f",
        guest_id="g",
        scenario_id="s",
        scenario_session_id="ss",
        validation=validation,
    )
    assert clock.reads == 1  # consume must not read the clock again
    assert [r.period_key for r in repo.rows.values()] == ["day:2026-09-30"]
    assert state.resets_at == _utc(2026, 10, 1)
    assert [(t, p["period_key"]) for t, p in emitter.events] == [
        ("quota.checked", "day:2026-09-30"),
        ("quota.consumed", "day:2026-09-30"),
    ]
    assert all("resets_at" not in p for _, p in emitter.events)


def test_check_quota_resolves_window_once_and_exposes_resets_at() -> None:
    # Second value would be day B; a second clock read would yield it (and then IndexError).
    clock = _Clock(_utc(2026, 9, 30, 23, 59, 59, 999000), _utc(2026, 10, 1))
    service, repo, _ = _service(clock)
    state = service.check_quota(
        tenant_id="t",
        region="r",
        product_id="kernel_demo",
        guest_id="g",
        emit_event=False,
        persist_usage=False,
    )
    assert clock.reads == 1
    assert state.period_key == "day:2026-09-30"
    assert state.resets_at == _utc(2026, 10, 1)
    assert repo.rows == {}
