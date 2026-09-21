from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    AllocationKind,
    AuditEvent,
    Customer,
    CustomerLedgerEntry,
    Invoice,
    LedgerEntryType,
    Payment,
    PaymentAllocation,
    PaymentDirection,
)
from tawzeevo_api.repositories.tenancy import commit_and_restore_tenant_scope
from tawzeevo_api.schemas.payments import (
    AllocationSelectionRequest,
    CustomerObligationListResponse,
    CustomerObligationResponse,
    CustomerPaymentResponse,
    CustomerReceiptRequest,
    CustomerRefundRequest,
    PaymentAllocationResponse,
    PaymentReversalRequest,
)
from tawzeevo_api.services.customer_ledger import (
    opening_obligation_positions,
    standalone_customer_debt_entries,
)
from tawzeevo_api.services.invoice_editor import money


@dataclass(frozen=True)
class _Obligation:
    target: CustomerLedgerEntry
    original_amount: Decimal
    allocated_amount: Decimal
    outstanding_amount: Decimal
    label: str


def _lock_idempotency_key(db: Session, idempotency_key: UUID) -> None:
    lock_key = idempotency_key.int & ((1 << 63) - 1)
    db.execute(text("SELECT pg_advisory_xact_lock(:lock_key)"), {"lock_key": lock_key})


def _locked_customer(db: Session, tenant_id: UUID, customer_id: UUID) -> Customer:
    customer = db.scalar(
        select(Customer)
        .where(Customer.tenant_id == tenant_id, Customer.id == customer_id)
        .with_for_update()
    )
    if customer is None:
        raise AppError(404, "CUSTOMER_NOT_FOUND", "Customer was not found")
    return customer


def _customer_balance(db: Session, tenant_id: UUID, customer_id: UUID, currency: str) -> Decimal:
    value = db.scalar(
        select(func.coalesce(func.sum(CustomerLedgerEntry.signed_amount), 0)).where(
            CustomerLedgerEntry.tenant_id == tenant_id,
            CustomerLedgerEntry.customer_id == customer_id,
            CustomerLedgerEntry.currency == currency,
        )
    )
    return money(Decimal(value or 0))


def _allocation_rows(
    db: Session,
    tenant_id: UUID,
    *,
    customer_id: UUID | None = None,
    currency: str | None = None,
    payment_id: UUID | None = None,
) -> list[PaymentAllocation]:
    query = select(PaymentAllocation).where(PaymentAllocation.tenant_id == tenant_id)
    if customer_id is not None:
        query = query.where(PaymentAllocation.customer_id == customer_id)
    if currency is not None:
        query = query.where(PaymentAllocation.currency == currency)
    if payment_id is not None:
        query = query.where(PaymentAllocation.payment_id == payment_id)
    return list(
        db.scalars(query.order_by(PaymentAllocation.created_at.asc(), PaymentAllocation.id.asc()))
    )


def _effective_allocation_amounts(
    rows: list[PaymentAllocation],
) -> tuple[dict[UUID, Decimal], dict[UUID, Decimal]]:
    reversed_by_apply: dict[UUID, Decimal] = defaultdict(lambda: Decimal("0.0000"))
    applies: dict[UUID, PaymentAllocation] = {}
    for row in rows:
        if row.kind == AllocationKind.APPLY:
            applies[row.id] = row
        elif row.reverses_allocation_id is not None:
            reversed_by_apply[row.reverses_allocation_id] = money(
                reversed_by_apply[row.reverses_allocation_id] + row.amount
            )
    by_apply: dict[UUID, Decimal] = {}
    by_target: dict[UUID, Decimal] = defaultdict(lambda: Decimal("0.0000"))
    for allocation_id, row in applies.items():
        effective = money(row.amount - reversed_by_apply[allocation_id])
        if effective < 0:
            raise AppError(
                409,
                "ALLOCATION_HISTORY_INVALID",
                "Allocation reversals exceed their original allocation",
            )
        by_apply[allocation_id] = effective
        by_target[row.target_ledger_entry_id] = money(
            by_target[row.target_ledger_entry_id] + effective
        )
    return by_apply, by_target


