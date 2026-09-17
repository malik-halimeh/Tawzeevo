from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    AllocationKind,
    AuditEvent,
    Customer,
    CustomerLedgerEntry,
    Invoice,
    InvoiceRevision,
    InvoiceRevisionItem,
    InvoiceSequence,
    InvoiceStatus,
    LedgerEntryType,
    PaymentAllocation,
    PublicInvoiceCapability,
)
from tawzeevo_api.repositories.tenancy import commit_and_restore_tenant_scope, set_tenant_scope
from tawzeevo_api.schemas.invoice_editor import (
    InvoiceCancelRequest,
    InvoiceEditorDraftRequest,
    InvoiceEditorResponse,
    InvoiceHistoryResponse,
    InvoiceHistoryRevisionResponse,
)
from tawzeevo_api.services.cash_van import get_customer
from tawzeevo_api.services.invoice_editor import (
    _audit_fuzzy_acceptances,
    _customer_snapshot,
    _editor_response,
    _prepare_items,
    _totals,
    _write_revision_items,
    money,
    update_editor_draft,
)


def _locked_invoice(db: Session, tenant_id: UUID, invoice_id: UUID) -> Invoice:
    invoice = db.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
        .with_for_update()
    )
    if invoice is None:
        raise AppError(404, "INVOICE_NOT_FOUND", "Invoice was not found")
    return invoice


def _revision(db: Session, tenant_id: UUID, invoice: Invoice) -> InvoiceRevision:
    revision = db.scalar(
        select(InvoiceRevision).where(
            InvoiceRevision.id == invoice.current_revision_id,
            InvoiceRevision.invoice_id == invoice.id,
            InvoiceRevision.tenant_id == tenant_id,
        )
    )
    if revision is None:
        raise AppError(409, "INVOICE_REVISION_MISSING", "Invoice revision was not found")
    return revision


def _validate_confirmable_costs(db: Session, tenant_id: UUID, revision: InvoiceRevision) -> None:
    items = list(
        db.scalars(
            select(InvoiceRevisionItem).where(
                InvoiceRevisionItem.tenant_id == tenant_id,
                InvoiceRevisionItem.invoice_revision_id == revision.id,
            )
        )
    )
    if not items:
        raise AppError(409, "INVOICE_ITEMS_REQUIRED", "Invoice must contain at least one item")
    for item in items:
        if (
            item.supplier_id is None
            or item.unit_cost is None
            or item.cost_currency is None
            or item.cost_basis is None
            or item.cost_source_type is None
        ):
            raise AppError(
                409,
                "INVOICE_COST_REQUIRED",
                "Every confirmed invoice line requires a complete supplier cost snapshot",
            )
        if item.cost_currency != revision.currency:
            raise AppError(
                409,
                "INVOICE_COST_CURRENCY_MISMATCH",
                "Every line cost must use the invoice currency",
            )


def _allocate_official_number(
    db: Session, tenant_id: UUID, confirmed_at: datetime
) -> tuple[int, int, str]:
    year = confirmed_at.year
    db.execute(
        insert(InvoiceSequence)
        .values(tenant_id=tenant_id, year=year, last_number=0)
        .on_conflict_do_nothing(index_elements=["tenant_id", "year"])
    )
    sequence = db.scalar(
        select(InvoiceSequence)
        .where(InvoiceSequence.tenant_id == tenant_id, InvoiceSequence.year == year)
        .with_for_update()
    )
    if sequence is None:
        raise AppError(409, "INVOICE_SEQUENCE_UNAVAILABLE", "Invoice sequence is unavailable")
    sequence.last_number += 1
    sequence.updated_at = confirmed_at
    db.flush()
    return year, sequence.last_number, f"{year:04d}-{sequence.last_number:06d}"


