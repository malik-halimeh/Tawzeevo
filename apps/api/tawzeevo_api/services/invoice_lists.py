"""Bounded read-only invoice projections. Financial filtering precedes paging in SQL."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Date, and_, case, cast, func, literal, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.selectable import CTE

from tawzeevo_api.models import (
    AllocationKind,
    Customer,
    CustomerLedgerEntry,
    Invoice,
    InvoiceRevision,
    InvoiceStatus,
    PaymentAllocation,
)
from tawzeevo_api.schemas.invoice_lists import (
    BusinessInvoiceListQuery,
    BusinessInvoiceListResponse,
    BusinessInvoiceListRow,
    InvoiceCurrencySummary,
    InvoiceListFilters,
    InvoiceSummaryResponse,
)
from tawzeevo_api.services.customer_ledger import (
    OVERDUE_CALENDAR,
    get_financial_settings,
    overdue_calendar_date,
)
from tawzeevo_api.services.customer_lists import _pages
from tawzeevo_api.services.invoice_editor import money
from tawzeevo_api.services.text_search import (
    normalize_search_text,
    normalized_search_expression,
)


def _filtered_invoices(
    tenant_id: UUID,
    filters: InvoiceListFilters,
    threshold: int | None,
    now: datetime,
) -> CTE:
    # SQL equivalent of customer_ledger._allocation_totals: aggregate BEFORE joining ledger
    # entries so multiple APPLY/REVERSAL rows never multiply an invoice's signed amount.
    allocations = (
        select(
            PaymentAllocation.target_ledger_entry_id.label("entry_id"),
            func.sum(
                case(
                    (PaymentAllocation.kind == AllocationKind.APPLY, PaymentAllocation.amount),
                    else_=-PaymentAllocation.amount,
                )
            ).label("allocated"),
        )
        .where(PaymentAllocation.tenant_id == tenant_id)
        .group_by(PaymentAllocation.target_ledger_entry_id)
        .cte("invoice_allocations")
    )
    # Exactly the per-invoice grouping in customer_debts, including revision deltas.
    obligations = (
        select(
            CustomerLedgerEntry.source_id.label("invoice_id"),
            func.sum(CustomerLedgerEntry.signed_amount).label("ledger_amount"),
            func.sum(func.coalesce(allocations.c.allocated, 0)).label("allocated"),
            func.min(CustomerLedgerEntry.effective_at).label("oldest"),
        )
        .outerjoin(allocations, allocations.c.entry_id == CustomerLedgerEntry.id)
        .where(
            CustomerLedgerEntry.tenant_id == tenant_id,
            CustomerLedgerEntry.source_type == "INVOICE",
            CustomerLedgerEntry.source_id.is_not(None),
        )
        .group_by(CustomerLedgerEntry.source_id)
        .cte("invoice_obligations")
    )
    confirmed = Invoice.status == InvoiceStatus.CONFIRMED
    outstanding = case(
        (confirmed, func.coalesce(obligations.c.ledger_amount - obligations.c.allocated, 0)),
        else_=0,
    )
    # D-040: both dates use the canonical calendar, independent of DB/server session zones.
    age = case(
        (
            and_(confirmed, obligations.c.oldest.is_not(None)),
            func.greatest(
                0,
                overdue_calendar_date(now)
                - cast(func.timezone(OVERDUE_CALENDAR.key, obligations.c.oldest), Date),
            ),
        ),
        else_=None,
    )
    paid_state = case(
        (~confirmed, None),
        (outstanding <= 0, "PAID"),
        (outstanding == obligations.c.ledger_amount, "UNPAID"),
        else_="PARTLY_PAID",
    )
    is_overdue = (
        func.coalesce(and_(outstanding > 0, age > threshold), False)
        if threshold is not None
        else literal(False)
    )
    invoice_date = func.coalesce(Invoice.confirmed_at, Invoice.created_at)
    conditions = [Invoice.tenant_id == tenant_id]
    if filters.status is not None:
        conditions.append(Invoice.status == filters.status)
    if filters.customer_id is not None:
        conditions.append(Invoice.customer_id == filters.customer_id)
    if filters.currency is not None:
        conditions.append(InvoiceRevision.currency == filters.currency)
    calendar_date = cast(func.timezone(OVERDUE_CALENDAR.key, invoice_date), Date)
    if filters.date_from is not None:
        conditions.append(calendar_date >= filters.date_from)
    if filters.date_to is not None:
        conditions.append(calendar_date <= filters.date_to)
    if filters.q is not None:
        query = normalize_search_text(filters.q)
        conditions.append(
            or_(
                normalized_search_expression(Invoice.official_invoice_number).contains(
                    query, autoescape=True
                ),
                normalized_search_expression(Customer.name).contains(query, autoescape=True),
            )
        )
    rows = (
        select(
            Invoice.id,
            Invoice.status,
            Invoice.official_invoice_number,
            Invoice.confirmed_at,
            Invoice.created_at,
            InvoiceRevision.currency,
            InvoiceRevision.net_sales,
            InvoiceRevision.amount_due_display.label("total_due"),
            InvoiceRevision.server_revision_number,
            Invoice.customer_id,
            Customer.name.label("customer_name"),
            outstanding.label("outstanding"),
            paid_state.label("paid_state"),
            age.label("overdue_age_days"),
            case((is_overdue, True), else_=False).label("is_overdue"),
            invoice_date.label("invoice_date"),
        )
        .join(
            InvoiceRevision,
            (InvoiceRevision.id == Invoice.current_revision_id)
            & (InvoiceRevision.tenant_id == Invoice.tenant_id),
        )
        .outerjoin(
            Customer,
            (Customer.id == Invoice.customer_id) & (Customer.tenant_id == Invoice.tenant_id),
        )
        .outerjoin(obligations, obligations.c.invoice_id == Invoice.id)
        .where(*conditions)
        .cte("invoice_positions")
    )
    financial_conditions = []
    if filters.paid_state == "OPEN":
        financial_conditions.append(rows.c.outstanding > 0)
    elif filters.paid_state is not None:
        financial_conditions.append(rows.c.paid_state == filters.paid_state)
    if filters.overdue is not None:
        financial_conditions.append(rows.c.is_overdue == filters.overdue)
    return select(rows).where(*financial_conditions).cte("filtered_invoices")


def list_business_invoices(
    db: Session, tenant_id: UUID, query: BusinessInvoiceListQuery
) -> BusinessInvoiceListResponse:
    threshold = get_financial_settings(db, tenant_id).customer_overdue_threshold_days
    rows = _filtered_invoices(tenant_id, query, threshold, datetime.now(UTC))
    total = int(db.scalar(select(func.count()).select_from(rows)) or 0)
    page_rows = db.execute(
        select(rows)
        .order_by(rows.c.invoice_date.desc(), rows.c.id.desc())
        .offset((query.page - 1) * query.limit)
        .limit(query.limit)
    ).mappings()
    return BusinessInvoiceListResponse(
        page=query.page,
        limit=query.limit,
        total=total,
        total_pages=_pages(total, query.limit),
        invoices=[
            BusinessInvoiceListRow.model_validate({**row, "outstanding": money(row["outstanding"])})
            for row in page_rows
        ],
    )


def summarize_business_invoices(
    db: Session, tenant_id: UUID, filters: InvoiceListFilters
) -> InvoiceSummaryResponse:
    threshold = get_financial_settings(db, tenant_id).customer_overdue_threshold_days
    rows = _filtered_invoices(tenant_id, filters, threshold, datetime.now(UTC))
    summaries = db.execute(
        select(
            rows.c.currency,
            func.sum(rows.c.outstanding).label("outstanding_total"),
            func.coalesce(func.sum(rows.c.outstanding).filter(rows.c.is_overdue), 0).label(
                "overdue_total"
            ),
            func.count().filter(rows.c.outstanding > 0).label("open_count"),
            func.count().filter(rows.c.is_overdue).label("overdue_count"),
            func.count().filter(rows.c.paid_state == "PAID").label("paid_count"),
            func.count().filter(rows.c.status == InvoiceStatus.DRAFT).label("draft_count"),
        )
        .group_by(rows.c.currency)
        .order_by(rows.c.currency)
    ).mappings()
    return InvoiceSummaryResponse(
        currencies=[
            InvoiceCurrencySummary.model_validate(
                {
                    **row,
                    "outstanding_total": money(row["outstanding_total"]),
                    "overdue_total": money(row["overdue_total"]),
                }
            )
            for row in summaries
        ]
    )