def _obligations(
    db: Session, tenant_id: UUID, customer_id: UUID, currency: str
) -> list[_Obligation]:
    entries = list(
        db.scalars(
            select(CustomerLedgerEntry)
            .where(
                CustomerLedgerEntry.tenant_id == tenant_id,
                CustomerLedgerEntry.customer_id == customer_id,
                CustomerLedgerEntry.currency == currency,
            )
            .order_by(
                CustomerLedgerEntry.effective_at.asc(),
                CustomerLedgerEntry.created_at.asc(),
                CustomerLedgerEntry.id.asc(),
            )
        )
    )
    _by_apply, allocated_by_target = _effective_allocation_amounts(
        _allocation_rows(
            db,
            tenant_id,
            customer_id=customer_id,
            currency=currency,
        )
    )
    invoice_groups: dict[UUID, list[CustomerLedgerEntry]] = defaultdict(list)
    non_invoice_entries: list[CustomerLedgerEntry] = []
    for entry in entries:
        if entry.source_type == "INVOICE" and entry.source_id is not None:
            invoice_groups[entry.source_id].append(entry)
        else:
            non_invoice_entries.append(entry)

    invoice_ids = list(invoice_groups)
    invoice_numbers = (
        {
            invoice.id: invoice.official_invoice_number
            for invoice in db.scalars(
                select(Invoice).where(
                    Invoice.tenant_id == tenant_id,
                    Invoice.id.in_(invoice_ids),
                )
            )
        }
        if invoice_ids
        else {}
    )
    obligations: list[_Obligation] = []
    for invoice_id, invoice_entries in invoice_groups.items():
        original = money(sum((entry.signed_amount for entry in invoice_entries), Decimal("0")))
        charges = [
            entry for entry in invoice_entries if entry.entry_type == LedgerEntryType.INVOICE_CHARGE
        ]
        if original <= 0 or not charges:
            continue
        target = min(charges, key=lambda entry: (entry.effective_at, entry.created_at, entry.id))
        allocated = money(
            sum(
                (allocated_by_target.get(entry.id, Decimal("0")) for entry in invoice_entries),
                Decimal("0"),
            )
        )
        outstanding = money(original - allocated)
        if outstanding > 0:
            number = invoice_numbers.get(invoice_id)
            obligations.append(
                _Obligation(
                    target=target,
                    original_amount=original,
                    allocated_amount=allocated,
                    outstanding_amount=outstanding,
                    label=f"Invoice {number}" if number else "Invoice",
                )
            )
    for position in opening_obligation_positions(non_invoice_entries, allocated_by_target):
        obligations.append(
            _Obligation(
                target=position.target,
                original_amount=position.original_amount,
                allocated_amount=position.allocated_amount,
                outstanding_amount=position.outstanding_amount,
                label="Opening Balance",
            )
        )
    for entry in standalone_customer_debt_entries(non_invoice_entries):
        allocated = allocated_by_target.get(entry.id, Decimal("0.0000"))
        outstanding = money(entry.signed_amount - allocated)
        if outstanding > 0:
            obligations.append(
                _Obligation(
                    target=entry,
                    original_amount=money(entry.signed_amount),
                    allocated_amount=money(allocated),
                    outstanding_amount=outstanding,
                    label="Authorized Manual Adjustment",
                )
            )
    obligations.sort(
        key=lambda item: (item.target.effective_at, item.target.created_at, item.target.id)
    )
    return obligations


def customer_obligations(
    db: Session, tenant_id: UUID, customer_id: UUID, currency: str
) -> CustomerObligationListResponse:
    _locked_customer(db, tenant_id, customer_id)
    return CustomerObligationListResponse(
        customer_id=customer_id,
        currency=currency,
        obligations=[
            CustomerObligationResponse(
                target_ledger_entry_id=item.target.id,
                source_type=item.target.source_type,
                source_id=item.target.source_id,
                label=item.label,
                effective_at=item.target.effective_at,
                original_amount=item.original_amount,
                allocated_amount=item.allocated_amount,
                outstanding_amount=item.outstanding_amount,
            )
            for item in _obligations(db, tenant_id, customer_id, currency)
        ],
    )