def confirm_invoice(
    db: Session,
    tenant_id: UUID,
    actor_user_id: UUID,
    invoice_id: UUID,
    expected_revision_id: UUID,
) -> InvoiceEditorResponse:
    invoice = _locked_invoice(db, tenant_id, invoice_id)
    if invoice.status is InvoiceStatus.CANCELLED:
        raise AppError(409, "INVOICE_CANCELLED", "A cancelled invoice cannot be confirmed")
    if invoice.status is InvoiceStatus.CONFIRMED:
        return _editor_response(db, tenant_id, invoice)
    if invoice.current_revision_id != expected_revision_id:
        raise AppError(409, "STALE_INVOICE_REVISION", "Invoice has a newer revision")
    revision = _revision(db, tenant_id, invoice)
    if revision.customer_id is None:
        raise AppError(409, "INVOICE_CUSTOMER_REQUIRED", "Invoice requires a customer")
    if money(revision.net_sales) <= 0:
        raise AppError(
            409,
            "ZERO_VALUE_INVOICE_NOT_CONFIRMABLE",
            "A confirmed invoice must have a positive net sales value",
        )
    _validate_confirmable_costs(db, tenant_id, revision)

    confirmed_at = datetime.now(UTC)
    year, sequence_number, official_number = _allocate_official_number(db, tenant_id, confirmed_at)
    invoice.official_invoice_year = year
    invoice.official_sequence_number = sequence_number
    invoice.official_invoice_number = official_number
    invoice.confirmed_revision_id = revision.id
    invoice.status = InvoiceStatus.CONFIRMED
    invoice.confirmed_at = confirmed_at
    invoice.updated_by_user_id = actor_user_id
    db.add(
        CustomerLedgerEntry(
            tenant_id=tenant_id,
            customer_id=revision.customer_id,
            currency=revision.currency,
            signed_amount=money(revision.net_sales),
            entry_type=LedgerEntryType.INVOICE_CHARGE,
            source_type="INVOICE",
            source_id=invoice.id,
            source_effect_key=f"invoice:{invoice.id}:charge",
            effective_at=confirmed_at,
            actor_user_id=actor_user_id,
            metadata_json={
                "invoice_revision_id": str(revision.id),
                "official_invoice_number": official_number,
            },
        )
    )
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action="invoice_confirmed",
            entity_type="invoice",
            entity_id=invoice.id,
            details={
                "revision_id": str(revision.id),
                "official_invoice_number": official_number,
                "net_sales": str(money(revision.net_sales)),
                "currency": revision.currency,
            },
        )
    )
    try:
        commit_and_restore_tenant_scope(db, tenant_id)
    except IntegrityError as exc:
        db.rollback()
        set_tenant_scope(db, tenant_id)
        replay = db.scalar(
            select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
        )
        if replay is not None and replay.status is InvoiceStatus.CONFIRMED:
            return _editor_response(db, tenant_id, replay)
        raise AppError(
            409, "INVOICE_CONFIRMATION_CONFLICT", "Invoice confirmation conflicted"
        ) from exc
    db.refresh(invoice)
    return _editor_response(db, tenant_id, invoice)


