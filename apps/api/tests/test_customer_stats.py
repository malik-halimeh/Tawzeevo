"""Phase 8 P8-M2: customer lifetime statistics (PHASE_08.md D; D-069) — financial per currency,
activity, habits, grade timeline, late payments, cancellations, duplicates never merged,
owner-only and cross-tenant safe."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from test_delivery_tasks import _driver, _get, _post
from test_invoice_editor import (
    _attach_latest_cost,
    _auth,
    _catalog,
    _confirmable_payload,
    _owner_context,
)
from test_procurement import _confirm_invoice

from tawzeevo_api.models import Invoice


def test_lifetime_statistics_reconcile_and_never_merge_duplicates(client, session_factory):
    owner, tenant, token = _owner_context(client, session_factory, "p8life")
    _category, product, customer = _catalog(client, tenant, token, name="Cedar Water")
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    _c2, product2, _cust2 = _catalog(
        client, tenant, token, name="Olive Oil", barcode="5280000000050"
    )
    _attach_latest_cost(session_factory, owner, tenant, product2["id"])
    # A second customer with the same phone is a duplicate the owner chose not to merge.
    twin = client.post(
        f"/api/v1/tenants/{tenant}/customers",
        headers=_auth(token),
        json={"name": "Maya Market (branch)", "phone": customer["phone"], "grade": "B"},
    ).json()
    client.put(
        f"/api/v1/customer-ledger/settings?tenant_id={tenant}",
        headers=_auth(token),
        json={"customer_overdue_threshold_days": 7},
    )

    # Empty: insufficient data, nothing invented.
    empty = _get(client, tenant, token, f"/api/v1/analytics/customers/{customer['id']}")
    assert empty.status_code == 200, empty.text
    assert empty.json()["insufficient_data"] is True and empty.json()["financial"] == []
    assert empty.json()["average_days_between_purchases"] is None

    # Three purchases (grade A → later B), one to the twin, one cancelled.
    first = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "2")
    second_payload = _confirmable_payload(customer["id"], product2["id"])
    second_payload["items"][0]["barcode"] = "5280000000050"  # type: ignore[index]
    second_payload["items"][0]["quantity_expression"] = "3"  # type: ignore[index]
    second_draft = _post(client, tenant, token, "/api/v1/invoices", second_payload).json()
    second = _post(
        client,
        tenant,
        token,
        f"/api/v1/invoices/{second_draft['id']}/confirm",
        {"expected_revision_id": second_draft["current_revision_id"]},
    ).json()
    regraded = client.put(
        f"/api/v1/tenants/{tenant}/customers/{customer['id']}",
        headers=_auth(token),
        json={"grade": "B"},
    )
    assert regraded.status_code == 200, regraded.text
    third = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "1")
    _confirm_invoice(client, tenant, token, twin["id"], product["id"], "9")
    doomed = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "4")
    _post(
        client,
        tenant,
        token,
        f"/api/v1/invoices/{doomed['id']}/cancel",
        {"idempotency_key": str(uuid4()), "reason": "x"},
    )
    # Space the confirmations out and make the first charge old enough to be paid late.
    with session_factory() as db:
        now = datetime.now(UTC)
        for invoice_id, days_ago in ((first["id"], 40), (second["id"], 20), (third["id"], 0)):
            row = db.get(Invoice, UUID(invoice_id))
            assert row is not None
            row.confirmed_at = now - timedelta(days=days_ago)
        db.commit()
    # A receipt dated 10 days after the charge, allocated oldest-first: settled late (> 7 days).
    receipt = _post(
        client,
        tenant,
        token,
        "/api/v1/payments/customer-receipts",
        {
            "idempotency_key": str(uuid4()),
            "customer_id": customer["id"],
            "amount": first["net_sales"],
            "currency": "USD",
            "paid_at": (datetime.now(UTC) + timedelta(days=10)).isoformat(),
        },
    )
    assert receipt.status_code == 201, receipt.text

    stats = _get(client, tenant, token, f"/api/v1/analytics/customers/{customer['id']}").json()
    assert stats["insufficient_data"] is False and stats["invoice_count"] == 3
    assert stats["cancelled_invoices"] == 1 and stats["current_grade"] == "B"
    usd = stats["financial"][0]
    total = Decimal(first["net_sales"]) + Decimal(second["net_sales"]) + Decimal(third["net_sales"])
    assert Decimal(usd["total_purchased"]) == total  # the twin's 9 pieces are not here
    assert usd["invoice_count"] == 3
    assert Decimal(usd["largest_invoice"]) == max(
        Decimal(first["net_sales"]), Decimal(second["net_sales"]), Decimal(third["net_sales"])
    )
    assert Decimal(usd["average_invoice"]) == (total / 3).quantize(Decimal("0.0001"))
    assert usd["total_receipts"] == first["net_sales"]
    assert Decimal(usd["outstanding"]) == total - Decimal(first["net_sales"])
    assert Decimal(usd["total_discounts"]) > 0 and Decimal(usd["total_markups"]) > 0
    assert stats["first_purchase_at"] < stats["latest_purchase_at"]
    assert Decimal(stats["average_days_between_purchases"]) == Decimal("20.0000")
    assert Decimal(stats["purchases_per_month"]) > 0
    assert stats["late_payment_count"] == 1 and stats["overdue_threshold_days"] == 7
    assert stats["cancellation_requests"] == 0
    # Habits: products/categories ranked by value within the currency, at most five each.
    assert [row["name"] for row in stats["top_products"]][:2] == sorted(
        [row["name"] for row in stats["top_products"]][:2],
        key=lambda n: -Decimal(next(r["value"] for r in stats["top_products"] if r["name"] == n)),
    )
    assert {row["name"] for row in stats["top_products"]} == {"Cedar Water", "Olive Oil"}
    assert stats["top_categories"][0]["name"] == "Beverages"
    assert len(stats["monthly_spend"]) >= 1 and stats["monthly_spend"][0]["currency"] == "USD"
    # Grade timeline from the sale-time snapshots: A on the first purchases, then B.
    assert [point["grade"] for point in stats["grade_timeline"]] == ["A", "B"]

    # The twin reports only its own single purchase; nobody merged anything.
    twin_stats = _get(client, tenant, token, f"/api/v1/analytics/customers/{twin['id']}").json()
    assert twin_stats["invoice_count"] == 1 and twin_stats["current_grade"] == "B"
    assert twin_stats["grade_timeline"] == [{"at": twin_stats["first_purchase_at"], "grade": "B"}]

    # Owner-only and tenant-scoped.
    _d, driver_token, _m = _driver(client, session_factory, tenant, "driver-p8life@example.com")
    assert (
        _get(
            client, tenant, driver_token, f"/api/v1/analytics/customers/{customer['id']}"
        ).status_code
        == 403
    )
    _o, other_tenant, other_token = _owner_context(client, session_factory, "p8life2")
    assert (
        _get(
            client, other_tenant, other_token, f"/api/v1/analytics/customers/{customer['id']}"
        ).status_code
        == 404
    )
