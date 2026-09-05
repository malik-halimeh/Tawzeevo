from __future__ import annotations

from collections import defaultdict
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
    OpeningBalanceRequest,
)
from tawzeevo_api.services.cash_van import get_customer
from tawzeevo_api.services.invoice_editor import money


def _entry_response(entry: CustomerLedgerEntry) -> CustomerLedgerEntryResponse:
    return CustomerLedgerEntryResponse(
        id=entry.id,
        tenant_id=entry.tenant_id,
        customer_id=entry.customer_id,
        currency=entry.currency,
        signed_amount=money(entry.signed_amount),
        entry_type=entry.entry_type,
        effective_at=entry.effective_at,
        created_at=entry.created_at,
    )


def create_opening_balance(
    db: Session,
    tenant_id: UUID,
    actor_user_id: UUID,
    request: OpeningBalanceRequest,
) -> CustomerLedgerEntryResponse:
    get_customer(db, tenant_id, request.customer_id)
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
        metadata_json={"note": request.note} if request.note else {},
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
            },
        )
    )
    commit_and_restore_tenant_scope(db, tenant_id)
    db.refresh(entry)
    return _entry_response(entry)


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
        standalone: list[CustomerLedgerEntry] = []
        for entry in currency_entries:
            if entry.source_type == "INVOICE" and entry.source_id is not None:
                invoice_groups[entry.source_id].append(entry)
            elif entry.signed_amount > 0:
                standalone.append(entry)

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
        for entry in standalone:
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
