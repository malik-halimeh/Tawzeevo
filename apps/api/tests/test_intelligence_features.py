"""D-089 shared customer feature layer: reconciles with the ledger, debt and analytics services,
uses the current confirmed revision, keeps currencies apart, honours the tenant calendar, is
reproducible for a fixed as_of and never writes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from test_delivery_tasks import _post
from test_invoice_editor import (
    _attach_latest_cost,
    _auth,
    _catalog,
    _confirmable_payload,
    _owner_context,
)
from test_procurement import _confirm_invoice

from tawzeevo_api.models import (
    Customer,
    CustomerLedgerEntry,
    DeliveryTask,
    Invoice,
    InvoiceRevision,
    Order,
    Payment,
    PaymentAllocation,
    SupplierLedgerEntry,
    SupplierPurchase,
)
from tawzeevo_api.services import analytics
from tawzeevo_api.services.customer_ledger import customer_balances, customer_debts
from tawzeevo_api.services.intelligence.customers import daily_priorities, inactivity_risk
from tawzeevo_api.services.intelligence.features import customer_features

CANONICAL_TABLES = (
    Invoice,
    InvoiceRevision,
    CustomerLedgerEntry,
    Payment,
    PaymentAllocation,
    SupplierPurchase,
    SupplierLedgerEntry,
    Customer,
    Order,
    DeliveryTask,
)


def canonical_counts(session_factory) -> dict[str, int]:
    with session_factory() as db:
        return {
            model.__tablename__: int(db.scalar(select(func.count()).select_from(model)) or 0)
            for model in CANONICAL_TABLES
        }


def set_confirmed_at(session_factory, invoice_id: str, when: datetime) -> None:
    with session_factory() as db:
        row = db.get(Invoice, UUID(invoice_id))
        assert row is not None
        row.confirmed_at = when
        db.commit()


def seed_customer_history(client, session_factory, suffix: str):
    """One USD customer with a regular 20-day cadence (edited, cancelled, paid, reversed, an old
    opening debt), one LBP pair for the same customer and a second USD customer."""
    owner, tenant, token = _owner_context(client, session_factory, suffix)
    _category, product, customer = _catalog(client, tenant, token, name="Cedar Water")
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    _c2, product_lbp, _unused = _catalog(
        client, tenant, token, name="Bread", barcode="5280000000043", currency="LBP", price="90000"
    )
    supplier = _post(client, tenant, token, "/api/v1/suppliers", {"name": "Mill"}).json()
    assert (
        _post(
            client,
            tenant,
            token,
            f"/api/v1/suppliers/products/{product_lbp['id']}/costs",
            {
                "supplier_id": supplier["id"],
                "unit_cost": "60000",
                "currency": "LBP",
                "cost_basis": "PIECE",
            },
        ).status_code
        == 201
    )
    other = client.post(
        f"/api/v1/tenants/{tenant}/customers",
        headers=_auth(token),
        json={"name": "Byblos Grocery", "phone": "+96171000999", "grade": "B"},
    ).json()
    client.put(
        f"/api/v1/customer-ledger/settings?tenant_id={tenant}",
        headers=_auth(token),
        json={"customer_overdue_threshold_days": 7},
    )
    now = datetime.now(UTC)
    opening = _post(
        client,
        tenant,
        token,
        "/api/v1/customer-ledger/opening-balances",
        {
            "idempotency_key": str(uuid4()),
            "customer_id": customer["id"],
            "currency": "USD",
            "signed_amount": "100.0000",
            "effective_at": (now - timedelta(days=40)).isoformat(),
        },
    )
    assert opening.status_code == 201, opening.text

    first = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "2")
    second = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "3")
    third = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "1")
    # Confirmed edit of the third invoice: 1 -> 4 pieces; the current revision is the truth.
    payload = _confirmable_payload(
        customer["id"], product["id"], predecessor_id=third["current_revision_id"]
    )
    payload["items"][0]["quantity_expression"] = "4"  # type: ignore[index]
    edited = client.put(
        f"/api/v1/invoices/{third['id']}",
        params={"tenant_id": tenant},
        headers=_auth(token),
        json=payload,
    )
    assert edited.status_code == 200, edited.text
    doomed = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "7")
    assert (
        _post(
            client,
            tenant,
            token,
            f"/api/v1/invoices/{doomed['id']}/cancel",
            {"idempotency_key": str(uuid4()), "reason": "x"},
        ).status_code
        == 200
    )
    lbp_payload = _confirmable_payload(customer["id"], product_lbp["id"])
    lbp_payload["currency"] = "LBP"
    lbp_payload["items"][0]["barcode"] = "5280000000043"  # type: ignore[index]
    lbp_payload["items"][0]["quantity_expression"] = "1"  # type: ignore[index]
    lbp_draft = _post(client, tenant, token, "/api/v1/invoices", lbp_payload).json()
    lbp = _post(
        client,
        tenant,
        token,
        f"/api/v1/invoices/{lbp_draft['id']}/confirm",
        {"expected_revision_id": lbp_draft["current_revision_id"]},
    ).json()
    other_invoice = _confirm_invoice(client, tenant, token, other["id"], product["id"], "1")

    for invoice, days in ((first, 70), (second, 50), (third, 30)):
        set_confirmed_at(session_factory, invoice["id"], now - timedelta(days=days))

    receipt = _post(
        client,
        tenant,
        token,
        "/api/v1/payments/customer-receipts",
        {
            "idempotency_key": str(uuid4()),
            "customer_id": customer["id"],
            "amount": "10",
            "currency": "USD",
            "paid_at": (now - timedelta(days=2)).isoformat(),
        },
    )
    assert receipt.status_code == 201, receipt.text
    bounced = _post(
        client,
        tenant,
        token,
        "/api/v1/payments/customer-receipts",
        {
            "idempotency_key": str(uuid4()),
            "customer_id": customer["id"],
            "amount": "5",
            "currency": "USD",
            "paid_at": (now - timedelta(days=1)).isoformat(),
        },
    ).json()
    assert (
        _post(
            client,
            tenant,
            token,
            f"/api/v1/payments/{bounced['id']}/reverse",
            {"idempotency_key": str(uuid4()), "reason": "bounced"},
        ).status_code
        == 201
    )
    return {
        "owner": owner,
        "tenant": tenant,
        "token": token,
        "customer": customer,
        "other": other,
        "product": product,
        "invoices": {
            "first": first,
            "second": second,
            "third": edited.json(),
            "lbp": lbp,
            "other": other_invoice,
        },
    }


def test_features_reconcile_with_canonical_services(client, session_factory):
    seed = seed_customer_history(client, session_factory, "intfeat")
    tenant = UUID(seed["tenant"])
    customer_id = UUID(seed["customer"]["id"])
    inv = seed["invoices"]
    as_of = datetime.now(UTC) + timedelta(seconds=5)
    before = canonical_counts(session_factory)

    with session_factory() as db:
        rows = customer_features(db, tenant, as_of=as_of)
        again = customer_features(db, tenant, as_of=as_of)
        balances = customer_balances(db, tenant, customer_id)
        debts = {
            (d.customer_id, d.currency): d for d in customer_debts(db, tenant, now=as_of).debts
        }
        period_30 = analytics.resolve_period("30d", as_of)
        receipts_30, _refunds = analytics.customer_receipts(db, tenant, period_30)
        assert not db.new and not db.dirty and not db.deleted

    assert rows == again  # reproducible for a fixed as_of
    assert canonical_counts(session_factory) == before  # no writes
    by_key = {(r.customer_id, r.currency): r for r in rows}
    usd = by_key[(customer_id, "USD")]
    lbp = by_key[(customer_id, "LBP")]
    other = by_key[(UUID(seed["other"]["id"]), "USD")]

    # Current confirmed revision: the edited third invoice counts at its edited value; the
    # cancelled invoice is not a sale.
    expected_90 = sum(Decimal(inv[k]["net_sales"]) for k in ("first", "second", "third"))
    assert usd.invoice_count_lifetime == 3 and usd.invoice_count_90d == 3
    assert usd.sales_90d == expected_90
    # "30d" is the last 30 tenant-calendar days including today (D-068): 30 days ago is outside.
    assert usd.sales_30d == Decimal("0.0000") and usd.invoice_count_30d == 0
    assert usd.recent_cancelled_invoices == 1
    # Currencies never combine.
    assert lbp.invoice_count_lifetime == 1 and lbp.sales_30d == Decimal(inv["lbp"]["net_sales"])
    assert other.invoice_count_lifetime == 1

    # Ledger reconciliation per currency.
    ledger = {b.currency: b.balance for b in balances.balances}
    assert usd.balance == ledger["USD"] and lbp.balance == ledger["LBP"]
    debt = debts[(customer_id, "USD")]
    assert usd.outstanding_balance == debt.balance
    assert usd.oldest_unpaid_at == debt.oldest_unpaid_at
    assert usd.overdue_age_days == debt.overdue_age_days == 40
    assert usd.is_overdue is True and usd.overdue_threshold_days == 7
    # Receipts minus reversals (D-065), and the reversal is recent friction.
    assert usd.receipts_30d == receipts_30["USD"] == Decimal("10.0000")
    assert usd.recent_receipt_reversals == 1

    # Cadence: purchases 70, 50, 30 days ago -> median 20, 30 days since -> ratio 1.5.
    assert usd.median_purchase_interval_days == Decimal(20)
    assert usd.days_since_last_purchase == 30
    assert usd.history_sufficient and usd.recency_ratio == Decimal("1.5000")
    assert usd.recent_activity_ratio is None  # first purchase inside the 90d window


def test_priority_and_inactivity_services_are_owner_data_only_and_stable(client, session_factory):
    seed = seed_customer_history(client, session_factory, "intprio")
    _o, other_tenant, _t = _owner_context(client, session_factory, "intprio2")
    tenant = UUID(seed["tenant"])
    as_of = datetime.now(UTC) + timedelta(seconds=5)
    with session_factory() as db:
        _as_of, priorities = daily_priorities(db, tenant, as_of=as_of)
        _as_of, inactive = inactivity_risk(db, tenant, as_of=as_of)
        _as_of, empty = daily_priorities(db, UUID(other_tenant), as_of=as_of)
        assert daily_priorities(db, tenant, as_of=as_of)[1] == priorities
    assert empty == {}
    assert list(priorities) == ["LBP", "USD"]
    top = priorities["USD"][0]
    assert str(top.features.customer_id) == seed["customer"]["id"]
    assert top.suggested_action_code == "COLLECT_OVERDUE"
    assert {r.code for r in top.reasons} >= {
        "OLD_OVERDUE_BALANCE",
        "RECENT_CANCELLATIONS",
        "RECENT_REVERSALS",
        "PAST_NORMAL_PURCHASE_INTERVAL",
    }
    statuses = {
        (str(r.features.customer_id), c): r.status for c, rows in inactive.items() for r in rows
    }
    assert statuses[(seed["customer"]["id"], "USD")] == "WATCH"
    assert statuses[(seed["customer"]["id"], "LBP")] == "INSUFFICIENT_HISTORY"


def test_thirty_day_window_follows_the_tenant_calendar(client, session_factory):
    owner, tenant, token = _owner_context(client, session_factory, "intcal")
    _category, product, customer = _catalog(client, tenant, token, name="Cedar Water")
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    inside = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "1")
    outside = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "1")
    as_of = datetime.now(UTC) + timedelta(seconds=5)
    start = analytics.resolve_period("30d", as_of).start
    assert start is not None
    set_confirmed_at(session_factory, inside["id"], start + timedelta(minutes=30))
    set_confirmed_at(session_factory, outside["id"], start - timedelta(minutes=30))
    with session_factory() as db:
        (row,) = customer_features(db, UUID(tenant), as_of=as_of)
    assert row.invoice_count_30d == 1 and row.invoice_count_90d == 2
    # Last purchase at 00:30 Beirut on the window's first day is 29 calendar days ago.
    assert row.days_since_last_purchase == 29