def _payment_response(db: Session, tenant_id: UUID, payment: Payment) -> CustomerPaymentResponse:
    if payment.customer_id is None:
        raise AppError(409, "CUSTOMER_PAYMENT_REQUIRED", "Payment is not a customer payment")
    rows = _allocation_rows(db, tenant_id, payment_id=payment.id)
    effective_by_apply, _by_target = _effective_allocation_amounts(rows)
    allocated = money(sum(effective_by_apply.values(), Decimal("0")))
    is_reversed = (
        db.scalar(
            select(Payment.id).where(
                Payment.tenant_id == tenant_id,
                Payment.reverses_payment_id == payment.id,
            )
        )
        is not None
    )
    effective_receipt = (
        payment.amount
        if payment.direction == PaymentDirection.CUSTOMER_RECEIPT and not is_reversed
        else Decimal("0.0000")
    )
    balance = _customer_balance(db, tenant_id, payment.customer_id, payment.currency)
    allocation_responses: list[PaymentAllocationResponse] = []
    for row in rows:
        effective = (
            effective_by_apply.get(row.id, Decimal("0.0000"))
            if row.kind == AllocationKind.APPLY
            else money(-row.amount)
        )
        allocation_responses.append(
            PaymentAllocationResponse(
                id=row.id,
                target_ledger_entry_id=row.target_ledger_entry_id,
                amount=money(row.amount),
                kind=row.kind,
                reverses_allocation_id=row.reverses_allocation_id,
                effective_amount=effective,
                created_at=row.created_at,
            )
        )
    return CustomerPaymentResponse(
        id=payment.id,
        tenant_id=payment.tenant_id,
        customer_id=payment.customer_id,
        direction=payment.direction,
        amount=money(payment.amount),
        currency=payment.currency,
        method=payment.method,
        reference=payment.reference,
        paid_at=payment.paid_at,
        recorded_at=payment.recorded_at,
        reverses_payment_id=payment.reverses_payment_id,
        notes=payment.notes,
        allocated_amount=allocated,
        unallocated_amount=money(max(Decimal("0"), effective_receipt - allocated)),
        customer_balance=balance,
        available_credit=money(max(Decimal("0"), -balance)),
        allocations=allocation_responses,
    )


def _existing_payment(db: Session, tenant_id: UUID, idempotency_key: UUID) -> Payment | None:
    return db.scalar(
        select(Payment).where(
            Payment.tenant_id == tenant_id,
            Payment.idempotency_key == idempotency_key,
        )
    )


def _validate_replay(
    payment: Payment,
    *,
    direction: PaymentDirection,
    customer_id: UUID,
    currency: str,
    amount: Decimal,
    method: str | None = None,
    reference: str | None = None,
    paid_at: datetime | None = None,
    allocations: list[AllocationSelectionRequest] | None = None,
    db: Session | None = None,
) -> None:
    """FI-32: a replay must be the same logical command. Beyond direction/customer/currency/
    amount, the recorded method, reference, payment time and — when the request selects them —
    the allocation targets must match; otherwise the key was reused for a different intent.
    An omitted allocation list (automatic allocation) is not compared: it carries no intent."""
    different = (
        payment.direction != direction
        or payment.customer_id != customer_id
        or payment.currency != currency
        or money(payment.amount) != money(amount)
    )
    if method is not None and (payment.method or None) != (method or None):
        different = True
    if reference is not None and (payment.reference or None) != (reference or None):
        different = True
    if paid_at is not None and payment.paid_at.astimezone(UTC) != paid_at.astimezone(UTC):
        different = True
    if allocations is not None and db is not None:
        stored = sorted(
            (row.target_ledger_entry_id, money(row.amount))
            for row in db.scalars(
                select(PaymentAllocation).where(
                    PaymentAllocation.tenant_id == payment.tenant_id,
                    PaymentAllocation.payment_id == payment.id,
                    PaymentAllocation.kind == AllocationKind.APPLY,
                )
            )
        )
        requested = sorted((row.target_ledger_entry_id, money(row.amount)) for row in allocations)
        if stored != requested:
            different = True
    if different:
        raise AppError(
            409,
            "IDEMPOTENCY_KEY_REUSED",
            "Idempotency key was already used for a different financial command",
        )


