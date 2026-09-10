from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    AllocationKind,
    AuditEvent,
    Customer,
    CustomerLedgerEntry,
    LedgerEntryType,
    PaymentAllocation,
    TenantFinancialSettings,
)
from tawzeevo_api.repositories.tenancy import commit_and_restore_tenant_scope
from tawzeevo_api.schemas.customer_ledger import (
    CustomerBalanceResponse,
    CustomerBalancesResponse,
    CustomerDebtListResponse,
    CustomerDebtResponse,
    CustomerLedgerEntryResponse,
    FinancialSettingsResponse,
    OpeningBalanceCorrectionRequest,
    OpeningBalanceRequest,
)
from tawzeevo_api.services.cash_van import get_customer
from tawzeevo_api.services.invoice_editor import money


@dataclass(frozen=True)
class OpeningObligationPosition:
    target: CustomerLedgerEntry
    original_amount: Decimal
    allocated_amount: Decimal
    outstanding_amount: Decimal


def opening_obligation_positions(
    entries: list[CustomerLedgerEntry],
    allocated_by_target: Mapping[UUID, Decimal],
) -> list[OpeningObligationPosition]:
    openings = [entry for entry in entries if entry.entry_type == LedgerEntryType.OPENING_BALANCE]
    corrections_by_opening: dict[UUID, list[CustomerLedgerEntry]] = defaultdict(list)
    for entry in entries:
        if (
            entry.entry_type == LedgerEntryType.OPENING_BALANCE_CORRECTION
            and entry.reverses_entry_id is not None
        ):
            corrections_by_opening[entry.reverses_entry_id].append(entry)

    positions: list[OpeningObligationPosition] = []
    for opening in openings:
        position_entries = (opening, *corrections_by_opening.get(opening.id, []))
        original_amount = money(
            sum((entry.signed_amount for entry in position_entries), Decimal("0"))
        )
        allocated_amount = money(
            sum(
                (allocated_by_target.get(entry.id, Decimal("0")) for entry in position_entries),
                Decimal("0"),
            )
        )
        outstanding_amount = money(original_amount - allocated_amount)
        if original_amount > 0 and outstanding_amount > 0:
            positions.append(
                OpeningObligationPosition(
                    target=opening,
                    original_amount=original_amount,
                    allocated_amount=allocated_amount,
                    outstanding_amount=outstanding_amount,
                )
            )
    return positions


def standalone_customer_debt_entries(
    entries: list[CustomerLedgerEntry],
) -> list[CustomerLedgerEntry]:
    return [
        entry
        for entry in entries
        if entry.entry_type == LedgerEntryType.AUTHORIZED_MANUAL_ADJUSTMENT
        and entry.signed_amount > 0
    ]


def _entry_response(entry: CustomerLedgerEntry) -> CustomerLedgerEntryResponse:
    return CustomerLedgerEntryResponse(
        id=entry.id,
        tenant_id=entry.tenant_id,
        customer_id=entry.customer_id,
        currency=entry.currency,
        signed_amount=money(entry.signed_amount),
        entry_type=entry.entry_type,
        reverses_entry_id=entry.reverses_entry_id,
        effective_at=entry.effective_at,
        created_at=entry.created_at,
    )


