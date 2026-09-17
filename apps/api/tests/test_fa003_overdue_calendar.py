"""FA-003 regression: customer overdue age uses the Asia/Beirut calendar (D-040, FI-25)."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import text
from test_fa008_obligations import _opening
from test_invoice_editor import _auth, _catalog, _owner_context

from tawzeevo_api.services.customer_ledger import customer_debts


def _set_threshold(client, tenant_id: str, token: str, days: int | None) -> None:
    response = client.put(
        "/api/v1/customer-ledger/settings",
        params={"tenant_id": tenant_id},
        headers=_auth(token),
        json={"customer_overdue_threshold_days": days},
    )
    assert response.status_code == 200, response.text


@pytest.mark.parametrize(
    ("label", "oldest", "now", "threshold", "expected_age", "expected_overdue"),
    [
        # Sep 6 21:15 UTC is already Sep 7 00:15 in Beirut: age 6 > 5 (UTC would say 5).
        (
            "beirut-midnight-before-utc-midnight",
            datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
            datetime(2026, 9, 6, 21, 15, tzinfo=UTC),
            5,
            6,
            True,
        ),
        # Sep 6 20:00 UTC is Sep 6 23:00 in Beirut: age exactly 5, not > 5.
        (
            "exactly-threshold-not-overdue",
            datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
            datetime(2026, 9, 6, 20, 0, tzinfo=UTC),
            5,
            5,
            False,
        ),
        # Crosses the October DST change: Oct 20 22:30 UTC is Oct 21 01:30 (+03:00) and
        # Oct 31 21:30 UTC is Oct 31 23:30 (+02:00): Beirut age 10 (UTC would say 11).
        (
            "dst-transition",
            datetime(2026, 10, 20, 22, 30, tzinfo=UTC),
            datetime(2026, 10, 31, 21, 30, tzinfo=UTC),
            10,
            10,
            False,
        ),
        # Same instants with threshold 9 are overdue.
        (
            "dst-transition-overdue",
            datetime(2026, 10, 20, 22, 30, tzinfo=UTC),
            datetime(2026, 10, 31, 21, 30, tzinfo=UTC),
            9,
            10,
            True,
        ),
        # Unset threshold disables overdue detection but still reports the age.
        (
            "unset-threshold-disabled",
            datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
            datetime(2026, 9, 6, 21, 15, tzinfo=UTC),
            None,
            6,
            False,
        ),
    ],
)
def test_overdue_age_uses_asia_beirut_calendar(
    client,
    session_factory,
    label: str,
    oldest: datetime,
    now: datetime,
    threshold: int | None,
    expected_age: int,
    expected_overdue: bool,
) -> None:
    _owner, tenant_id, token = _owner_context(client, session_factory, f"fa003-{label}")
    _category, _product, customer = _catalog(client, tenant_id, token)
    _set_threshold(client, tenant_id, token, threshold)
    _opening(client, tenant_id, token, customer["id"], "75.0000", effective_at=oldest)

    with session_factory() as db:
        # The calendar must not depend on the database session time zone.
        db.execute(text("SET TIME ZONE 'America/New_York'"))
        debts = customer_debts(db, UUID(tenant_id), now=now).debts

    assert len(debts) == 1
    debt = debts[0]
    assert debt.overdue_age_days == expected_age
    assert debt.is_overdue is expected_overdue
    assert debt.overdue_threshold_days == threshold
    assert (debt.alert_key is not None) is expected_overdue
