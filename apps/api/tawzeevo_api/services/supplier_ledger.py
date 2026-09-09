"""Aggregate supplier payable; never allocate supplier payments to purchases."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    AuditEvent,
    Payment,
    PaymentDirection,
    SupplierLedgerEntry,
    SupplierLedgerEntryType,
    TenantSupplier,
)
from tawzeevo_api.repositories.tenancy import commit_and_restore_tenant_scope
from tawzeevo_api.schemas.payments import PaymentReversalRequest
from tawzeevo_api.schemas.supplier_ledger import (
    SupplierBalancesResponse,
    SupplierCurrencyBalance,
    SupplierLedgerEntryResponse,
    SupplierOpeningCorrectionRequest,
    SupplierOpeningRequest,
    SupplierPaymentRequest,
    SupplierPaymentResponse,
)
from tawzeevo_api.services.payments import _existing_payment, _lock_idempotency_key


def _supplier(db: Session, tenant_id: UUID, supplier_id: UUID) -> TenantSupplier:
    supplier = db.scalar(
        select(TenantSupplier)
        .where(
            TenantSupplier.tenant_id == tenant_id,
            TenantSupplier.id == supplier_id,
        )
        .with_for_update()
    )
    if supplier is None:
        raise AppError(404, "SUPPLIER_NOT_FOUND", "Supplier was not found")
    return supplier


def supplier_balances(db: Session, tenant_id: UUID, supplier_id: UUID) -> SupplierBalancesResponse:
    _supplier(db, tenant_id, supplier_id)
    rows = db.execute(
        select(
            SupplierLedgerEntry.currency,
            func.sum(SupplierLedgerEntry.signed_amount),
        )
        .where(
            SupplierLedgerEntry.tenant_id == tenant_id,
            SupplierLedgerEntry.supplier_id == supplier_id,
        )
        .group_by(SupplierLedgerEntry.currency)
        .order_by(SupplierLedgerEntry.currency)
    ).all()
    return SupplierBalancesResponse(
        supplier_id=supplier_id,
        balances=[
            SupplierCurrencyBalance(currency=currency, balance=Decimal(balance))
            for currency, balance in rows
        ],
    )


def _conflict() -> AppError:
    return AppError(409, "IDEMPOTENCY_KEY_REUSED", "Key belongs to a different financial command")


def _entry_response(entry: SupplierLedgerEntry) -> SupplierLedgerEntryResponse:
    return SupplierLedgerEntryResponse(
        id=entry.id,
        tenant_id=entry.tenant_id,
        supplier_id=entry.supplier_id,
        currency=entry.currency,
        signed_amount=entry.signed_amount,
        entry_type=entry.entry_type,
        reverses_entry_id=entry.reverses_entry_id,
        effective_at=entry.effective_at,
        created_at=entry.created_at,
    )


def record_supplier_opening(
    db: Session,
    tenant_id: UUID,
    actor: UUID,
    request: SupplierOpeningRequest,
) -> SupplierBalancesResponse:
    _lock_idempotency_key(db, request.idempotency_key)
    _supplier(db, tenant_id, request.supplier_id)
    prior = db.scalar(
        select(SupplierLedgerEntry).where(
            SupplierLedgerEntry.tenant_id == tenant_id,
            SupplierLedgerEntry.idempotency_key == request.idempotency_key,
        )
    )
    if prior is not None:
        if (
            prior.entry_type != SupplierLedgerEntryType.OPENING_BALANCE
            or prior.supplier_id != request.supplier_id
            or prior.currency != request.currency
            or prior.signed_amount != request.signed_amount
            or prior.effective_at != request.effective_at
            or prior.metadata_json.get("note") != request.note
        ):
            raise _conflict()
        return supplier_balances(db, tenant_id, request.supplier_id)
    if _existing_payment(db, tenant_id, request.idempotency_key) is not None:
        raise _conflict()
    existing_opening = db.scalar(
        select(SupplierLedgerEntry.id).where(
            SupplierLedgerEntry.tenant_id == tenant_id,
            SupplierLedgerEntry.supplier_id == request.supplier_id,
            SupplierLedgerEntry.currency == request.currency,
            SupplierLedgerEntry.entry_type == SupplierLedgerEntryType.OPENING_BALANCE,
        )
    )
    if existing_opening is not None:
        raise AppError(
            409,
            "OPENING_BALANCE_ALREADY_EXISTS",
            "An initial opening balance already exists for this supplier and currency",
        )
    classification = "HISTORICAL_CREDIT" if request.signed_amount < 0 else "HISTORICAL_PAYABLE"
    entry = SupplierLedgerEntry(
        tenant_id=tenant_id,
        supplier_id=request.supplier_id,
        currency=request.currency,
        signed_amount=request.signed_amount,
        entry_type=SupplierLedgerEntryType.OPENING_BALANCE,
        source_type="OPENING_BALANCE",
        source_effect_key=f"opening:{request.idempotency_key}",
        effective_at=request.effective_at,
        actor_user_id=actor,
        idempotency_key=request.idempotency_key,
        metadata_json={"note": request.note, "opening_classification": classification},
    )
    db.add(entry)
    db.flush()
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor,
            action="supplier_opening_balance_recorded",
            entity_type="supplier_ledger_entry",
            entity_id=entry.id,
            details={
                "supplier_id": str(request.supplier_id),
                "currency": request.currency,
                "opening_classification": classification,
            },
        )
    )
    commit_and_restore_tenant_scope(db, tenant_id)
    return supplier_balances(db, tenant_id, request.supplier_id)


def correct_supplier_opening(
    db: Session,
    tenant_id: UUID,
    actor: UUID,
    entry_id: UUID,
    request: SupplierOpeningCorrectionRequest,
) -> SupplierLedgerEntryResponse:
    reason = request.reason.strip()
    if not reason:
        raise AppError(422, "CORRECTION_REASON_REQUIRED", "A correction reason is required")
    original = db.scalar(
        select(SupplierLedgerEntry)
        .where(SupplierLedgerEntry.tenant_id == tenant_id, SupplierLedgerEntry.id == entry_id)
        .with_for_update()
    )
    if original is None or original.entry_type != SupplierLedgerEntryType.OPENING_BALANCE:
        raise AppError(404, "OPENING_BALANCE_NOT_FOUND", "Opening balance was not found")
    _supplier(db, tenant_id, original.supplier_id)
    corrected_amount = request.corrected_signed_amount.quantize(Decimal("0.0001"))
    replay = db.scalar(
        select(SupplierLedgerEntry).where(
            SupplierLedgerEntry.tenant_id == tenant_id,
            SupplierLedgerEntry.idempotency_key == request.idempotency_key,
        )
    )
    if replay is not None:
        if (
            replay.entry_type != SupplierLedgerEntryType.OPENING_BALANCE_CORRECTION
            or replay.reverses_entry_id != original.id
            or replay.metadata_json.get("reason") != reason
            or replay.metadata_json.get("corrected_signed_amount") != str(corrected_amount)
        ):
            raise _conflict()
        return _entry_response(replay)
    if _existing_payment(db, tenant_id, request.idempotency_key) is not None:
        raise _conflict()
    existing_correction = db.scalar(
        select(SupplierLedgerEntry.id).where(
            SupplierLedgerEntry.tenant_id == tenant_id,
            SupplierLedgerEntry.reverses_entry_id == original.id,
        )
    )
    if existing_correction is not None:
        raise AppError(
            409, "OPENING_BALANCE_ALREADY_CORRECTED", "Opening balance is already corrected"
        )
    correction_amount = (corrected_amount - original.signed_amount).quantize(Decimal("0.0001"))
    if correction_amount == 0:
        raise AppError(409, "OPENING_BALANCE_UNCHANGED", "Corrected opening balance is unchanged")
    corrected_classification = (
        "REVERSED"
        if corrected_amount == 0
        else "HISTORICAL_CREDIT"
        if corrected_amount < 0
        else "HISTORICAL_PAYABLE"
    )
    correction = SupplierLedgerEntry(
        tenant_id=tenant_id,
        supplier_id=original.supplier_id,
        currency=original.currency,
        signed_amount=correction_amount,
        entry_type=SupplierLedgerEntryType.OPENING_BALANCE_CORRECTION,
        source_type="OPENING_BALANCE_CORRECTION",
        source_id=original.id,
        source_effect_key=f"supplier-opening-correction:{original.id}",
        effective_at=datetime.now(UTC),
        actor_user_id=actor,
        reverses_entry_id=original.id,
        idempotency_key=request.idempotency_key,
        metadata_json={
            "reason": reason,
            "original_opening_entry_id": str(original.id),
            "original_signed_amount": str(original.signed_amount),
            "corrected_signed_amount": str(corrected_amount),
            "corrected_opening_classification": corrected_classification,
            "correction_kind": "REVERSAL" if corrected_amount == 0 else "CORRECTION",
        },
    )
    db.add(correction)
    db.flush()
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor,
            action="supplier_opening_balance_corrected",
            entity_type="supplier_ledger_entry",
            entity_id=correction.id,
            details={
                "supplier_id": str(original.supplier_id),
                "currency": original.currency,
                "original_opening_entry_id": str(original.id),
                "original_signed_amount": str(original.signed_amount),
                "corrected_signed_amount": str(corrected_amount),
                "corrected_opening_classification": corrected_classification,
                "correction_kind": "REVERSAL" if corrected_amount == 0 else "CORRECTION",
                "reason": reason,
            },
        )
    )
    commit_and_restore_tenant_scope(db, tenant_id)
    db.refresh(correction)
    return _entry_response(correction)


def _write_payment_effect(
    db: Session, payment: Payment, actor: UUID, original: Payment | None = None
) -> None:
    db.add(payment)
    db.flush()
    original_entry = None
    if original is not None:
        original_entry = db.scalar(
            select(SupplierLedgerEntry).where(
                SupplierLedgerEntry.tenant_id == payment.tenant_id,
                SupplierLedgerEntry.source_effect_key == f"supplier-payment:{original.id}",
            )
        )
        if original_entry is None:
            raise AppError(
                409, "PAYMENT_LEDGER_EFFECT_MISSING", "Supplier payment effect is missing"
            )
    db.add(
        SupplierLedgerEntry(
            tenant_id=payment.tenant_id,
            supplier_id=payment.supplier_id,
            currency=payment.currency,
            signed_amount=payment.amount if original else -payment.amount,
            entry_type=(
                SupplierLedgerEntryType.SUPPLIER_PAYMENT_REVERSAL
                if original
                else SupplierLedgerEntryType.SUPPLIER_PAYMENT
            ),
            source_type="PAYMENT",
            source_id=payment.id,
            source_effect_key=f"supplier-payment:{payment.id}",
            effective_at=payment.paid_at,
            actor_user_id=actor,
            reverses_entry_id=original_entry.id if original_entry else None,
            idempotency_key=payment.idempotency_key,
        )
    )
    db.add(
        AuditEvent(
            tenant_id=payment.tenant_id,
            actor_user_id=actor,
            action="supplier_payment_reversed" if original else "supplier_payment_recorded",
            entity_type="payment",
            entity_id=payment.id,
            details={"supplier_id": str(payment.supplier_id), "currency": payment.currency},
        )
    )
    commit_and_restore_tenant_scope(db, payment.tenant_id)


def record_supplier_payment(
    db: Session,
    tenant_id: UUID,
    actor: UUID,
    request: SupplierPaymentRequest,
) -> SupplierPaymentResponse:
    _lock_idempotency_key(db, request.idempotency_key)
    _supplier(db, tenant_id, request.supplier_id)
    prior = _existing_payment(db, tenant_id, request.idempotency_key)
    if prior is not None:
        if prior.direction != PaymentDirection.SUPPLIER_PAYMENT or any(
            getattr(prior, field) != getattr(request, field)
            for field in (
                "supplier_id",
                "currency",
                "amount",
                "paid_at",
                "method",
                "reference",
                "notes",
            )
        ):
            raise _conflict()
        return SupplierPaymentResponse.model_validate(prior)
    if (
        db.scalar(
            select(SupplierLedgerEntry.id).where(
                SupplierLedgerEntry.tenant_id == tenant_id,
                SupplierLedgerEntry.idempotency_key == request.idempotency_key,
            )
        )
        is not None
    ):
        raise _conflict()
    payment = Payment(
        tenant_id=tenant_id,
        recorded_by_user_id=actor,
        direction=PaymentDirection.SUPPLIER_PAYMENT,
        **request.model_dump(),
    )
    _write_payment_effect(db, payment, actor)
    return SupplierPaymentResponse.model_validate(payment)


def reverse_supplier_payment(
    db: Session,
    tenant_id: UUID,
    actor: UUID,
    payment_id: UUID,
    request: PaymentReversalRequest,
) -> SupplierPaymentResponse:
    reason = request.reason.strip()
    if not reason:
        raise AppError(422, "REVERSAL_REASON_REQUIRED", "A reversal reason is required")
    _lock_idempotency_key(db, request.idempotency_key)
    original = db.scalar(
        select(Payment).where(Payment.tenant_id == tenant_id, Payment.id == payment_id)
    )
    if original is None or original.direction != PaymentDirection.SUPPLIER_PAYMENT:
        raise AppError(404, "SUPPLIER_PAYMENT_NOT_FOUND", "Supplier payment was not found")
    assert original.supplier_id is not None
    _supplier(db, tenant_id, original.supplier_id)
    prior = _existing_payment(db, tenant_id, request.idempotency_key)
    if prior is not None:
        if (
            prior.direction != PaymentDirection.SUPPLIER_PAYMENT_REVERSAL
            or prior.reverses_payment_id != original.id
            or prior.notes != reason
        ):
            raise _conflict()
        return SupplierPaymentResponse.model_validate(prior)
    if (
        db.scalar(
            select(Payment.id).where(
                Payment.tenant_id == tenant_id, Payment.reverses_payment_id == original.id
            )
        )
        is not None
    ):
        raise AppError(409, "PAYMENT_ALREADY_REVERSED", "Supplier payment is already reversed")
    if (
        db.scalar(
            select(SupplierLedgerEntry.id).where(
                SupplierLedgerEntry.tenant_id == tenant_id,
                SupplierLedgerEntry.idempotency_key == request.idempotency_key,
            )
        )
        is not None
    ):
        raise _conflict()
    reversal = Payment(
        tenant_id=tenant_id,
        supplier_id=original.supplier_id,
        direction=PaymentDirection.SUPPLIER_PAYMENT_REVERSAL,
        amount=original.amount,
        currency=original.currency,
        paid_at=datetime.now(UTC),
        method=original.method,
        reference=original.reference,
        notes=reason,
        recorded_by_user_id=actor,
        reverses_payment_id=original.id,
        idempotency_key=request.idempotency_key,
    )
    _write_payment_effect(db, reversal, actor, original)
    return SupplierPaymentResponse.model_validate(reversal)