def create_opening_balance(
    db: Session,
    tenant_id: UUID,
    actor_user_id: UUID,
    request: OpeningBalanceRequest,
) -> CustomerLedgerEntryResponse:
    customer = db.scalar(
        select(Customer)
        .where(Customer.tenant_id == tenant_id, Customer.id == request.customer_id)
        .with_for_update()
    )
    if customer is None:
        raise AppError(404, "CUSTOMER_NOT_FOUND", "Customer was not found")
    replay = db.scalar(
        select(CustomerLedgerEntry).where(
            CustomerLedgerEntry.tenant_id == tenant_id,
            CustomerLedgerEntry.idempotency_key == request.idempotency_key,
        )
    )
    if replay is not None:
        if (
            replay.entry_type != LedgerEntryType.OPENING_BALANCE
            or replay.customer_id != request.customer_id
            or replay.currency != request.currency
            or money(replay.signed_amount) != money(request.signed_amount)
            or replay.effective_at != request.effective_at
        ):
            raise AppError(
                409,
                "IDEMPOTENCY_KEY_REUSED",
                "Idempotency key was already used for a different ledger effect",
            )
        return _entry_response(replay)
    existing_opening = db.scalar(
        select(CustomerLedgerEntry.id).where(
            CustomerLedgerEntry.tenant_id == tenant_id,
            CustomerLedgerEntry.customer_id == request.customer_id,
            CustomerLedgerEntry.currency == request.currency,
            CustomerLedgerEntry.entry_type == LedgerEntryType.OPENING_BALANCE,
        )
    )
    if existing_opening is not None:
        raise AppError(
            409,
            "OPENING_BALANCE_ALREADY_EXISTS",
            "An initial opening balance already exists for this customer and currency",
        )
    classification = "HISTORICAL_CREDIT" if request.signed_amount < 0 else "HISTORICAL_DEBT"
    entry = CustomerLedgerEntry(
        tenant_id=tenant_id,
        customer_id=request.customer_id,
        currency=request.currency,
        signed_amount=money(request.signed_amount),
        entry_type=LedgerEntryType.OPENING_BALANCE,
        source_type="OPENING_BALANCE",
        source_effect_key=f"opening-balance:{request.idempotency_key}",
        effective_at=request.effective_at,
        actor_user_id=actor_user_id,
        idempotency_key=request.idempotency_key,
        metadata_json={
            **({"note": request.note} if request.note else {}),
            "opening_classification": classification,
        },
    )
    db.add(entry)
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action="customer_opening_balance_recorded",
            entity_type="customer",
            entity_id=request.customer_id,
            details={
                "currency": request.currency,
                "signed_amount": str(money(request.signed_amount)),
                "effective_at": request.effective_at.isoformat(),
                "opening_classification": classification,
            },
        )
    )
    commit_and_restore_tenant_scope(db, tenant_id)
    db.refresh(entry)
    return _entry_response(entry)


