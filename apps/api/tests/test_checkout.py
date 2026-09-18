"""P5-M4: guest checkout, idempotency, provisional representation (D-046, D-049, D-072)."""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from sqlalchemy import func, select
from test_customer_access import HEADER, _issue
from test_invoice_editor import _auth, _catalog, _login, _owner_context, _user
from test_storefront import _publish, _slug

from tawzeevo_api.models import (
    Invoice,
    InvoiceRevision,
    Order,
    OrderAccessReference,
    OwnerNotification,
    SystemUserType,
)

REF = "X-Order-Reference"


def _cart(product_id, quantity="2", name="Guest Grocer", phone="+96170123456"):
    return {
        "contact_name": name,
        "contact_phone": phone,
        "contact_address": "Hamra Street 12, Beirut",
        "notes": "Deliver after 4pm",
        "items": [{"product_id": product_id, "quantity": quantity, "price_basis": "PIECE"}],
    }


def _checkout(client, slug, body, key=None, extra=None):
    headers = {"Idempotency-Key": key or str(uuid4()), **(extra or {})}
    return client.post(f"/api/v1/public/{slug}/checkout", json=body, headers=headers)


def _count(session_factory, model, tenant):
    with session_factory() as db:
        return db.scalar(
            select(func.count()).select_from(model).where(model.tenant_id == UUID(tenant))
        )


def test_guest_checkout_is_atomic_idempotent_and_provisional(client, session_factory, caplog):
    _owner, tenant, token = _owner_context(client, session_factory, "checkout")
    _category, product, _customer = _catalog(client, tenant, token, name="Cedar Water")
    _publish(client, tenant, token, product["id"])
    slug = _slug(session_factory, tenant)
    key = str(uuid4())

    with caplog.at_level(logging.INFO):
        first = _checkout(client, slug, _cart(product["id"]), key)
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["status"] == "RECEIVED" and body["replayed"] is False
    assert body["net_sales"] == "25.0000" and body["item_count"] == 1  # 2 × 12.5000 public price
    assert body["provisional_path"].startswith(f"/{slug}/order#")
    assert first.headers["cache-control"] == "private, no-store"
    reference = body["provisional_path"].split("#", 1)[1]
    assert reference not in caplog.text and reference.split(".")[1] not in caplog.text

    # Exactly one order, one draft invoice with one provisional revision, one reference, one
    # owner notification; no confirmed invoice, no invoice capability, no customer created.
    assert _count(session_factory, Order, tenant) == 1
    assert _count(session_factory, Invoice, tenant) == 1
    assert _count(session_factory, InvoiceRevision, tenant) == 1
    assert _count(session_factory, OrderAccessReference, tenant) == 1
    assert _count(session_factory, OwnerNotification, tenant) == 1
    with session_factory() as db:
        order = db.scalar(select(Order).where(Order.tenant_id == UUID(tenant)))
        invoice = db.scalar(select(Invoice).where(Invoice.tenant_id == UUID(tenant)))
        assert order is not None and invoice is not None
        assert invoice.status.value == "DRAFT" and invoice.official_invoice_number is None
        assert invoice.customer_id is None and invoice.order_id == order.id
        assert order.intended_customer_id is None and order.contact_phone == "+96170123456"
        assert order.invoice_id == invoice.id

    # Same key + same request → the original result; same key + different request → 409.
    replay = _checkout(client, slug, _cart(product["id"]), key)
    assert replay.status_code == 201 and replay.json()["order_id"] == body["order_id"]
    assert replay.json()["replayed"] is True
    conflict = _checkout(client, slug, _cart(product["id"], quantity="3"), key)
    assert (
        conflict.status_code == 409 and conflict.json()["detail"]["code"] == "IDEMPOTENCY_CONFLICT"
    )
    assert _count(session_factory, Order, tenant) == 1
    assert _count(session_factory, OwnerNotification, tenant) == 1

    # The provisional page: customer-safe projection, no store, nothing private.
    page = client.get("/api/v1/public/order", headers={REF: reference})
    assert page.status_code == 200, page.text
    view = page.json()
    assert view["status"] == "RECEIVED" and view["invoice_status"] == "DRAFT"
    assert view["official_number"] is None and view["net_sales"] == "25.0000"
    assert view["contact_name"] == "Guest Grocer" and view["items"][0]["name"] == "Cedar Water"
    assert page.headers["cache-control"] == "no-store"
    assert page.headers.get("x-robots-tag", "").startswith("noindex")
    for forbidden in ("grade", "balance", "debt", "cost", "profit", "supplier", "driver"):
        assert forbidden not in page.text.lower(), forbidden
    for bad in ("", "nonsense", reference[:-1] + "x"):
        r = client.get("/api/v1/public/order", headers={REF: bad})
        assert r.status_code == 404 and r.json()["detail"]["code"] == "ORDER_REFERENCE_UNAVAILABLE"

    # Validation: mandatory fields, invalid phone, unpublished product, missing key.
    assert (
        _checkout(client, slug, {**_cart(product["id"]), "contact_address": " "}).status_code == 422
    )
    assert _checkout(client, slug, _cart(product["id"], phone="12")).status_code == 422
    assert _checkout(client, slug, {**_cart(product["id"]), "items": []}).status_code == 422
    _publish(client, tenant, token, product["id"], published=False)
    hidden = _checkout(client, slug, _cart(product["id"]))
    assert hidden.status_code == 422 and hidden.json()["detail"]["code"] == "PRODUCT_NOT_AVAILABLE"
    _publish(client, tenant, token, product["id"])
    assert (
        client.post(f"/api/v1/public/{slug}/checkout", json=_cart(product["id"])).status_code == 422
    )
    assert _count(session_factory, Order, tenant) == 1