def cancel_invoice(
    db: Session,
    tenant_id: UUID,
    actor_user_id: UUID,
    invoice_id: UUID,
    request: InvoiceCancelRequest,
) -> InvoiceEditorResponse:
    invoice = _locked_invoice(db, tenant_id, invoice_id)
    if invoice.status is InvoiceStatus.CANCELLED:
        return _editor_response(db, tenant_id, invoice)
    revision = _revision(db, tenant_id, invoice)
    cancelled_at = datetime.now(UTC)
    released_credit = Decimal("0.0000")
    if invoice.status is InvoiceStatus.CONFIRMED:
        if revision.customer_id is None:
            raise AppError(409, "INVOICE_CUSTOMER_REQUIRED", "Invoice requires a customer")
        customer = db.scalar(
            select(Customer)
            .where(
                Customer.tenant_id == tenant_id,
                Customer.id == revision.customer_id,
            )
            .with_for_update()
        )
        if customer is None:
            raise AppError(404, "CUSTOMER_NOT_FOUND", "Customer was not found")
        ledger_entries = list(
            db.scalars(
                select(CustomerLedgerEntry).where(
                    CustomerLedgerEntry.tenant_id == tenant_id,
                    CustomerLedgerEntry.customer_id == revision.customer_id,
                    CustomerLedgerEntry.currency == revision.currency,
                    CustomerLedgerEntry.source_type == "INVOICE",
                    CustomerLedgerEntry.source_id == invoice.id,
                )
            )
        )
        ledger_value = money(sum((entry.signed_amount for entry in ledger_entries), Decimal("0")))
        if ledger_value != money(revision.net_sales):
            raise AppError(
                409,
                "INVOICE_LEDGER_OUT_OF_BALANCE",
                "Invoice ledger value does not match its current revision",
            )
        db.add(
            CustomerLedgerEntry(
                tenant_id=tenant_id,
                customer_id=revision.customer_id,
                currency=revision.currency,
                signed_amount=money(-revision.net_sales),
                entry_type=LedgerEntryType.INVOICE_REVERSAL,
                source_type="INVOICE",
                source_id=invoice.id,
                source_effect_key=f"invoice:{invoice.id}:cancellation",
                effective_at=cancelled_at,
                actor_user_id=actor_user_id,
                idempotency_key=request.idempotency_key,
                metadata_json={
                    "invoice_revision_id": str(revision.id),
                    "reason": request.reason,
                },
            )
        )
        for entry in ledger_entries:
            for allocation, effective_amount in _effective_allocations(db, tenant_id, entry.id):
                db.add(
                    PaymentAllocation(
                        tenant_id=tenant_id,
                        payment_id=allocation.payment_id,
                        customer_id=allocation.customer_id,
                        target_ledger_entry_id=allocation.target_ledger_entry_id,
                        currency=allocation.currency,
                        amount=effective_amount,
                        kind=AllocationKind.REVERSAL,
                        reverses_allocation_id=allocation.id,
                        created_by_user_id=actor_user_id,
                        idempotency_key=uuid5(
                            NAMESPACE_URL,
                            f"tawzeevo:{tenant_id}:invoice:{invoice.id}:cancel:"
                            f"{request.idempotency_key}:allocation:{allocation.id}",
                        ),
                    )
                )
                released_credit = money(released_credit + effective_amount)
    invoice.status = InvoiceStatus.CANCELLED
    invoice.cancelled_at = cancelled_at
    invoice.updated_by_user_id = actor_user_id
    # D-042: cancellation revokes public access in the same transaction.
    for cap in db.scalars(
        select(PublicInvoiceCapability)
        .where(
            PublicInvoiceCapability.tenant_id == tenant_id,
            PublicInvoiceCapability.invoice_id == invoice.id,
            PublicInvoiceCapability.revoked_at.is_(None),
        )
        .with_for_update()
    ):
        cap.revoked_at = cancelled_at
        db.add(
            AuditEvent(
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                action="invoice_capability_revoked",
                entity_type="public_invoice_capability",
                entity_id=cap.id,
                details={"invoice_id": str(invoice.id), "reason": "invoice_cancelled"},
            )
        )
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=(
                "confirmed_invoice_cancelled"
                if invoice.confirmed_at is not None
                else "draft_invoice_cancelled"
            ),
            entity_type="invoice",
            entity_id=invoice.id,
            details={
                "revision_id": str(revision.id),
                "reason": request.reason,
                "released_allocation_credit": str(released_credit),
                "payments_preserved": True,
            },
        )
    )
    commit_and_restore_tenant_scope(db, tenant_id)
    db.refresh(invoice)
    return _editor_response(db, tenant_id, invoice)


def _balance_excluding_invoice(
    db: Session,
    tenant_id: UUID,
    customer_id: UUID,
    currency: str,
    invoice_id: UUID,
) -> Decimal:
    value = db.scalar(
        select(func.coalesce(func.sum(CustomerLedgerEntry.signed_amount), 0)).where(
            CustomerLedgerEntry.tenant_id == tenant_id,
            CustomerLedgerEntry.customer_id == customer_id,
            CustomerLedgerEntry.currency == currency,
            ~(
                (CustomerLedgerEntry.source_type == "INVOICE")
                & (CustomerLedgerEntry.source_id == invoice_id)
            ),
        )
    )
    return money(Decimal(value or 0))