def _selected_allocations(
    db: Session,
    tenant_id: UUID,
    customer_id: UUID,
    currency: str,
    amount: Decimal,
    requested: list[AllocationSelectionRequest] | None,
) -> list[tuple[CustomerLedgerEntry, Decimal]]:
    obligations = _obligations(db, tenant_id, customer_id, currency)
    by_target = {item.target.id: item for item in obligations}
    if requested is not None:
        selected: list[tuple[CustomerLedgerEntry, Decimal]] = []
        total = Decimal("0.0000")
        for allocation in requested:
            obligation = by_target.get(allocation.target_ledger_entry_id)
            allocation_amount = money(allocation.amount)
            if obligation is None:
                raise AppError(
                    409,
                    "ALLOCATION_TARGET_UNAVAILABLE",
                    "Allocation target is not an unpaid obligation in this currency",
                )
            if allocation_amount > obligation.outstanding_amount:
                raise AppError(
                    409,
                    "ALLOCATION_EXCEEDS_OBLIGATION",
                    "Allocation exceeds the target obligation outstanding amount",
                )
            total = money(total + allocation_amount)
            selected.append((obligation.target, allocation_amount))
        if total > amount:
            raise AppError(
                409,
                "ALLOCATION_EXCEEDS_PAYMENT",
                "Allocations cannot exceed the payment amount",
            )
        return selected

    remaining = amount
    selected = []
    for obligation in obligations:
        if remaining <= 0:
            break
        allocation_amount = money(min(remaining, obligation.outstanding_amount))
        selected.append((obligation.target, allocation_amount))
        remaining = money(remaining - allocation_amount)
    return selected


def record_customer_receipt(
    db: Session,
    tenant_id: UUID,
    actor_user_id: UUID,
    request: CustomerReceiptRequest,
) -> CustomerPaymentResponse:
    _lock_idempotency_key(db, request.idempotency_key)
    _locked_customer(db, tenant_id, request.customer_id)
    amount = money(request.amount)
    replay = _existing_payment(db, tenant_id, request.idempotency_key)
    if replay is not None:
        _validate_replay(
            replay,
            direction=PaymentDirection.CUSTOMER_RECEIPT,
            customer_id=request.customer_id,
            currency=request.currency,
            amount=amount,
            method=request.method or "",
            reference=request.reference or "",
            paid_at=request.paid_at,
            allocations=request.allocations,
            db=db,
        )
        return _payment_response(db, tenant_id, replay)
    selected = _selected_allocations(
        db,
        tenant_id,
        request.customer_id,
        request.currency,
        amount,
        request.allocations,
    )
    payment = Payment(
        tenant_id=tenant_id,
        customer_id=request.customer_id,
        direction=PaymentDirection.CUSTOMER_RECEIPT,
        amount=amount,
        currency=request.currency,
        method=request.method,
        reference=request.reference,
        paid_at=request.paid_at,
        recorded_by_user_id=actor_user_id,
        notes=request.notes,
        idempotency_key=request.idempotency_key,
    )
    db.add(payment)
    db.flush()
    db.add(
        CustomerLedgerEntry(
            tenant_id=tenant_id,
            customer_id=request.customer_id,
            currency=request.currency,
            signed_amount=money(-amount),
            entry_type=LedgerEntryType.CUSTOMER_PAYMENT,
            source_type="PAYMENT",
            source_id=payment.id,
            source_effect_key=f"payment:{payment.id}:receipt",
            effective_at=request.paid_at,
            actor_user_id=actor_user_id,
            idempotency_key=request.idempotency_key,
            metadata_json={"method": request.method, "reference": request.reference},
        )
    )
    for index, (target, allocation_amount) in enumerate(selected, start=1):
        db.add(
            PaymentAllocation(
                tenant_id=tenant_id,
                payment_id=payment.id,
                customer_id=request.customer_id,
                target_ledger_entry_id=target.id,
                currency=request.currency,
                amount=allocation_amount,
                kind=AllocationKind.APPLY,
                created_by_user_id=actor_user_id,
                idempotency_key=uuid5(
                    NAMESPACE_URL,
                    f"tawzeevo:{tenant_id}:payment:{payment.id}:allocation:{index}:{target.id}",
                ),
            )
        )
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action="customer_receipt_recorded",
            entity_type="payment",
            entity_id=payment.id,
            details={
                "customer_id": str(request.customer_id),
                "amount": str(amount),
                "currency": request.currency,
                "allocation_mode": "FIFO" if request.allocations is None else "OWNER_SELECTED",
                "allocation_count": len(selected),
            },
        )
    )
    commit_and_restore_tenant_scope(db, tenant_id)
    db.refresh(payment)
    return _payment_response(db, tenant_id, payment)