def test_personalized_checkout_carries_only_a_hint_and_phone_never_links(client, session_factory):
    _owner, tenant, token = _owner_context(client, session_factory, "checkout-link")
    _category, product, customer = _catalog(client, tenant, token, name="Cedar Water")
    _publish(client, tenant, token, product["id"])
    slug = _slug(session_factory, tenant)
    assert client.put(
        f"/api/v1/tenants/{tenant}/grade-discounts/A",
        headers=_auth(token),
        json={"discount_percent": "20.00"},
    ).status_code in (200, 201)

    # A guest using the existing customer's phone gets public prices and no link to history.
    guest = _checkout(client, slug, _cart(product["id"], phone=customer["phone"]))
    assert guest.status_code == 201 and guest.json()["net_sales"] == "25.0000"
    with session_factory() as db:
        order = db.scalar(select(Order).where(Order.tenant_id == UUID(tenant)))
        assert order is not None and order.intended_customer_id is None

    # Through the personalized link: customer's current price, and only a hint on the order.
    _link, secret = _issue(client, tenant, token, customer["id"])
    personal = _checkout(client, slug, _cart(product["id"]), extra={HEADER: secret})
    assert personal.status_code == 201, personal.text
    assert personal.json()["net_sales"] == "20.0000"  # 2 × (12.5 − 20 %)
    with session_factory() as db:
        hinted = db.scalar(
            select(Order).where(
                Order.tenant_id == UUID(tenant), Order.intended_customer_id.isnot(None)
            )
        )
        assert hinted is not None
        assert (
            hinted.intended_customer_id == UUID(customer["id"])
            and hinted.intended_assurance == "LINK"
        )
        invoice = db.get(Invoice, hinted.invoice_id)
        assert invoice is not None and invoice.customer_id is None, "the hint never links"
        assert invoice.status.value == "DRAFT" and invoice.official_invoice_number is None
    # A revoked/rotated link at checkout time is simply anonymous; a foreign business's link too.
    _issue(client, tenant, token, customer["id"])  # rotates → old secret dead
    stale = _checkout(client, slug, _cart(product["id"]), extra={HEADER: secret})
    assert stale.status_code == 201 and stale.json()["net_sales"] == "25.0000"
    assert _count(session_factory, OwnerNotification, tenant) == 3


def test_suspended_business_refuses_checkout_but_keeps_provisional_pages(client, session_factory):
    _owner, tenant, token = _owner_context(client, session_factory, "checkout-susp")
    _category, product, _customer = _catalog(client, tenant, token, name="Cedar Water")
    _publish(client, tenant, token, product["id"])
    slug = _slug(session_factory, tenant)
    placed = _checkout(client, slug, _cart(product["id"]))
    assert placed.status_code == 201
    reference = placed.json()["provisional_path"].split("#", 1)[1]
    admin = _user(session_factory, "checkout.admin@example.com", SystemUserType.ADMIN)
    admin_token = _login(client, admin.email)
    assert (
        client.post(
            f"/api/v1/platform/tenants/{tenant}/suspend",
            headers=_auth(admin_token),
            json={"reason": "SUBSCRIPTION_OVERDUE"},
        ).status_code
        == 200
    )
    refused = _checkout(client, slug, _cart(product["id"]))
    assert (
        refused.status_code == 409
        and refused.json()["detail"]["code"] == "STOREFRONT_NOT_ACCEPTING"
    )
    assert client.get("/api/v1/public/order", headers={REF: reference}).status_code == 200
    assert _count(session_factory, Order, tenant) == 1
    # Another business's slug never sees this order; unknown slugs are 404.
    assert client.get("/api/v1/public/no-such-shop/catalog").status_code == 404