def _effective_allocations(
    db: Session, tenant_id: UUID, target_entry_id: UUID
) -> list[tuple[PaymentAllocation, Decimal]]:
    rows = list(
        db.scalars(
            select(PaymentAllocation)
            .where(
                PaymentAllocation.tenant_id == tenant_id,
                PaymentAllocation.target_ledger_entry_id == target_entry_id,
            )
            .order_by(PaymentAllocation.created_at.asc(), PaymentAllocation.id.asc())
        )
    )
    reversals: dict[UUID, Decimal] = {}
    applies: list[PaymentAllocation] = []
    for row in rows:
        if row.kind == AllocationKind.APPLY:
            applies.append(row)
        elif row.reverses_allocation_id is not None:
            reversals[row.reverses_allocation_id] = money(
                reversals.get(row.reverses_allocation_id, Decimal("0")) + row.amount
            )
    return [
        (row, money(row.amount - reversals.get(row.id, Decimal("0"))))
        for row in applies
        if money(row.amount - reversals.get(row.id, Decimal("0"))) > 0
    ]


def _reconcile_excess_allocations(
    db: Session,
    tenant_id: UUID,
    actor_user_id: UUID,
    invoice: Invoice,
    revision_id: UUID,
    new_net_sales: Decimal,
) -> Decimal:
    charge = db.scalar(
        select(CustomerLedgerEntry).where(
            CustomerLedgerEntry.tenant_id == tenant_id,
            CustomerLedgerEntry.source_effect_key == f"invoice:{invoice.id}:charge",
        )
    )
    if charge is None:
        return Decimal("0.0000")
    effective = _effective_allocations(db, tenant_id, charge.id)
    allocated = money(sum((amount for _row, amount in effective), Decimal("0")))
    excess = money(allocated - new_net_sales)
    if excess <= 0:
        return Decimal("0.0000")
    released = excess
    for allocation, effective_amount in reversed(effective):
        if excess <= 0:
            break
        release = min(excess, effective_amount)
        reverse_key = uuid5(
            NAMESPACE_URL,
            f"tawzeevo:{tenant_id}:invoice:{invoice.id}:revision:{revision_id}:"
            f"allocation:{allocation.id}:reverse",
        )
        db.add(
            PaymentAllocation(
                tenant_id=tenant_id,
                payment_id=allocation.payment_id,
                customer_id=allocation.customer_id,
                target_ledger_entry_id=allocation.target_ledger_entry_id,
                currency=allocation.currency,
                amount=effective_amount,
                kind=AllocationKind.REVERSAL,
                reverses_allocation_id=allocation.id,
                created_by_user_id=actor_user_id,
                idempotency_key=reverse_key,
            )
        )
        retained = money(effective_amount - release)
        if retained > 0:
            db.add(
                PaymentAllocation(
                    tenant_id=tenant_id,
                    payment_id=allocation.payment_id,
                    customer_id=allocation.customer_id,
                    target_ledger_entry_id=allocation.target_ledger_entry_id,
                    currency=allocation.currency,
                    amount=retained,
                    kind=AllocationKind.APPLY,
                    created_by_user_id=actor_user_id,
                    idempotency_key=uuid5(
                        NAMESPACE_URL,
                        f"tawzeevo:{tenant_id}:invoice:{invoice.id}:revision:{revision_id}:"
                        f"allocation:{allocation.id}:retained",
                    ),
                )
            )
        excess = money(excess - release)
    if excess > 0:
        raise AppError(
            409,
            "ALLOCATION_RECONCILIATION_FAILED",
            "Allocated invoice value could not be reconciled",
        )
    return released


