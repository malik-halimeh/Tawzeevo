"""Guest checkout: RECEIVED order, draft invoice, provisional reference, one owner notification.

PHASE_05.md E/F (D-046, D-049, D-072, D-090). No account is needed; name, phone and address are
an immutable contact snapshot. A granted personalized context makes the order that customer's
(D-090): the customer comes only from the server-resolved link, never from the browser, and the
owner still confirms or declines before anything financial happens. The whole checkout is one
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
    OrderCancellationRequest,
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
    customer = db.get(Customer, context.customer_id) if context is not None else None
    if customer is not None:
        # D-090: identity comes from the resolved link only; browser name/phone are ignored.
        contact_name = customer.name
        phone = customer.phone
        phone_raw = customer.phone_raw or customer.phone
        contact_address = request.contact_address or (customer.address or "").strip()
        if not contact_address:
            raise AppError(422, "CONTACT_ADDRESS_REQUIRED", "Enter a delivery address")
    else:
        context = None
        if not (request.contact_name and request.contact_phone and request.contact_address):
            raise AppError(422, "CONTACT_REQUIRED", "Name, phone and address are required")
        try:
            phone = normalize_phone(request.contact_phone)
        except InvalidPhoneNumberError as exc:
            raise AppError(422, "INVALID_PHONE", "Contact phone is invalid") from exc
        contact_name = request.contact_name
        phone_raw = request.contact_phone
        contact_address = request.contact_address
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

    pricing_customer = customer or _guest_customer(contact_name, phone, contact_address)
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
        contact_name=contact_name.strip(),
        contact_phone=phone,
        contact_phone_raw=phone_raw.strip(),
        contact_address=contact_address.strip(),
        notes=(request.notes or "").strip() or None,
        currency=order_currency,
        intended_customer_id=context.customer_id if context else None,
        intended_assurance=context.assurance.value if context else None,
        linked_customer_id=customer.id if customer else None,
        created_at=now,
    )
    db.add(order)
    db.flush()
    # Draft invoice + first provisional revision (D-033: one order → one header). A public order
    # stays unlinked until the owner resolves it; a personalized one is applied to its customer
    # through the editor's own customer path (D-090), exactly as an owner link would be.
    customer_snapshot: dict[str, object]
    if customer is not None:
        applied = invoice_editor.apply_customer(db, tenant.id, customer, order_currency, net_sales)
        customer_snapshot = applied.customer_snapshot
        prior_balance, amount_due = applied.prior_balance_snapshot, applied.amount_due_display
    else:
        customer_snapshot = {
            "name": order.contact_name,
            "phone": order.contact_phone,
            "address": order.contact_address,
            "source": "storefront_checkout",
        }
        prior_balance = Decimal("0")
        amount_due = invoice_editor.stored_money(net_sales)
    invoice_id, revision_id = uuid4(), uuid4()
    invoice = Invoice(
        id=invoice_id,
        tenant_id=tenant.id,
        customer_id=customer.id if customer else None,
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
        customer_id=customer.id if customer else None,
        customer_snapshot=customer_snapshot,
        prior_balance_snapshot=prior_balance,
        subtotal=subtotal,
        discount_total=discount_total,
        markup_total=markup_total,
        net_sales=net_sales,
        amount_due_display=amount_due,
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


def resolve_reference(db: Session, raw: str | None) -> OrderAccessReference:
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
    return reference


def provisional_order(db: Session, raw: str | None) -> ProvisionalOrderResponse:
    """Customer-safe projection through the provisional reference: contact snapshot, current
    items/totals, status, the owner-set delivery date and the cancellation state. Never debt,
    history, grades, costs, driver data or other orders (PHASE_05.md F)."""
    reference = resolve_reference(db, raw)
    tenant_id = reference.tenant_id
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
        delivery_date=order.delivery_date,
        cancellation=(
            db.scalar(
                select(OrderCancellationRequest.status)
                .where(OrderCancellationRequest.order_id == order.id)
                .order_by(OrderCancellationRequest.created_at.desc())
            )
        ),
    )
