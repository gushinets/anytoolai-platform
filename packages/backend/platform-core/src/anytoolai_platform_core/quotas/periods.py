from __future__ import annotations

from datetime import UTC, datetime, timedelta

from anytoolai_platform_core.quotas.models import QuotaPeriod, ResolvedQuotaPeriod


class UnsupportedQuotaPeriodError(ValueError):
    pass


def resolve_quota_period(period: QuotaPeriod, now: datetime) -> ResolvedQuotaPeriod:
    """Resolve the fixed UTC calendar window containing `now`.

    Key and boundaries come from the same normalized instant; the key is never parsed back.
    """
    if now.utcoffset() is None:
        raise ValueError("quota period resolution requires a timezone-aware datetime")
    utc = now.astimezone(UTC)
    day = utc.replace(hour=0, minute=0, second=0, microsecond=0)
    match period:
        case QuotaPeriod.lifetime:
            return ResolvedQuotaPeriod(period, "lifetime", None, None)
        case QuotaPeriod.calendar_day:
            return ResolvedQuotaPeriod(period, f"day:{day:%Y-%m-%d}", day, day + timedelta(days=1))
        case QuotaPeriod.calendar_week:
            iso_year, iso_week, _ = utc.isocalendar()
            start = day - timedelta(days=utc.weekday())
            return ResolvedQuotaPeriod(
                period, f"week:{iso_year}-W{iso_week:02d}", start, start + timedelta(days=7)
            )
        case QuotaPeriod.calendar_month:
            start = day.replace(day=1)
            end = (start + timedelta(days=32)).replace(day=1)
            return ResolvedQuotaPeriod(period, f"month:{start:%Y-%m}", start, end)
        case _:
            raise UnsupportedQuotaPeriodError(f"unsupported quota period: {period!r}")