def update_confirmed_invoice(
    db: Session,
    tenant_id: UUID,
    actor_user_id: UUID,
    invoice_id: UUID,
    request: InvoiceEditorDraftRequest,
    *,
    fuzzy_threshold: Decimal,
) -> InvoiceEditorResponse:
    invoice = _locked_invoice(db, tenant_id, invoice_id)
    if invoice.status is not InvoiceStatus.CONFIRMED:
        raise AppError(409, "INVOICE_NOT_CONFIRMED", "Invoice is not confirmed")
    replay = db.scalar(
        select(InvoiceRevision).where(
            InvoiceRevision.tenant_id == tenant_id,
            InvoiceRevision.invoice_id == invoice_id,
            InvoiceRevision.client_command_id == request.client_command_id,
        )
    )
    if replay is not None:
        if invoice.current_revision_id != replay.id:
            raise AppError(409, "STALE_INVOICE_REVISION", "Invoice has a newer revision")
        return _editor_response(db, tenant_id, invoice)
    if request.expected_predecessor_revision_id != invoice.current_revision_id:
        raise AppError(409, "STALE_INVOICE_REVISION", "Invoice has a newer revision")
    predecessor = _revision(db, tenant_id, invoice)
    if predecessor.customer_id is None:
        raise AppError(409, "INVOICE_CUSTOMER_REQUIRED", "Invoice requires a customer")
    if request.customer_id != predecessor.customer_id:
        raise AppError(
            409,
            "CONFIRMED_INVOICE_CUSTOMER_FIXED",
            "A confirmed invoice cannot be moved to another customer",
        )
    if request.currency != predecessor.currency:
        raise AppError(
            409,
            "CONFIRMED_INVOICE_CURRENCY_FIXED",
            "A confirmed invoice currency cannot be changed",
        )
    customer = get_customer(db, tenant_id, request.customer_id)
    items = _prepare_items(
        db, tenant_id, customer, request.currency, request.items, fuzzy_threshold
    )
    subtotal, discount_total, markup_total, net_sales = _totals(
        items, request.invoice_discount_expression, request.invoice_markup_expression
    )
    if money(net_sales) <= 0:
        # D-043: every confirmed revision keeps strictly positive net sales. A zero economic
        # effect must go through cancellation/reversal, never a zero-value confirmed revision.
        raise AppError(
            409,
            "ZERO_VALUE_INVOICE_NOT_CONFIRMABLE",
            "A confirmed invoice revision must keep a positive net sales value",
        )
    prior_balance = _balance_excluding_invoice(
        db, tenant_id, customer.id, request.currency, invoice.id
    )
    revision_id = uuid4()
    revision = InvoiceRevision(
        id=revision_id,
        tenant_id=tenant_id,
        invoice_id=invoice_id,
        client_command_id=request.client_command_id,
        predecessor_revision_id=predecessor.id,
        server_revision_number=predecessor.server_revision_number + 1,
        pricing_version="pricing-v1",
        currency=request.currency,
        customer_id=customer.id,
        customer_snapshot=_customer_snapshot(customer),
        prior_balance_snapshot=prior_balance,
        subtotal=subtotal,
        discount_total=discount_total,
        markup_total=markup_total,
        net_sales=net_sales,
        amount_due_display=money(prior_balance + net_sales),
        created_by_user_id=actor_user_id,
        reason=request.reason,
    )
    db.add(revision)
    _write_revision_items(db, tenant_id, revision_id, items)
    db.flush()
    _validate_confirmable_costs(db, tenant_id, revision)
    delta = money(net_sales - predecessor.net_sales)
    effective_at = datetime.now(UTC)
    db.add(
        CustomerLedgerEntry(
            tenant_id=tenant_id,
            customer_id=customer.id,
            currency=request.currency,
            signed_amount=delta,
            entry_type=LedgerEntryType.INVOICE_ADJUSTMENT,
            source_type="INVOICE",
            source_id=invoice.id,
            source_effect_key=f"invoice:{invoice.id}:revision:{revision.id}:adjustment",
            effective_at=effective_at,
            actor_user_id=actor_user_id,
            idempotency_key=request.client_command_id,
            metadata_json={
                "invoice_revision_id": str(revision.id),
                "predecessor_revision_id": str(predecessor.id),
            },
        )
    )
    released = _reconcile_excess_allocations(
        db, tenant_id, actor_user_id, invoice, revision.id, net_sales
    )
    _audit_fuzzy_acceptances(db, tenant_id, actor_user_id, invoice.id, items)
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action="confirmed_invoice_revised",
            entity_type="invoice",
            entity_id=invoice.id,
            details={
                "revision_id": str(revision.id),
                "predecessor_revision_id": str(predecessor.id),
                "ledger_delta": str(delta),
                "released_allocation_credit": str(released),
                "currency": revision.currency,
            },
        )
    )
    invoice.current_revision_id = revision.id
    invoice.updated_by_user_id = actor_user_id
    try:
        commit_and_restore_tenant_scope(db, tenant_id)
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "STALE_INVOICE_REVISION", "Invoice has a newer revision") from exc
    db.refresh(invoice)
    return _editor_response(db, tenant_id, invoice)


