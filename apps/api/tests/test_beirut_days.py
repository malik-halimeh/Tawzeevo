"""ML-T1: calendar-day seeds stay at Beirut noon across DST and UTC date boundaries."""

from datetime import UTC, datetime, time

import pytest
from beirut_days import BEIRUT, beirut_days_ago


@pytest.mark.parametrize(
    ("now", "days", "expected"),
    [
        ("2026-10-29T21:04:00+00:00", 30, "2026-09-29T09:00:00+00:00"),
        ("2026-10-29T21:04:00+00:00", 10, "2026-10-19T09:00:00+00:00"),
        ("2026-10-29T21:04:00+00:00", 40, "2026-09-19T09:00:00+00:00"),
        ("2026-10-29T21:04:00+00:00", 1, "2026-10-28T10:00:00+00:00"),
        ("2026-10-29T22:04:00+00:00", 30, "2026-09-30T09:00:00+00:00"),
        ("2026-03-29T21:04:00+00:00", 30, "2026-02-28T10:00:00+00:00"),
        ("2026-03-29T20:04:00+00:00", 1, "2026-03-28T10:00:00+00:00"),
        ("2026-09-23T21:04:00+00:00", 0, "2026-09-24T09:00:00+00:00"),
    ],
)
def test_beirut_days_ago_uses_local_dates_and_noon(now: str, days: int, expected: str) -> None:
    reference = datetime.fromisoformat(now)
    seeded = beirut_days_ago(days, now=reference)

    assert seeded == datetime.fromisoformat(expected)
    assert seeded.tzinfo is UTC
    local = seeded.astimezone(BEIRUT)
    assert local.time() == time(12, 0)
    assert (reference.astimezone(BEIRUT).date() - local.date()).days == days