def correct_opening_balance(
    db: Session,
    tenant_id: UUID,
    actor_user_id: UUID,
    entry_id: UUID,
    request: OpeningBalanceCorrectionRequest,
) -> CustomerLedgerEntryResponse:
    reason = request.reason.strip()
    if not reason:
        raise AppError(422, "CORRECTION_REASON_REQUIRED", "A correction reason is required")
    original = db.scalar(
        select(CustomerLedgerEntry)
        .where(CustomerLedgerEntry.tenant_id == tenant_id, CustomerLedgerEntry.id == entry_id)
        .with_for_update()
    )
    if original is None or original.entry_type != LedgerEntryType.OPENING_BALANCE:
        raise AppError(404, "OPENING_BALANCE_NOT_FOUND", "Opening balance was not found")
    replay = db.scalar(
        select(CustomerLedgerEntry).where(
            CustomerLedgerEntry.tenant_id == tenant_id,
            CustomerLedgerEntry.idempotency_key == request.idempotency_key,
        )
    )
    if replay is not None:
        if (
            replay.entry_type != LedgerEntryType.OPENING_BALANCE_CORRECTION
            or replay.reverses_entry_id != original.id
            or replay.metadata_json.get("reason") != reason
            or money(Decimal(replay.metadata_json["corrected_signed_amount"]))
            != money(request.corrected_signed_amount)
        ):
            raise AppError(
                409,
                "IDEMPOTENCY_KEY_REUSED",
                "Idempotency key was already used for a different ledger effect",
            )
        return _entry_response(replay)
    existing_correction = db.scalar(
        select(CustomerLedgerEntry.id).where(
            CustomerLedgerEntry.tenant_id == tenant_id,
            CustomerLedgerEntry.reverses_entry_id == original.id,
        )
    )
    if existing_correction is not None:
        raise AppError(
            409, "OPENING_BALANCE_ALREADY_CORRECTED", "Opening balance is already corrected"
        )
    corrected_amount = money(request.corrected_signed_amount)
    correction_amount = money(corrected_amount - original.signed_amount)
    if correction_amount == 0:
        raise AppError(409, "OPENING_BALANCE_UNCHANGED", "Corrected opening balance is unchanged")
    corrected_classification = (
        "REVERSED"
        if corrected_amount == 0
        else "HISTORICAL_CREDIT"
        if corrected_amount < 0
        else "HISTORICAL_DEBT"
    )
    correction = CustomerLedgerEntry(
        tenant_id=tenant_id,
        customer_id=original.customer_id,
        currency=original.currency,
        signed_amount=correction_amount,
        entry_type=LedgerEntryType.OPENING_BALANCE_CORRECTION,
        source_type="OPENING_BALANCE_CORRECTION",
        source_id=original.id,
        source_effect_key=f"opening-balance-correction:{original.id}",
        effective_at=datetime.now(UTC),
        actor_user_id=actor_user_id,
        reverses_entry_id=original.id,
        idempotency_key=request.idempotency_key,
        metadata_json={
            "reason": reason,
            "original_opening_entry_id": str(original.id),
            "original_signed_amount": str(money(original.signed_amount)),
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
            actor_user_id=actor_user_id,
            action="customer_opening_balance_corrected",
            entity_type="customer_ledger_entry",
            entity_id=correction.id,
            details={
                "customer_id": str(original.customer_id),
                "currency": original.currency,
                "original_opening_entry_id": str(original.id),
                "original_signed_amount": str(money(original.signed_amount)),
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


def customer_balances(db: Session, tenant_id: UUID, customer_id: UUID) -> CustomerBalancesResponse:
    customer = get_customer(db, tenant_id, customer_id)
    rows = db.execute(
        select(
            CustomerLedgerEntry.currency,
            func.sum(CustomerLedgerEntry.signed_amount),
        )
        .where(
            CustomerLedgerEntry.tenant_id == tenant_id,
            CustomerLedgerEntry.customer_id == customer_id,
        )
        .group_by(CustomerLedgerEntry.currency)
        .order_by(CustomerLedgerEntry.currency.asc())
    ).all()
    return CustomerBalancesResponse(
        customer_id=customer.id,
        customer_name=customer.name,
        balances=[
            CustomerBalanceResponse(currency=currency, balance=money(Decimal(balance)))
            for currency, balance in rows
        ],
    )


def get_financial_settings(db: Session, tenant_id: UUID) -> FinancialSettingsResponse:
    settings = db.get(TenantFinancialSettings, tenant_id)
    return FinancialSettingsResponse(
        tenant_id=tenant_id,
        customer_overdue_threshold_days=(
            settings.customer_overdue_threshold_days if settings is not None else None
        ),
    )


def set_overdue_threshold(
    db: Session,
    tenant_id: UUID,
    actor_user_id: UUID,
    threshold_days: int | None,
) -> FinancialSettingsResponse:
    settings = db.scalar(
        select(TenantFinancialSettings)
        .where(TenantFinancialSettings.tenant_id == tenant_id)
        .with_for_update()
    )
    if settings is None:
        settings = TenantFinancialSettings(
            tenant_id=tenant_id,
            customer_overdue_threshold_days=threshold_days,
        )
        db.add(settings)
    else:
        settings.customer_overdue_threshold_days = threshold_days
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action="customer_overdue_threshold_changed",
            entity_type="tenant_financial_settings",
            entity_id=tenant_id,
            details={"customer_overdue_threshold_days": threshold_days},
        )
    )
    commit_and_restore_tenant_scope(db, tenant_id)
    return FinancialSettingsResponse(
        tenant_id=tenant_id,
        customer_overdue_threshold_days=threshold_days,
    )


def _allocation_totals(db: Session, tenant_id: UUID) -> dict[UUID, Decimal]:
    allocations = list(
        db.scalars(select(PaymentAllocation).where(PaymentAllocation.tenant_id == tenant_id))
    )
    totals: dict[UUID, Decimal] = defaultdict(lambda: Decimal("0.0000"))
    for allocation in allocations:
        sign = Decimal("1") if allocation.kind == AllocationKind.APPLY else Decimal("-1")
        totals[allocation.target_ledger_entry_id] = money(
            totals[allocation.target_ledger_entry_id] + (sign * allocation.amount)
        )
    return totals


def customer_debts(
    db: Session,
    tenant_id: UUID,
    *,
    now: datetime | None = None,
) -> CustomerDebtListResponse:
    now = now or datetime.now(UTC)
    settings = db.get(TenantFinancialSettings, tenant_id)
    threshold = settings.customer_overdue_threshold_days if settings is not None else None
    customers = {
        customer.id: customer
        for customer in db.scalars(
            select(Customer)
            .where(Customer.tenant_id == tenant_id)
            .order_by(Customer.name.asc(), Customer.id.asc())
        )
    }
    entries = list(
        db.scalars(
            select(CustomerLedgerEntry)
            .where(CustomerLedgerEntry.tenant_id == tenant_id)
            .order_by(
                CustomerLedgerEntry.effective_at.asc(),
                CustomerLedgerEntry.created_at.asc(),
                CustomerLedgerEntry.id.asc(),
            )
        )
    )
    allocation_totals = _allocation_totals(db, tenant_id)
    grouped: dict[tuple[UUID, str], list[CustomerLedgerEntry]] = defaultdict(list)
    for entry in entries:
        grouped[(entry.customer_id, entry.currency)].append(entry)

    debts: list[CustomerDebtResponse] = []
    for (customer_id, currency), currency_entries in grouped.items():
        balance = money(sum((entry.signed_amount for entry in currency_entries), Decimal("0")))
        if balance <= 0:
            continue
        customer = customers.get(customer_id)
        if customer is None:
            continue

        invoice_groups: dict[UUID, list[CustomerLedgerEntry]] = defaultdict(list)
        non_invoice_entries: list[CustomerLedgerEntry] = []
        for entry in currency_entries:
            if entry.source_type == "INVOICE" and entry.source_id is not None:
                invoice_groups[entry.source_id].append(entry)
            else:
                non_invoice_entries.append(entry)

        obligation_dates: list[datetime] = []
        for invoice_entries in invoice_groups.values():
            canonical_amount = money(
                sum((entry.signed_amount for entry in invoice_entries), Decimal("0"))
            )
            allocated = money(
                sum(
                    (allocation_totals.get(entry.id, Decimal("0")) for entry in invoice_entries),
                    Decimal("0"),
                )
            )
            if money(canonical_amount - allocated) > 0:
                obligation_dates.append(min(entry.effective_at for entry in invoice_entries))
        for position in opening_obligation_positions(non_invoice_entries, allocation_totals):
            obligation_dates.append(position.target.effective_at)
        for entry in standalone_customer_debt_entries(non_invoice_entries):
            if money(entry.signed_amount - allocation_totals.get(entry.id, Decimal("0"))) > 0:
                obligation_dates.append(entry.effective_at)

        oldest = min(obligation_dates) if obligation_dates else None
        age_days = max(0, (now.date() - oldest.date()).days) if oldest is not None else None
        is_overdue = (
            threshold is not None and age_days is not None and age_days > threshold and balance > 0
        )
        debts.append(
            CustomerDebtResponse(
                customer_id=customer.id,
                customer_name=customer.name,
                customer_phone=customer.phone,
                currency=currency,
                balance=balance,
                oldest_unpaid_at=oldest,
                overdue_age_days=age_days,
                overdue_threshold_days=threshold,
                is_overdue=is_overdue,
                alert_key=(f"customer-overdue:{customer.id}:{currency}" if is_overdue else None),
            )
        )
    debts.sort(
        key=lambda debt: (
            not debt.is_overdue,
            -(debt.overdue_age_days if debt.overdue_age_days is not None else -1),
            debt.customer_name.casefold(),
            debt.currency,
        )
    )
    return CustomerDebtListResponse(debts=debts)