def update_invoice(
    db: Session,
    tenant_id: UUID,
    actor_user_id: UUID,
    invoice_id: UUID,
    request: InvoiceEditorDraftRequest,
    *,
    fuzzy_threshold: Decimal,
) -> InvoiceEditorResponse:
    status = db.scalar(
        select(Invoice.status).where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
    )
    if status is None:
        raise AppError(404, "INVOICE_NOT_FOUND", "Invoice was not found")
    if status is InvoiceStatus.DRAFT:
        return update_editor_draft(
            db,
            tenant_id,
            actor_user_id,
            invoice_id,
            request,
            fuzzy_threshold=fuzzy_threshold,
        )
    if status is InvoiceStatus.CONFIRMED:
        return update_confirmed_invoice(
            db,
            tenant_id,
            actor_user_id,
            invoice_id,
            request,
            fuzzy_threshold=fuzzy_threshold,
        )
    raise AppError(409, "INVOICE_CANCELLED", "A cancelled invoice cannot be edited")


def get_invoice_history(db: Session, tenant_id: UUID, invoice_id: UUID) -> InvoiceHistoryResponse:
    invoice = db.scalar(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
    )
    if invoice is None:
        raise AppError(404, "INVOICE_NOT_FOUND", "Invoice was not found")
    revisions = list(
        db.scalars(
            select(InvoiceRevision)
            .where(
                InvoiceRevision.tenant_id == tenant_id,
                InvoiceRevision.invoice_id == invoice_id,
            )
            .order_by(InvoiceRevision.server_revision_number.desc())
        )
    )
    by_id = {revision.id: revision for revision in revisions}
    history: list[InvoiceHistoryRevisionResponse] = []
    for revision in revisions:
        original_pointer = invoice.current_revision_id
        invoice.current_revision_id = revision.id
        base = _editor_response(db, tenant_id, invoice)
        invoice.current_revision_id = original_pointer
        ledger_delta: Decimal | None = None
        if invoice.confirmed_revision_id == revision.id:
            ledger_delta = money(revision.net_sales)
        elif invoice.confirmed_revision_id is not None:
            confirmed = by_id.get(invoice.confirmed_revision_id)
            if (
                confirmed is not None
                and revision.server_revision_number > confirmed.server_revision_number
            ):
                predecessor = (
                    by_id.get(revision.predecessor_revision_id)
                    if revision.predecessor_revision_id is not None
                    else None
                )
                if predecessor is not None:
                    ledger_delta = money(revision.net_sales - predecessor.net_sales)
        history.append(
            InvoiceHistoryRevisionResponse(
                **base.model_dump(),
                predecessor_revision_id=revision.predecessor_revision_id,
                reason=revision.reason,
                revision_created_at=revision.created_at,
                is_current=revision.id == original_pointer,
                ledger_delta=ledger_delta,
            )
        )
    return InvoiceHistoryResponse(revisions=history)