def reverse_customer_receipt(
    db: Session,
    tenant_id: UUID,
    actor_user_id: UUID,
    payment_id: UUID,
    request: PaymentReversalRequest,
) -> CustomerPaymentResponse:
    _lock_idempotency_key(db, request.idempotency_key)
    original = db.scalar(
        select(Payment).where(Payment.tenant_id == tenant_id, Payment.id == payment_id)
    )
    if original is None or original.direction != PaymentDirection.CUSTOMER_RECEIPT:
        raise AppError(404, "CUSTOMER_RECEIPT_NOT_FOUND", "Customer receipt was not found")
    if original.customer_id is None:
        raise AppError(409, "CUSTOMER_PAYMENT_REQUIRED", "Payment is not a customer payment")
    _locked_customer(db, tenant_id, original.customer_id)
    replay = _existing_payment(db, tenant_id, request.idempotency_key)
    if replay is not None:
        _validate_replay(
            replay,
            direction=PaymentDirection.CUSTOMER_RECEIPT_REVERSAL,
            customer_id=original.customer_id,
            currency=original.currency,
            amount=original.amount,
        )
        if replay.reverses_payment_id != original.id:
            raise AppError(409, "IDEMPOTENCY_KEY_REUSED", "Reversal key belongs to another receipt")
        return _payment_response(db, tenant_id, replay)
    existing_reversal = db.scalar(
        select(Payment).where(
            Payment.tenant_id == tenant_id,
            Payment.reverses_payment_id == original.id,
        )
    )
    if existing_reversal is not None:
        raise AppError(409, "PAYMENT_ALREADY_REVERSED", "Customer receipt is already reversed")
    reason = request.reason.strip()
    if not reason:
        raise AppError(422, "REVERSAL_REASON_REQUIRED", "A reversal reason is required")
    reversal = Payment(
        tenant_id=tenant_id,
        customer_id=original.customer_id,
        direction=PaymentDirection.CUSTOMER_RECEIPT_REVERSAL,
        amount=money(original.amount),
        currency=original.currency,
        method=original.method,
        reference=original.reference,
        paid_at=datetime.now(UTC),
        recorded_by_user_id=actor_user_id,
        reverses_payment_id=original.id,
        notes=reason,
        idempotency_key=request.idempotency_key,
    )
    db.add(reversal)
    db.flush()
    receipt_ledger = db.scalar(
        select(CustomerLedgerEntry).where(
            CustomerLedgerEntry.tenant_id == tenant_id,
            CustomerLedgerEntry.source_effect_key == f"payment:{original.id}:receipt",
        )
    )
    if receipt_ledger is None:
        raise AppError(409, "PAYMENT_LEDGER_EFFECT_MISSING", "Receipt ledger effect is missing")
    db.add(
        CustomerLedgerEntry(
            tenant_id=tenant_id,
            customer_id=original.customer_id,
            currency=original.currency,
            signed_amount=money(original.amount),
            entry_type=LedgerEntryType.CUSTOMER_PAYMENT_REVERSAL,
            source_type="PAYMENT",
            source_id=reversal.id,
            source_effect_key=f"payment:{original.id}:reversal",
            effective_at=reversal.paid_at,
            actor_user_id=actor_user_id,
            reverses_entry_id=receipt_ledger.id,
            idempotency_key=request.idempotency_key,
            metadata_json={"reason": reason},
        )
    )
    rows = _allocation_rows(db, tenant_id, payment_id=original.id)
    effective_by_apply, _by_target = _effective_allocation_amounts(rows)
    applies = {row.id: row for row in rows if row.kind == AllocationKind.APPLY}
    for allocation_id, effective in effective_by_apply.items():
        if effective <= 0:
            continue
        allocation = applies[allocation_id]
        db.add(
            PaymentAllocation(
                tenant_id=tenant_id,
                payment_id=original.id,
                customer_id=original.customer_id,
                target_ledger_entry_id=allocation.target_ledger_entry_id,
                currency=original.currency,
                amount=effective,
                kind=AllocationKind.REVERSAL,
                reverses_allocation_id=allocation.id,
                created_by_user_id=actor_user_id,
                idempotency_key=uuid5(
                    NAMESPACE_URL,
                    f"tawzeevo:{tenant_id}:payment:{original.id}:reversal:{allocation.id}",
                ),
            )
        )
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action="customer_receipt_reversed",
            entity_type="payment",
            entity_id=reversal.id,
            details={"reverses_payment_id": str(original.id), "reason": reason},
        )
    )
    commit_and_restore_tenant_scope(db, tenant_id)
    db.refresh(reversal)
    return _payment_response(db, tenant_id, reversal)


