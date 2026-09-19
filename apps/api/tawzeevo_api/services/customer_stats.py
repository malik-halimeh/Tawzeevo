"""Customer lifetime statistics (PHASE_08.md D; D-069, D-072).

Attribution is the owner-resolved `customer_id` on the invoice — a storefront hint never counts.
Everything is recomputed from confirmed, non-cancelled current revisions, receipts and the ledger,
per currency, reproducibly. Duplicate customers are never merged: each id reports only itself.
A statistic without enough data says so rather than inventing a value.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    Category,
    Customer,
    CustomerLedgerEntry,
    Invoice,
    InvoiceRevision,
    InvoiceRevisionItem,
    InvoiceStatus,
    OrderCancellationRequest,
    Payment,
    PaymentAllocation,
    PaymentDirection,
    TenantFinancialSettings,
    TenantProduct,
)
from tawzeevo_api.repositories.tenancy import set_tenant_scope
from tawzeevo_api.schemas.customer_stats import (
    CurrencyStat,
    CustomerLifetimeResponse,
    GradePoint,
    MonthlySpend,
    TopItem,
)
from tawzeevo_api.services.invoice_editor import money

TENANT_TZ = ZoneInfo("Asia/Beirut")
ZERO = Decimal("0.0000")


def _customer(db: Session, tenant_id: UUID, customer_id: UUID) -> Customer:
    set_tenant_scope(db, tenant_id)
    row = db.get(Customer, customer_id)
    if row is None or row.tenant_id != tenant_id:
        raise AppError(404, "CUSTOMER_NOT_FOUND", "Customer was not found")
    return row


def customer_lifetime(db: Session, tenant_id: UUID, customer_id: UUID) -> CustomerLifetimeResponse:
    customer = _customer(db, tenant_id, customer_id)
    invoices = list(
        db.execute(
            select(Invoice, InvoiceRevision)
            .join(InvoiceRevision, InvoiceRevision.id == Invoice.current_revision_id)
            .where(
                Invoice.tenant_id == tenant_id,
                Invoice.customer_id == customer.id,  # owner-resolved attribution only (D-072)
                Invoice.status == InvoiceStatus.CONFIRMED,
            )
            .order_by(Invoice.confirmed_at.asc())
        ).all()
    )

    # ---- financial, per currency
    purchased: dict[str, Decimal] = defaultdict(Decimal)
    discounts: dict[str, Decimal] = defaultdict(Decimal)
    markups: dict[str, Decimal] = defaultdict(Decimal)
    largest: dict[str, Decimal] = defaultdict(Decimal)
    counts: dict[str, int] = defaultdict(int)
    monthly: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    for invoice, revision in invoices:
        currency = revision.currency
        net = Decimal(revision.net_sales)
        purchased[currency] += net
        discounts[currency] += Decimal(revision.discount_total)
        markups[currency] += Decimal(revision.markup_total)
        largest[currency] = max(largest[currency], net)
        counts[currency] += 1
        if invoice.confirmed_at is not None:
            monthly[(currency, invoice.confirmed_at.astimezone(TENANT_TZ).strftime("%Y-%m"))] += net
    receipts: dict[str, Decimal] = defaultdict(Decimal)
    refunds: dict[str, Decimal] = defaultdict(Decimal)
    for currency, direction, total in db.execute(
        select(Payment.currency, Payment.direction, func.sum(Payment.amount))
        .where(Payment.tenant_id == tenant_id, Payment.customer_id == customer.id)
        .group_by(Payment.currency, Payment.direction)
    ).all():
        amount = Decimal(total or 0)
        if direction == PaymentDirection.CUSTOMER_RECEIPT:
            receipts[currency] += amount
        elif direction == PaymentDirection.CUSTOMER_RECEIPT_REVERSAL:
            receipts[currency] -= amount
        elif direction == PaymentDirection.CUSTOMER_REFUND:
            refunds[currency] += amount
    balances: dict[str, Decimal] = {
        currency: Decimal(total or 0)
        for currency, total in db.execute(
            select(CustomerLedgerEntry.currency, func.sum(CustomerLedgerEntry.signed_amount))
            .where(
                CustomerLedgerEntry.tenant_id == tenant_id,
                CustomerLedgerEntry.customer_id == customer.id,
            )
            .group_by(CustomerLedgerEntry.currency)
        ).all()
    }
    currencies = sorted(set(purchased) | set(receipts) | set(balances) | set(refunds))
    financial = [
        CurrencyStat(
            currency=c,
            total_purchased=money(purchased[c]),
            invoice_count=counts[c],
            largest_invoice=money(largest[c]) if counts[c] else None,
            average_invoice=money(purchased[c] / counts[c]) if counts[c] else None,
            total_receipts=money(receipts[c]),
            total_refunds=money(refunds[c]),
            outstanding=money(max(ZERO, balances.get(c, ZERO))),
            credit=money(max(ZERO, -balances.get(c, ZERO))),
            total_discounts=money(discounts[c]),
            total_markups=money(markups[c]),
        )
        for c in currencies
    ]

    # ---- activity
    dates = [invoice.confirmed_at for invoice, _ in invoices if invoice.confirmed_at is not None]
    first_purchase = dates[0] if dates else None
    latest_purchase = dates[-1] if dates else None
    average_days: Decimal | None = None
    if len(dates) >= 2:
        span_days = Decimal((dates[-1] - dates[0]).total_seconds()) / Decimal(86400)
        average_days = money(span_days / Decimal(len(dates) - 1))
    purchases_per_month: Decimal | None = None
    if first_purchase is not None and latest_purchase is not None and len(dates) >= 2:
        months = max(Decimal("1"), Decimal((latest_purchase - first_purchase).days) / Decimal(30))
        purchases_per_month = money(Decimal(len(dates)) / months)

    # ---- late payments (D-069): receipts allocated to a charge after the overdue threshold
    settings = db.scalar(
        select(TenantFinancialSettings).where(TenantFinancialSettings.tenant_id == tenant_id)
    )
    threshold = settings.customer_overdue_threshold_days if settings else None
    late_count = 0
    if threshold is not None:
        charges = {
            row.id: row
            for row in db.scalars(
                select(CustomerLedgerEntry).where(
                    CustomerLedgerEntry.tenant_id == tenant_id,
                    CustomerLedgerEntry.customer_id == customer.id,
                    CustomerLedgerEntry.entry_type == "INVOICE_CHARGE",
                )
            )
        }
        if charges:
            late_ids: set[UUID] = set()
            for allocation, payment in db.execute(
                select(PaymentAllocation, Payment)
                .join(Payment, Payment.id == PaymentAllocation.payment_id)
                .where(
                    PaymentAllocation.tenant_id == tenant_id,
                    PaymentAllocation.customer_id == customer.id,
                    PaymentAllocation.target_ledger_entry_id.in_(list(charges)),
                )
            ).all():
                charge = charges[allocation.target_ledger_entry_id]
                if (payment.paid_at - charge.effective_at).days > threshold:
                    late_ids.add(charge.id)
            late_count = len(late_ids)

    # ---- cancellation requests on this customer's storefront orders
    cancellation_requests = int(
        db.scalar(
            select(func.count())
            .select_from(OrderCancellationRequest)
            .join(Invoice, Invoice.order_id == OrderCancellationRequest.order_id)
            .where(Invoice.tenant_id == tenant_id, Invoice.customer_id == customer.id)
        )
        or 0
    )
    cancelled_invoices = int(
        db.scalar(
            select(func.count())
            .select_from(Invoice)
            .where(
                Invoice.tenant_id == tenant_id,
                Invoice.customer_id == customer.id,
                Invoice.status == InvoiceStatus.CANCELLED,
            )
        )
        or 0
    )

    # ---- habits: top products and categories by quantity and value (per currency), grade timeline
    revision_ids = [revision.id for _, revision in invoices]
    product_qty: dict[tuple[str, str, str | None], Decimal] = defaultdict(Decimal)
    product_val: dict[tuple[str, str, str | None], Decimal] = defaultdict(Decimal)
    category_qty: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    category_val: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    grade_points: list[GradePoint] = []
    if revision_ids:
        rows = db.execute(
            select(
                InvoiceRevisionItem,
                InvoiceRevision.currency,
                Invoice.confirmed_at,
                TenantProduct.category_id,
            )
            .join(InvoiceRevision, InvoiceRevision.id == InvoiceRevisionItem.invoice_revision_id)
            .join(Invoice, Invoice.current_revision_id == InvoiceRevision.id)
            .outerjoin(TenantProduct, TenantProduct.id == InvoiceRevisionItem.tenant_product_id)
            .where(InvoiceRevisionItem.invoice_revision_id.in_(revision_ids))
            .order_by(Invoice.confirmed_at.asc(), InvoiceRevisionItem.line_number.asc())
        ).all()
        category_names = {
            row.id: row.name_en
            for row in db.scalars(select(Category).where(Category.tenant_id == tenant_id))
        }
        seen_grade: str | None = "__unset__"
        for item, currency, confirmed_at, category_id in rows:
            key = (
                currency,
                item.product_name,
                str(item.tenant_product_id) if item.tenant_product_id else None,
            )
            product_qty[key] += Decimal(item.quantity)
            product_val[key] += Decimal(item.line_total)
            if category_id is not None:
                ckey = (currency, category_names.get(category_id, "?"))
                category_qty[ckey] += Decimal(item.quantity)
                category_val[ckey] += Decimal(item.line_total)
            grade = item.customer_grade.value if item.customer_grade else None
            if grade != seen_grade and confirmed_at is not None:
                grade_points.append(GradePoint(at=confirmed_at, grade=grade))
                seen_grade = grade
    top_products = sorted(
        (
            TopItem(
                currency=c,
                name=n,
                product_id=UUID(pid) if pid else None,
                quantity=money(q),
                value=money(product_val[(c, n, pid)]),
            )
            for (c, n, pid), q in product_qty.items()
        ),
        key=lambda row: (row.currency, -row.value, -row.quantity, row.name),
    )
    top_categories = sorted(
        (
            TopItem(
                currency=c,
                name=n,
                product_id=None,
                quantity=money(q),
                value=money(category_val[(c, n)]),
            )
            for (c, n), q in category_qty.items()
        ),
        key=lambda row: (row.currency, -row.value, -row.quantity, row.name),
    )

    def _top5(rows: list[TopItem]) -> list[TopItem]:
        kept: list[TopItem] = []
        per_currency: dict[str, int] = defaultdict(int)
        for row in rows:
            if per_currency[row.currency] < 5:
                kept.append(row)
                per_currency[row.currency] += 1
        return kept

    return CustomerLifetimeResponse(
        customer_id=customer.id,
        customer_name=customer.name,
        current_grade=customer.grade.value if customer.grade else None,
        as_of=datetime.now(UTC),
        financial=financial,
        invoice_count=len(invoices),
        cancelled_invoices=cancelled_invoices,
        cancellation_requests=cancellation_requests,
        first_purchase_at=first_purchase,
        latest_purchase_at=latest_purchase,
        average_days_between_purchases=average_days,
        purchases_per_month=purchases_per_month,
        late_payment_count=late_count,
        overdue_threshold_days=threshold,
        monthly_spend=[
            MonthlySpend(currency=c, month=m, amount=money(v))
            for (c, m), v in sorted(monthly.items())
        ],
        top_products=_top5(top_products),
        top_categories=_top5(top_categories),
        grade_timeline=grade_points,
        insufficient_data=len(invoices) == 0,
    )
