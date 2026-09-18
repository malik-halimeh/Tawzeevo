"""Guest checkout: RECEIVED order, draft invoice, provisional reference, one owner notification.

PHASE_05.md E/F (D-046, D-049, D-072). No account is needed; name, phone and address are an
immutable contact snapshot. A valid personalized context adds `intended_customer_id` as a hint
for owner review — it never links, prices as final, or confirms. The whole checkout is one
transaction keyed by the client's `Idempotency-Key`: the same key with the same request returns
the original result, a different request under the same key is a 409. Nothing here creates
confirmed financial truth; the owner's review (P5-M5) does, through the Phase 3 services.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    CheckoutIdempotency,
    Customer,
    Invoice,
    InvoiceRevision,
    InvoiceRevisionItem,
    InvoiceStatus,
    Order,
    OrderAccessReference,
    OwnerNotification,
    Tenant,
    TenantProduct,
    TenantStatus,
)
from tawzeevo_api.phone import InvalidPhoneNumberError, normalize_phone
from tawzeevo_api.repositories.tenancy import commit_and_restore_tenant_scope, set_tenant_scope
from tawzeevo_api.schemas.checkout import (
    CheckoutRequest,
    CheckoutResponse,
    ProvisionalItem,
    ProvisionalOrderResponse,
)
from tawzeevo_api.schemas.invoice_editor import InvoiceEditorItemRequest
from tawzeevo_api.services import invoice_editor
from tawzeevo_api.services.customer_access import CustomerContext
from tawzeevo_api.services.storefront import resolve_slug

PROVISIONAL_REFERENCE_TTL = timedelta(hours=72)
PROVISIONAL_PATH = "/order"  # storefront: /{slug}/order#<reference>
TOKEN_PATTERN = re.compile(r"[a-f0-9]{32}\.[A-Za-z0-9_-]{43}")
MAX_ITEMS = 100


def _fingerprint(request: CheckoutRequest, context: CustomerContext | None) -> str:
    payload = request.model_dump(mode="json")
    payload["intended_customer_id"] = str(context.customer_id) if context else None
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _guest_customer(name: str, phone: str, address: str) -> Customer:
    """A transient, never-persisted customer used only for public-price calculation."""
    return Customer(
        id=uuid4(), name=name, phone=phone, phone_raw=phone, address=address, grade=None
    )


def checkout(
    db: Session,
    slug: str,
    request: CheckoutRequest,
    idempotency_key: UUID,
    context: CustomerContext | None,
    *,
    fuzzy_threshold: Decimal,
) -> CheckoutResponse:
    resolution = resolve_slug(db, slug)
    tenant = db.get(Tenant, resolution.tenant_id)
    if tenant is None or tenant.status is TenantStatus.CLOSED:
        raise AppError(404, "STOREFRONT_NOT_FOUND", "No storefront at this address")
    if tenant.status is not TenantStatus.ACTIVE:
        raise AppError(409, "STOREFRONT_NOT_ACCEPTING", "This shop is not taking orders right now")
    set_tenant_scope(db, tenant.id)
    if context is not None and context.tenant_id != tenant.id:
        context = None  # a link for another business never attaches to this order
    try:
        phone = normalize_phone(request.contact_phone)
    except InvalidPhoneNumberError as exc:
        raise AppError(422, "INVALID_PHONE", "Contact phone is invalid") from exc
    if not request.items or len(request.items) > MAX_ITEMS:
        raise AppError(422, "ITEMS_REQUIRED", "Add at least one item")

    # One checkout per key: serialize replays and compare the semantic request (fingerprint).
    db.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": idempotency_key.int & ((1 << 63) - 1)},
    )
    fingerprint = _fingerprint(request, context)
    existing = db.get(CheckoutIdempotency, (tenant.id, idempotency_key))
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise AppError(
                409, "IDEMPOTENCY_CONFLICT", "This idempotency key was used for a different order"
            )
        return CheckoutResponse.model_validate({**existing.response, "replayed": True})

    pricing_customer = (
        db.get(Customer, context.customer_id)
        if context is not None
        else _guest_customer(request.contact_name, phone, request.contact_address)
    )
    assert pricing_customer is not None
    item_requests: list[InvoiceEditorItemRequest] = []
    for line in request.items:
        product = db.scalar(
            select(TenantProduct).where(
                TenantProduct.id == line.product_id,
                TenantProduct.tenant_id == tenant.id,
                TenantProduct.is_published.is_(True),
            )
        )
        if product is None:
            raise AppError(422, "PRODUCT_NOT_AVAILABLE", "A product in the cart is not available")
        item_requests.append(
            InvoiceEditorItemRequest(
                product_id=product.id,
                quantity_expression=str(line.quantity),
                price_basis=line.price_basis,
            )
        )
    currency = {
        db.scalar(select(TenantProduct.currency).where(TenantProduct.id == item.product_id))
        for item in item_requests
    }
    if len(currency) != 1:
        raise AppError(422, "CURRENCY_MISMATCH", "All items must share one currency")
    order_currency = currency.pop()
    assert order_currency is not None
    items = invoice_editor._prepare_items(
        db, tenant.id, pricing_customer, order_currency, item_requests, fuzzy_threshold
    )
    subtotal, discount_total, markup_total, net_sales = invoice_editor._totals(items, "0", "0")

    now = datetime.now(UTC)
    order = Order(
        id=uuid4(),
        tenant_id=tenant.id,
        status="RECEIVED",
        contact_name=request.contact_name.strip(),
        contact_phone=phone,
        contact_phone_raw=request.contact_phone.strip(),
        contact_address=request.contact_address.strip(),
        notes=(request.notes or "").strip() or None,
        currency=order_currency,
        intended_customer_id=context.customer_id if context else None,
        intended_assurance=context.assurance.value if context else None,
        created_at=now,
    )
    db.add(order)
    db.flush()
    # Draft invoice + first provisional revision (D-033: one order → one header). The customer
    # stays unlinked until the owner resolves it; the hint lives on the order, not the invoice.
    invoice_id, revision_id = uuid4(), uuid4()
    invoice = Invoice(
        id=invoice_id,
        tenant_id=tenant.id,
        customer_id=None,
        order_id=order.id,
        current_revision_id=revision_id,
        status=InvoiceStatus.DRAFT,
        created_by_user_id=None,
        updated_by_user_id=None,
    )
    revision = InvoiceRevision(
        id=revision_id,
        tenant_id=tenant.id,
        invoice_id=invoice_id,
        client_command_id=idempotency_key,
        predecessor_revision_id=None,
        server_revision_number=1,
        pricing_version="pricing-v1",
        currency=order_currency,
        customer_id=None,
        customer_snapshot={
            "name": order.contact_name,
            "phone": order.contact_phone,
            "address": order.contact_address,
            "source": "storefront_checkout",
        },
        prior_balance_snapshot=Decimal("0"),
        subtotal=subtotal,
        discount_total=discount_total,
        markup_total=markup_total,
        net_sales=net_sales,
        amount_due_display=invoice_editor.stored_money(net_sales),
        created_by_user_id=None,
        reason="storefront guest checkout",
    )
    db.add(invoice)
    db.flush()
    db.add(revision)
    invoice_editor._write_revision_items(db, tenant.id, revision_id, items)
    order.invoice_id = invoice_id
    raw = f"{tenant.id.hex}.{secrets.token_urlsafe(32)}"
    db.add(
        OrderAccessReference(
            id=uuid4(),
            tenant_id=tenant.id,
            order_id=order.id,
            token_sha256=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=now + PROVISIONAL_REFERENCE_TTL,
        )
    )
    # D-049: exactly one in-app owner notification per accepted checkout.
    db.add(
        OwnerNotification(id=uuid4(), tenant_id=tenant.id, kind="ORDER_RECEIVED", order_id=order.id)
    )
    response = CheckoutResponse(
        order_id=order.id,
        status="RECEIVED",
        currency=order_currency,
        net_sales=net_sales,
        item_count=len(items),
        provisional_path=f"/{tenant.slug}{PROVISIONAL_PATH}#{raw}",
        replayed=False,
    )
    db.add(
        CheckoutIdempotency(
            tenant_id=tenant.id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            order_id=order.id,
            response=json.loads(response.model_dump_json()),
        )
    )
    commit_and_restore_tenant_scope(db, tenant.id)
    return response


# ---------------------------------------------------------------------------------------------
# Provisional representation (D-046)
# ---------------------------------------------------------------------------------------------


def _unavailable() -> AppError:
    return AppError(404, "ORDER_REFERENCE_UNAVAILABLE", "This order page is not available")


def provisional_order(db: Session, raw: str | None) -> ProvisionalOrderResponse:
    """Customer-safe projection through the provisional reference: contact snapshot, current
    items/totals, status, later the delivery date and cancellation message. Never debt, history,
    grades, costs, driver data or other orders (PHASE_05.md F)."""
    if not raw or not TOKEN_PATTERN.fullmatch(raw):
        raise _unavailable()
    tenant_id = UUID(hex=raw[:32])
    set_tenant_scope(db, tenant_id)
    reference = db.scalar(
        select(OrderAccessReference).where(
            OrderAccessReference.tenant_id == tenant_id,
            OrderAccessReference.token_sha256 == hashlib.sha256(raw.encode()).hexdigest(),
            OrderAccessReference.revoked_at.is_(None),
            OrderAccessReference.expires_at > datetime.now(UTC),
        )
    )
    if reference is None:
        raise _unavailable()
    tenant = db.get(Tenant, tenant_id)
    order = db.get(Order, reference.order_id)
    if tenant is None or order is None or tenant.status is TenantStatus.CLOSED:
        raise _unavailable()
    invoice = db.get(Invoice, order.invoice_id) if order.invoice_id else None
    revision = db.get(InvoiceRevision, invoice.current_revision_id) if invoice else None
    items: list[Any] = []
    if revision is not None:
        items = list(
            db.scalars(
                select(InvoiceRevisionItem)
                .where(
                    InvoiceRevisionItem.tenant_id == tenant_id,
                    InvoiceRevisionItem.invoice_revision_id == revision.id,
                )
                .order_by(InvoiceRevisionItem.line_number)
            )
        )
    return ProvisionalOrderResponse(
        business_name=tenant.name,
        status=order.status,
        contact_name=order.contact_name,
        contact_phone=order.contact_phone,
        contact_address=order.contact_address,
        notes=order.notes,
        currency=order.currency,
        created_at=order.created_at,
        invoice_status=invoice.status.value if invoice else None,
        official_number=invoice.official_invoice_number if invoice else None,
        subtotal=revision.subtotal if revision else Decimal("0"),
        discount=revision.discount_total if revision else Decimal("0"),
        markup=revision.markup_total if revision else Decimal("0"),
        net_sales=revision.net_sales if revision else Decimal("0"),
        items=[
            ProvisionalItem(
                name=item.product_name,
                quantity=item.quantity,
                unit=item.price_basis.value,
                pieces_per_box=item.pieces_per_box,
                unit_price=item.effective_unit_price,
                total=item.line_total,
            )
            for item in items
        ],
        decision_note=order.decision_note,
    )