def record_customer_refund(
    db: Session,
    tenant_id: UUID,
    actor_user_id: UUID,
    request: CustomerRefundRequest,
) -> CustomerPaymentResponse:
    _lock_idempotency_key(db, request.idempotency_key)
    _locked_customer(db, tenant_id, request.customer_id)
    amount = money(request.amount)
    replay = _existing_payment(db, tenant_id, request.idempotency_key)
    if replay is not None:
        _validate_replay(
            replay,
            direction=PaymentDirection.CUSTOMER_REFUND,
            customer_id=request.customer_id,
            currency=request.currency,
            amount=amount,
            method=request.method or "",
            reference=request.reference or "",
            paid_at=request.paid_at,
        )
        return _payment_response(db, tenant_id, replay)
    balance = _customer_balance(db, tenant_id, request.customer_id, request.currency)
    available_credit = money(max(Decimal("0"), -balance))
    if amount > available_credit:
        raise AppError(
            409,
            "REFUND_EXCEEDS_AVAILABLE_CREDIT",
            "Refund cannot exceed the customer's available credit in this currency",
        )
    refund = Payment(
        tenant_id=tenant_id,
        customer_id=request.customer_id,
        direction=PaymentDirection.CUSTOMER_REFUND,
        amount=amount,
        currency=request.currency,
        method=request.method,
        reference=request.reference,
        paid_at=request.paid_at,
        recorded_by_user_id=actor_user_id,
        notes=request.notes,
        idempotency_key=request.idempotency_key,
    )
    db.add(refund)
    db.flush()
    db.add(
        CustomerLedgerEntry(
            tenant_id=tenant_id,
            customer_id=request.customer_id,
            currency=request.currency,
            signed_amount=amount,
            entry_type=LedgerEntryType.CUSTOMER_REFUND,
            source_type="PAYMENT",
            source_id=refund.id,
            source_effect_key=f"payment:{refund.id}:refund",
            effective_at=request.paid_at,
            actor_user_id=actor_user_id,
            idempotency_key=request.idempotency_key,
            metadata_json={"method": request.method, "reference": request.reference},
        )
    )
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action="customer_refund_recorded",
            entity_type="payment",
            entity_id=refund.id,
            details={
                "customer_id": str(request.customer_id),
                "amount": str(amount),
                "currency": request.currency,
                "available_credit_before": str(available_credit),
            },
        )
    )
    commit_and_restore_tenant_scope(db, tenant_id)
    db.refresh(refund)
    return _payment_response(db, tenant_id, refund)
