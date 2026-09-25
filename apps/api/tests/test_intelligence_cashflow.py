"""D-089 cash-flow position and ageing: receivables/payables reconcile with the authoritative
services, ageing sums to receivables, overdue follows D-040 (and disappears with no threshold),
historical flows reconcile with payments, planned collections carry their projection warning,
currencies stay apart, no forecast field exists, and nothing is written."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from test_delivery_tasks import _post
from test_intelligence_features import canonical_counts
from test_invoice_editor import _attach_latest_cost, _auth, _catalog, _owner_context
from test_procurement import _confirm_invoice

from tawzeevo_api.services import analytics
from tawzeevo_api.services.customer_ledger import customer_debts
from tawzeevo_api.services.intelligence import cashflow as cashflow_module
from tawzeevo_api.services.intelligence.cashflow import cash_flow
from tawzeevo_api.services.supplier_purchases import outstanding_totals

FORBIDDEN_FIELDS = {
    "predicted_cash_balance",
    "expected_payment_date",
    "collection_probability",
    "supplier_due_date",
    "runway",
    "fx_converted_total",
}


def test_no_forecast_field_exists_in_any_cash_flow_shape():
    for shape in (
        cashflow_module.CashFlowReport,
        cashflow_module.CurrencyCashFlow,
        cashflow_module.PlannedCollections,
        cashflow_module.AgeingBucket,
    ):
        names = {f.name for f in dataclasses.fields(shape)}
        assert not names & FORBIDDEN_FIELDS, shape


def test_cash_flow_reconciles_per_currency_and_labels_the_projection(client, session_factory):
    owner, tenant, token = _owner_context(client, session_factory, "cashflow")
    _category, product, customer = _catalog(client, tenant, token, name="Cedar Water")
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    now = datetime.now(UTC)
    # USD: an old opening debt (ages 61-90), two invoices, a receipt, a reversed receipt.
    assert (
        _post(
            client,
            tenant,
            token,
            "/api/v1/customer-ledger/opening-balances",
            {
                "idempotency_key": str(uuid4()),
                "customer_id": customer["id"],
                "currency": "USD",
                "signed_amount": "100.0000",
                "effective_at": (now - timedelta(days=70)).isoformat(),
            },
        ).status_code
        == 201
    )
    first = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "2")
    second = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "3")
    other = client.post(
        f"/api/v1/tenants/{tenant}/customers",
        headers=_auth(token),
        json={"name": "Byblos Grocery", "phone": "+96171000777"},
    ).json()
    # LBP: a separate customer's opening debt; never added to USD.
    assert (
        _post(
            client,
            tenant,
            token,
            "/api/v1/customer-ledger/opening-balances",
            {
                "idempotency_key": str(uuid4()),
                "customer_id": other["id"],
                "currency": "LBP",
                "signed_amount": "900000.0000",
                "effective_at": now.isoformat(),
            },
        ).status_code
        == 201
    )
    for amount in ("30", "5"):
        paid = _post(
            client,
            tenant,
            token,
            "/api/v1/payments/customer-receipts",
            {
                "idempotency_key": str(uuid4()),
                "customer_id": customer["id"],
                "amount": amount,
                "currency": "USD",
                "paid_at": (now - timedelta(days=1)).isoformat(),
            },
        ).json()
    assert (
        _post(
            client,
            tenant,
            token,
            f"/api/v1/payments/{paid['id']}/reverse",
            {"idempotency_key": str(uuid4()), "reason": "bounced"},
        ).status_code
        == 201
    )
    # Supplier: payable 50, paid 20, a reversed payment of 7.
    supplier = _post(client, tenant, token, "/api/v1/suppliers", {"name": "Mill"}).json()
    assert (
        client.post(
            f"/api/v1/supplier-ledger/opening-balances?tenant_id={tenant}",
            headers=_auth(token),
            json={
                "idempotency_key": str(uuid4()),
                "supplier_id": supplier["id"],
                "currency": "USD",
                "signed_amount": "50.0000",
                "effective_at": now.isoformat(),
            },
        ).status_code
        == 201
    )
    path = f"/api/v1/payments/supplier-payments?tenant_id={tenant}"
    for amount in ("20.0000", "7.0000"):
        supplier_paid = client.post(
            path,
            headers=_auth(token),
            json={
                "idempotency_key": str(uuid4()),
                "supplier_id": supplier["id"],
                "currency": "USD",
                "amount": amount,
                "paid_at": now.isoformat(),
                "method": "CASH",
            },
        )
        assert supplier_paid.status_code == 201, supplier_paid.text
    assert (
        client.post(
            f"/api/v1/payments/supplier-payments/{supplier_paid.json()['id']}/reverse"
            f"?tenant_id={tenant}",
            headers=_auth(token),
            json={"idempotency_key": str(uuid4()), "reason": "wrong"},
        ).status_code
        == 201
    )
    # Delivery tasks: today (inside the window), in 20 days (outside) and undated (excluded).
    today = analytics.resolve_period("30d", now).end.astimezone(analytics.TENANT_TZ).date()
    for invoice, day in ((first, today), (second, today + timedelta(days=20))):
        task = _post(
            client,
            tenant,
            token,
            "/api/v1/delivery-tasks",
            {"invoice_id": invoice["id"], "delivery_date": day.isoformat()},
        )
        assert task.status_code == 201, task.text
    undated_invoice = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "1")
    assert (
        _post(
            client, tenant, token, "/api/v1/delivery-tasks", {"invoice_id": undated_invoice["id"]}
        ).status_code
        == 201
    )

    as_of = datetime.now(UTC) + timedelta(seconds=5)
    before = canonical_counts(session_factory)
    with session_factory() as db:
        report = cash_flow(db, UUID(tenant), "30d", as_of=as_of)
        assert cash_flow(db, UUID(tenant), "30d", as_of=as_of) == report
        overview = analytics.overview(db, UUID(tenant), "30d", as_of)
        totals = outstanding_totals(db, UUID(tenant))
        debts = customer_debts(db, UUID(tenant), now=as_of).debts
    assert canonical_counts(session_factory) == before

    by_currency = {row.currency: row for row in report.currencies}
    assert list(by_currency) == ["LBP", "USD"]
    usd, lbp = by_currency["USD"], by_currency["LBP"]
    overview_outstanding = {row.currency: row.amount for row in overview.customer_outstanding}
    assert usd.customer_receivables == overview_outstanding["USD"]
    assert lbp.customer_receivables == overview_outstanding["LBP"] == Decimal("900000.0000")
    supplier_totals = {row.currency: row.outstanding for row in totals.suppliers}
    assert usd.supplier_payables == supplier_totals["USD"] == Decimal("30.0000")
    assert lbp.supplier_payables == Decimal("0.0000")
    # Ageing is the receivables split by the oldest unpaid obligation's age: it sums back.
    assert sum(b.amount for b in usd.ageing) == usd.customer_receivables
    assert {b.bucket: b.customer_count for b in usd.ageing if b.customer_count} == {"AGE_61_90": 1}
    # No threshold configured: nothing is overdue (D-040).
    assert report.overdue_threshold_days is None and usd.overdue_receivables == 0
    # Historical flows reconcile with the payment semantics.
    overview_receipts = {row.currency: row.amount for row in overview.customer_receipts}
    assert usd.customer_receipts == overview_receipts["USD"] == Decimal("30.0000")
    assert usd.supplier_payments == Decimal("20.0000")
    assert usd.net_customer_collections == Decimal("30.0000")
    assert usd.average_weekly_collections is not None and usd.average_weekly_collections > 0
    # Planned collections: only the dated task inside the window, with the projection warning.
    planned = usd.planned_collections
    assert planned.task_count == 1 and planned.amount == Decimal(first["net_sales"])
    assert planned.from_date == today and planned.through_date == today + timedelta(days=6)
    assert planned.source == "DELIVERY_TASK_AMOUNT_TO_COLLECT"
    assert planned.projection_warning_code == "DELIVERY_PROJECTION_IGNORES_ADJUSTMENTS"

    client.put(
        f"/api/v1/customer-ledger/settings?tenant_id={tenant}",
        headers=_auth(token),
        json={"customer_overdue_threshold_days": 7},
    )
    with session_factory() as db:
        with_threshold = cash_flow(db, UUID(tenant), "30d", as_of=as_of)
    usd_after = next(row for row in with_threshold.currencies if row.currency == "USD")
    expected_overdue = sum(
        (d.balance for d in debts if d.currency == "USD"), Decimal("0")
    )  # the only USD debtor's oldest obligation is 70 days old
    assert (
        usd_after.overdue_receivables == expected_overdue and usd_after.overdue_customer_count == 1
    )
    assert with_threshold.overdue_threshold_days == 7
