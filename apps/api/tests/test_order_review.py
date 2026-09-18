"""P5-M5: owner review, explicit customer link, confirmation through Phase 3, delivery date,
cancellation requests and decisions, one-owner/zero-driver operation (PHASE_05.md G–J)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from test_checkout import REF, _cart, _checkout
from test_customer_access import HEADER, _issue
from test_invoice_editor import _attach_latest_cost, _auth, _catalog, _owner_context
from test_storefront import _publish, _slug

from tawzeevo_api.models import (
    Customer,
    CustomerLedgerEntry,
    DeliveryReminder,
    Invoice,
    InvoiceRevision,
    OwnerNotification,
)


def _place(client, session_factory, owner, tenant, token, product, **kwargs):
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    slug = _slug(session_factory, tenant)
    placed = _checkout(client, slug, _cart(product["id"], **kwargs))
    assert placed.status_code == 201, placed.text
    return placed.json(), placed.json()["provisional_path"].split("#", 1)[1]


def _order(client, tenant, token, order_id):
    r = client.get(f"/api/v1/tenants/{tenant}/orders/{order_id}", headers=_auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def test_owner_reviews_links_explicitly_and_confirms_through_phase_3(client, session_factory):
    owner, tenant, token = _owner_context(client, session_factory, "review")
    _category, product, customer = _catalog(client, tenant, token, name="Cedar Water")
    _publish(client, tenant, token, product["id"])
    assert client.put(
        f"/api/v1/tenants/{tenant}/grade-discounts/A",
        headers=_auth(token),
        json={"discount_percent": "20.00"},
    ).status_code in (200, 201)
    # A guest checkout using the existing customer's phone: candidates listed, nothing linked.
    placed, reference = _place(
        client, session_factory, owner, tenant, token, product, phone=customer["phone"]
    )
    inbox = client.get(f"/api/v1/tenants/{tenant}/orders", headers=_auth(token)).json()["orders"]
    assert [row["id"] for row in inbox] == [placed["order_id"]]
    assert inbox[0]["status"] == "RECEIVED" and inbox[0]["linked_customer_id"] is None
    detail = _order(client, tenant, token, placed["order_id"])
    assert [c["id"] for c in detail["candidates"]] == [customer["id"]]
    assert detail["candidates"][0]["is_hint"] is False
    notes = client.get(f"/api/v1/tenants/{tenant}/notifications", headers=_auth(token)).json()
    assert notes["unread"] == 1 and notes["notifications"][0]["kind"] == "ORDER_RECEIVED"

    # Confirming before linking is refused; the price stays public until the explicit link.
    with session_factory() as db:
        order_invoice = db.scalar(select(Invoice).where(Invoice.tenant_id == UUID(tenant)))
        assert order_invoice is not None and order_invoice.customer_id is None
        first_revision = order_invoice.current_revision_id
    refused = client.post(
        f"/api/v1/tenants/{tenant}/orders/{placed['order_id']}/confirm",
        headers=_auth(token),
        json={"expected_revision_id": str(first_revision)},
    )
    assert (
        refused.status_code == 409 and refused.json()["detail"]["code"] == "ORDER_CUSTOMER_REQUIRED"
    )

    linked = client.post(
        f"/api/v1/tenants/{tenant}/orders/{placed['order_id']}/link-customer",
        headers=_auth(token),
        json={"customer_id": customer["id"]},
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["order"]["linked_customer_id"] == customer["id"]
    with session_factory() as db:
        order_invoice = db.scalar(select(Invoice).where(Invoice.tenant_id == UUID(tenant)))
        assert order_invoice is not None and order_invoice.customer_id == UUID(customer["id"])
        revision = db.get(InvoiceRevision, order_invoice.current_revision_id)
        assert revision is not None and revision.server_revision_number == 2
        assert revision.net_sales == 20  # grade A discount applied only after the explicit link
        current_revision = revision.id
    # Delivery date is impossible before confirmation.
    early = client.put(
        f"/api/v1/tenants/{tenant}/orders/{placed['order_id']}/delivery-date",
        headers=_auth(token),
        json={"delivery_date": date.today().isoformat()},
    )
    assert early.status_code == 409 and early.json()["detail"]["code"] == "ORDER_NOT_CONFIRMED"

    confirmed = client.post(
        f"/api/v1/tenants/{tenant}/orders/{placed['order_id']}/confirm",
        headers=_auth(token),
        json={"expected_revision_id": str(current_revision)},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["order"]["status"] == "CONFIRMED"
    with session_factory() as db:
        order_invoice = db.scalar(select(Invoice).where(Invoice.tenant_id == UUID(tenant)))
        assert order_invoice is not None
        assert order_invoice.status.value == "CONFIRMED"
        assert (
            order_invoice.official_invoice_number
            and order_invoice.official_invoice_number.endswith("-000001")
        )
        charge = db.scalar(
            select(func.sum(CustomerLedgerEntry.signed_amount)).where(
                CustomerLedgerEntry.tenant_id == UUID(tenant),
                CustomerLedgerEntry.customer_id == UUID(customer["id"]),
            )
        )
        assert charge == 20, "one Phase 3 charge for the confirmed order"
    # Customer's page reflects confirmation; the official number is now visible there.
    page = client.get("/api/v1/public/order", headers={REF: reference}).json()
    assert page["status"] == "CONFIRMED" and page["official_number"].endswith("-000001")

    # Delivery date after confirmation: tenant-local date, UTC reminder, no new revision.
    tomorrow = (datetime.now(UTC) + timedelta(days=2)).date()
    dated = client.put(
        f"/api/v1/tenants/{tenant}/orders/{placed['order_id']}/delivery-date",
        headers=_auth(token),
        json={"delivery_date": tomorrow.isoformat()},
    )
    assert (
        dated.status_code == 200 and dated.json()["order"]["delivery_date"] == tomorrow.isoformat()
    )
    with session_factory() as db:
        reminder = db.scalar(
            select(DeliveryReminder).where(DeliveryReminder.tenant_id == UUID(tenant))
        )
        assert reminder is not None and reminder.status == "SCHEDULED"
        assert reminder.remind_at.astimezone(UTC).hour == 6, (
            "09:00 Beirut (UTC+3) executes at 06:00 UTC"
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(InvoiceRevision)
                .where(InvoiceRevision.tenant_id == UUID(tenant))
            )
            == 2
        )
    # Rescheduling updates the same reminder; the customer sees the date; the past is refused.
    later = tomorrow + timedelta(days=1)
    client.put(
        f"/api/v1/tenants/{tenant}/orders/{placed['order_id']}/delivery-date",
        headers=_auth(token),
        json={"delivery_date": later.isoformat()},
    )
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(DeliveryReminder)) == 1
        assert db.scalar(select(DeliveryReminder)).delivery_date == later
    assert (
        client.get("/api/v1/public/order", headers={REF: reference}).json()["delivery_date"]
        == later.isoformat()
    )
    past = client.put(
        f"/api/v1/tenants/{tenant}/orders/{placed['order_id']}/delivery-date",
        headers=_auth(token),
        json={"delivery_date": "2020-01-01"},
    )
    assert past.status_code == 422


def test_hint_from_personalized_link_is_shown_but_never_auto_linked_and_snapshot_creates_customer(
    client, session_factory
):
    owner, tenant, token = _owner_context(client, session_factory, "review-hint")
    _category, product, customer = _catalog(client, tenant, token, name="Cedar Water")
    _publish(client, tenant, token, product["id"])
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    slug = _slug(session_factory, tenant)
    _link, secret = _issue(client, tenant, token, customer["id"])
    placed = _checkout(
        client,
        slug,
        _cart(product["id"], name="Abu Ahmad", phone="+96170123900"),
        extra={HEADER: secret},
    ).json()
    detail = _order(client, tenant, token, placed["order_id"])
    assert detail["order"]["intended_customer_id"] == customer["id"]
    assert detail["order"]["intended_assurance"] == "LINK"
    assert detail["order"]["linked_customer_id"] is None
    assert [c["is_hint"] for c in detail["candidates"]] == [True]

    # The owner may ignore the hint and create a new customer from the contact snapshot.
    created = client.post(
        f"/api/v1/tenants/{tenant}/orders/{placed['order_id']}/link-customer",
        headers=_auth(token),
        json={"create_from_snapshot": True, "grade": "B"},
    )
    assert created.status_code == 200, created.text
    new_id = created.json()["order"]["linked_customer_id"]
    assert new_id != customer["id"]
    with session_factory() as db:
        new_customer = db.get(Customer, UUID(new_id))
        assert new_customer is not None and new_customer.name == "Abu Ahmad"
        assert new_customer.phone == "+96170123900" and new_customer.grade.value == "B"
    # Both choices are refused for a non-received order and without a choice.
    assert (
        client.post(
            f"/api/v1/tenants/{tenant}/orders/{placed['order_id']}/link-customer",
            headers=_auth(token),
            json={},
        ).status_code
        == 422
    )
    declined = client.post(
        f"/api/v1/tenants/{tenant}/orders/{placed['order_id']}/decline",
        headers=_auth(token),
        json={"note": "Out of the delivery area"},
    )
    assert declined.status_code == 200 and declined.json()["order"]["status"] == "DECLINED"
    with session_factory() as db:
        invoice = db.scalar(select(Invoice).where(Invoice.tenant_id == UUID(tenant)))
        assert invoice is not None and invoice.status.value == "CANCELLED"
        assert db.scalar(select(func.count()).select_from(CustomerLedgerEntry)) == 0, (
            "a declined draft never touches the ledger"
        )
    assert (
        client.post(
            f"/api/v1/tenants/{tenant}/orders/{placed['order_id']}/confirm",
            headers=_auth(token),
            json={"expected_revision_id": str(UUID(int=0))},
        ).status_code
        == 409
    )
    page = client.get(
        "/api/v1/public/order", headers={REF: placed["provisional_path"].split("#")[1]}
    ).json()
    assert page["status"] == "DECLINED" and page["decision_note"] == "Out of the delivery area"


def test_cancellation_request_and_owner_decision_reverse_confirmed_sales(client, session_factory):
    owner, tenant, token = _owner_context(client, session_factory, "review-cancel")
    _category, product, customer = _catalog(client, tenant, token, name="Cedar Water")
    _publish(client, tenant, token, product["id"])
    placed, reference = _place(
        client, session_factory, owner, tenant, token, product, phone=customer["phone"]
    )
    path = f"/api/v1/tenants/{tenant}/orders/{placed['order_id']}"
    client.post(f"{path}/link-customer", headers=_auth(token), json={"customer_id": customer["id"]})
    with session_factory() as db:
        invoice = db.scalar(select(Invoice).where(Invoice.tenant_id == UUID(tenant)))
        revision_id = invoice.current_revision_id
    assert (
        client.post(
            f"{path}/confirm", headers=_auth(token), json={"expected_revision_id": str(revision_id)}
        ).status_code
        == 200
    )

    # Customer requests cancellation through the provisional reference; only one pending.
    asked = client.post(
        "/api/v1/public/order/cancellation-request",
        headers={REF: reference},
        json={"reason": "Ordered by mistake"},
    )
    assert asked.status_code == 201, asked.text
    again = client.post(
        "/api/v1/public/order/cancellation-request",
        headers={REF: reference},
        json={"reason": "again"},
    )
    assert again.status_code == 201 and again.json()["id"] == asked.json()["id"]
    assert (
        client.post(
            "/api/v1/public/order/cancellation-request", headers={REF: "nope"}, json={}
        ).status_code
        == 404
    )
    assert (
        client.get("/api/v1/public/order", headers={REF: reference}).json()["cancellation"]
        == "PENDING"
    )
    with session_factory() as db:
        kinds = sorted(
            db.scalars(
                select(OwnerNotification.kind).where(OwnerNotification.tenant_id == UUID(tenant))
            )
        )
        assert kinds == ["CANCELLATION_REQUESTED", "ORDER_RECEIVED"]

    # Owner rejects: history kept, order still confirmed; a new request is possible.
    rejected = client.post(
        f"/api/v1/tenants/{tenant}/orders/cancellation-requests/{asked.json()['id']}/decide",
        headers=_auth(token),
        json={"approve": False, "note": "Already on the way"},
    )
    assert rejected.status_code == 200 and rejected.json()["status"] == "REJECTED"
    assert (
        client.post(
            f"/api/v1/tenants/{tenant}/orders/cancellation-requests/{asked.json()['id']}/decide",
            headers=_auth(token),
            json={"approve": True},
        ).status_code
        == 409
    )
    assert _order(client, tenant, token, placed["order_id"])["order"]["status"] == "CONFIRMED"
    second = client.post(
        "/api/v1/public/order/cancellation-request",
        headers={REF: reference},
        json={"reason": "Please cancel"},
    )
    assert second.status_code == 201 and second.json()["id"] != asked.json()["id"]

    # Owner approves: Phase 3 cancellation accounting reverses the charge; order CANCELLED.
    approved = client.post(
        f"/api/v1/tenants/{tenant}/orders/cancellation-requests/{second.json()['id']}/decide",
        headers=_auth(token),
        json={"approve": True, "note": "Cancelled at customer request"},
    )
    assert approved.status_code == 200 and approved.json()["status"] == "APPROVED"
    detail = _order(client, tenant, token, placed["order_id"])
    assert detail["order"]["status"] == "CANCELLED"
    assert [r["status"] for r in detail["cancellation_requests"]] == ["APPROVED", "REJECTED"]
    with session_factory() as db:
        invoice = db.scalar(select(Invoice).where(Invoice.tenant_id == UUID(tenant)))
        assert invoice.status.value == "CANCELLED"
        balance = db.scalar(
            select(func.sum(CustomerLedgerEntry.signed_amount)).where(
                CustomerLedgerEntry.tenant_id == UUID(tenant)
            )
        )
        assert balance == 0, "charge reversed, history preserved"
        assert db.scalar(select(func.count()).select_from(CustomerLedgerEntry)) == 2
    page = client.get("/api/v1/public/order", headers={REF: reference}).json()
    assert page["status"] == "CANCELLED" and page["cancellation"] == "APPROVED"
    assert (
        client.post(
            "/api/v1/public/order/cancellation-request", headers={REF: reference}, json={}
        ).status_code
        == 409
    )
    # Nothing here exposes delivery tracking or a driver; the customer never wrote order state.
    assert "driver" not in page and "tracking" not in str(page)
    # Notifications can be marked read.
    note = client.get(f"/api/v1/tenants/{tenant}/notifications", headers=_auth(token)).json()[
        "notifications"
    ][0]
    read = client.post(
        f"/api/v1/tenants/{tenant}/notifications/{note['id']}/read", headers=_auth(token)
    )
    assert read.status_code == 200 and read.json()["read_at"]
    assert (
        client.get(f"/api/v1/tenants/{tenant}/notifications", headers=_auth(token)).json()["unread"]
        == 2
    )  # arrival + 2 requests, 1 read
