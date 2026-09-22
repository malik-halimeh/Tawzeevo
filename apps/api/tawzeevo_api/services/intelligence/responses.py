"""Build the API shapes from the deterministic engines (shared by the routes and Copilot tools)."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from tawzeevo_api.schemas import intelligence as schema
from tawzeevo_api.schemas.analytics import PeriodInfo
from tawzeevo_api.services.analytics import TENANT_TZ
from tawzeevo_api.services.intelligence import anomalies, cashflow, customers


def _currency_ok(currency: str, wanted: str | None) -> bool:
    return wanted is None or currency == wanted


def priorities(
    db: Session,
    tenant_id: UUID,
    *,
    currency: str | None = None,
    limit: int = 50,
    as_of: datetime | None = None,
) -> schema.PrioritiesResponse:
    as_of, groups = customers.daily_priorities(db, tenant_id, as_of=as_of)
    return schema.PrioritiesResponse(
        as_of=as_of,
        groups=[
            schema.PriorityGroup(
                currency=code,
                items=[
                    schema.PriorityItem(
                        customer_id=p.features.customer_id,
                        customer_name=p.features.customer_name,
                        customer_grade=p.features.customer_grade,
                        currency=code,
                        score=p.score,
                        band=p.band,
                        components=schema.PriorityComponents(**p.components),
                        reasons=[
                            schema.Reason(code=r.code, value=r.value, context=dict(r.context or {}))
                            for r in p.reasons
                        ],
                        suggested_action_code=p.suggested_action_code,
                        inactivity_status=p.inactivity_status,
                        outstanding_balance=p.features.outstanding_balance,
                        days_since_last_purchase=p.features.days_since_last_purchase,
                    )
                    for p in rows[:limit]
                ],
            )
            for code, rows in groups.items()
            if _currency_ok(code, currency)
        ],
    )


def inactivity(
    db: Session,
    tenant_id: UUID,
    *,
    currency: str | None = None,
    statuses: Iterable[str] | None = None,
    limit: int = 100,
    as_of: datetime | None = None,
) -> schema.InactivityResponse:
    as_of, groups = customers.inactivity_risk(db, tenant_id, as_of=as_of)
    wanted = set(statuses) if statuses else None
    out: list[schema.InactivityGroup] = []
    for code, rows in groups.items():
        if not _currency_ok(code, currency):
            continue
        kept = [r for r in rows if wanted is None or r.status in wanted][:limit]
        out.append(
            schema.InactivityGroup(
                currency=code,
                items=[
                    schema.InactivityItem(
                        customer_id=r.features.customer_id,
                        customer_name=r.features.customer_name,
                        customer_grade=r.features.customer_grade,
                        currency=code,
                        status=r.status,
                        recency_ratio=r.features.recency_ratio,
                        days_since_last_purchase=r.features.days_since_last_purchase,
                        median_purchase_interval_days=r.features.median_purchase_interval_days,
                        purchase_interval_mad_days=r.features.purchase_interval_mad_days,
                        invoice_count_lifetime=r.features.invoice_count_lifetime,
                        invoice_count_90d=r.features.invoice_count_90d,
                        sales_30d=r.features.sales_30d,
                        sales_90d=r.features.sales_90d,
                        outstanding_balance=r.features.outstanding_balance,
                        last_purchase_at=r.features.last_purchase_at,
                        reason_codes=r.reason_codes,
                    )
                    for r in kept
                ],
            )
        )
    return schema.InactivityResponse(as_of=as_of, groups=out)


def anomaly_report(
    db: Session,
    tenant_id: UUID,
    *,
    currency: str | None = None,
    types: Iterable[str] | None = None,
    as_of: datetime | None = None,
) -> schema.AnomaliesResponse:
    report = anomalies.detect_anomalies(db, tenant_id, as_of=as_of, types=types)
    codes = sorted(set(report.anomalies) | set(report.insufficient_history))
    return schema.AnomaliesResponse(
        as_of=report.as_of,
        window=schema.AnomalyWindow(
            start=report.window.start,
            end=report.window.end,
            timezone=str(TENANT_TZ),
            block_days=anomalies.BLOCK_DAYS,
            baseline_blocks=anomalies.BASELINE_BLOCKS,
        ),
        groups=[
            schema.AnomalyGroup(
                currency=code,
                items=[
                    schema.AnomalyItem(
                        type=a.type,
                        severity=a.severity,
                        detected_at=report.as_of,
                        subject_type=a.subject_type,
                        subject_id=a.subject_id,
                        metric=a.metric,
                        observed_value=a.observed_value,
                        baseline=schema.AnomalyBaseline(
                            method=a.baseline.method,
                            median=a.baseline.median,
                            mad=a.baseline.mad,
                            sample_size=a.baseline.sample_size,
                        ),
                        reason_code=a.reason_code,
                        details=dict(a.details),
                    )
                    for a in report.anomalies.get(code, [])
                ],
                insufficient_history=report.insufficient_history.get(code, []),
            )
            for code in codes
            if _currency_ok(code, currency)
        ],
    )


def cash_flow(
    db: Session,
    tenant_id: UUID,
    *,
    period: str = "90d",
    planned_days: int = cashflow.DEFAULT_PLANNED_DAYS,
    currency: str | None = None,
    as_of: datetime | None = None,
) -> schema.CashFlowResponse:
    report = cashflow.cash_flow(db, tenant_id, period, planned_days=planned_days, as_of=as_of)
    return schema.CashFlowResponse(
        as_of=report.as_of,
        period=PeriodInfo(
            key=report.period.key,
            start=report.period.start,
            end=report.period.end,
            timezone=str(TENANT_TZ),
        ),
        overdue_threshold_days=report.overdue_threshold_days,
        currencies=[
            schema.CurrencyCashFlow(
                currency=row.currency,
                position=schema.CashPosition(
                    customer_receivables=row.customer_receivables,
                    customer_credit=row.customer_credit,
                    overdue_receivables=row.overdue_receivables,
                    overdue_customer_count=row.overdue_customer_count,
                    supplier_payables=row.supplier_payables,
                    supplier_credit=row.supplier_credit,
                ),
                ageing=[
                    schema.AgeingBucket(
                        bucket=b.bucket, amount=b.amount, customer_count=b.customer_count
                    )
                    for b in row.ageing
                ],
                historical_flow=schema.HistoricalFlow(
                    customer_receipts=row.customer_receipts,
                    customer_refunds=row.customer_refunds,
                    supplier_payments=row.supplier_payments,
                    net_customer_collections=row.net_customer_collections,
                    average_weekly_collections=row.average_weekly_collections,
                ),
                planned_collections=schema.PlannedCollections(
                    amount=row.planned_collections.amount,
                    task_count=row.planned_collections.task_count,
                    from_date=row.planned_collections.from_date,
                    through_date=row.planned_collections.through_date,
                    source=row.planned_collections.source,
                    projection_warning_code=row.planned_collections.projection_warning_code,
                ),
            )
            for row in report.currencies
            if _currency_ok(row.currency, currency)
        ],
    )
