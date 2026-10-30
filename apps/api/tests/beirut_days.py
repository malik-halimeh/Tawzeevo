"""Stable timestamps for seeds measured in tenant-calendar days (D-068)."""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

BEIRUT = ZoneInfo("Asia/Beirut")


def beirut_days_ago(days: int, *, now: datetime | None = None) -> datetime:
    """Return UTC for noon N Beirut dates ago, subtracting dates before applying DST."""
    today = (now or datetime.now(UTC)).astimezone(BEIRUT).date()
    day = today - timedelta(days=days)
    return datetime.combine(day, time(12, 0), tzinfo=BEIRUT).astimezone(UTC)
