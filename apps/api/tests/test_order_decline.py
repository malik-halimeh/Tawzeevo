"""F-03: an owner's decision on a received storefront order is one transaction.

A public order has no customer until the owner links one. Declining it (or approving the
customer's cancellation request) must close its draft invoice and record the decision together,
never leave a cancelled invoice behind a RECEIVED order, and never need a customer to do so.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import func, select
from test_checkout import REF, _cart, _checkout
from test_customer_access import HEADER, _issue
from test_invoice_editor import _auth, _catalog, _owner_context
from test_storefront import _publish, _slug

from tawzeevo_api.models import AuditEvent, CustomerLedgerEntry, Invoice, Order
from tawzeevo_api.services import orders as order_service


def _business(client, session_factory, suffix):
    _owner, tenant, token = _owner_context(client, session_factory, suffix)
    _category, product, customer = _catalog(client, tenant, token, name="Cedar Water")
    _publish(client, tenant, token, product["id"])
    return tenant, token, product, customer, _slug(session_factory, tenant)


def _awaiting(client, tenant, token):
    r = client.get(
        f"/api/v1/tenants/{tenant}/orders", params={"status": "RECEIVED"}, headers=_auth(token)
    )
    assert r.status_code == 200, r.text
    return [row["id"] for row in r.json()["orders"]]


def _state(session_factory, order_id):
    with session_factory() as db:
        order = db.get(Order, UUID(order_id))
        assert order is not None
        invoice = db.get(Invoice, order.invoice_id)
        assert invoice is not None
        cancellations = db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.entity_id == invoice.id, AuditEvent.action.like("%invoice_cancelled"))
        )
        return order.status, invoice.status.value, order.linked_customer_id, cancellations


def test_public_unlinked_order_is_declined_in_one_step_and_leaves_the_awaiting_set(
    client, session_factory
):
    tenant, token, product, _customer, slug = _business(client, session_factory, "decline-pub")
    placed = _checkout(client, slug, _cart(product["id"])).json()
    order_id = placed["order_id"]
    assert _state(session_factory, order_id)[:3] == ("RECEIVED", "DRAFT", None)
    assert _awaiting(client, tenant, token) == [order_id]

    declined = client.post(
        f"/api/v1/tenants/{tenant}/orders/{order_id}/decline",
        headers=_auth(token),
        json={"note": "Outside the delivery area"},
    )
    assert declined.status_code == 200, declined.text
    body = declined.json()
    assert body["order"]["status"] == "DECLINED" and body["order"]["decided_at"]
    assert body["order"]["linked_customer_id"] is None, "no customer is invented to decline"
    assert body["invoice"]["status"] == "CANCELLED"
    assert _state(session_factory, order_id) == ("DECLINED", "CANCELLED", None, 1)
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(CustomerLedgerEntry)) == 0
    assert _awaiting(client, tenant, token) == []
    page = client.get(
        "/api/v1/public/order", headers={REF: placed["provisional_path"].split("#")[1]}
    )
    assert page.json()["status"] == "DECLINED"
    assert page.json()["decision_note"] == "Outside the delivery area"

    # A second decline is refused by the order state machine and changes nothing.
    again = client.post(
        f"/api/v1/tenants/{tenant}/orders/{order_id}/decline", headers=_auth(token), json={}
    )
    assert again.status_code == 409 and again.json()["detail"]["code"] == "ORDER_NOT_REVIEWABLE"
    assert _state(session_factory, order_id) == ("DECLINED", "CANCELLED", None, 1)


def test_personalized_linked_order_still_declines(client, session_factory):
    tenant, token, product, customer, slug = _business(client, session_factory, "decline-link")
    _link, secret = _issue(client, tenant, token, customer["id"])
    placed = _checkout(client, slug, _cart(product["id"]), extra={HEADER: secret}).json()
    order_id = placed["order_id"]
    assert _state(session_factory, order_id)[2] == UUID(customer["id"])
    declined = client.post(
        f"/api/v1/tenants/{tenant}/orders/{order_id}/decline", headers=_auth(token), json={}
    )
    assert declined.status_code == 200, declined.text
    assert _state(session_factory, order_id) == ("DECLINED", "CANCELLED", UUID(customer["id"]), 1)
    assert _awaiting(client, tenant, token) == []


def test_a_failure_after_the_cancellation_rolls_the_whole_decision_back(
    client, session_factory, monkeypatch
):
    tenant, token, product, _customer, slug = _business(client, session_factory, "decline-atomic")
    order_id = _checkout(client, slug, _cart(product["id"])).json()["order_id"]

    def broken_clock():
        raise RuntimeError("simulated failure after the invoice was cancelled")

    monkeypatch.setattr(order_service, "_now", broken_clock)
    with pytest.raises(RuntimeError):
        client.post(
            f"/api/v1/tenants/{tenant}/orders/{order_id}/decline", headers=_auth(token), json={}
        )
    assert _state(session_factory, order_id) == ("RECEIVED", "DRAFT", None, 0)
    assert _awaiting(client, tenant, token) == [order_id]


def test_an_order_left_behind_a_cancelled_invoice_can_still_be_declined(client, session_factory):
    """Orders stuck by the earlier defect (invoice CANCELLED, order RECEIVED) are recoverable:
    the cancellation is not repeated, the decision is recorded."""
    tenant, token, product, _customer, slug = _business(client, session_factory, "decline-stuck")
    order_id = _checkout(client, slug, _cart(product["id"])).json()["order_id"]
    with session_factory() as db:
        order = db.get(Order, UUID(order_id))
        assert order is not None
        invoice = db.get(Invoice, order.invoice_id)
        assert invoice is not None
        invoice.status = type(invoice.status).CANCELLED
        db.commit()
    declined = client.post(
        f"/api/v1/tenants/{tenant}/orders/{order_id}/decline", headers=_auth(token), json={}
    )
    assert declined.status_code == 200, declined.text
    assert _state(session_factory, order_id)[:2] == ("DECLINED", "CANCELLED")
    assert _awaiting(client, tenant, token) == []


def test_approving_a_cancellation_request_on_an_unlinked_received_order(client, session_factory):
    tenant, token, product, _customer, slug = _business(client, session_factory, "decline-req")
    placed = _checkout(client, slug, _cart(product["id"])).json()
    order_id = placed["order_id"]
    asked = client.post(
        "/api/v1/public/order/cancellation-request",
        headers={REF: placed["provisional_path"].split("#")[1]},
        json={"reason": "Ordered by mistake"},
    )
    assert asked.status_code == 201, asked.text
    decided = client.post(
        f"/api/v1/tenants/{tenant}/orders/cancellation-requests/{asked.json()['id']}/decide",
        headers=_auth(token),
        json={"approve": True, "note": None},
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "APPROVED"
    assert _state(session_factory, order_id) == ("CANCELLED", "CANCELLED", None, 1)
    assert _awaiting(client, tenant, token) == []
