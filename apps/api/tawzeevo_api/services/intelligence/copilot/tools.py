"""Typed, read-only Copilot tools over the deterministic services (D-089).

Every tool reads through an existing deterministic service with the request's tenant, which is
bound here and is never a model-visible parameter. No tool writes, accepts SQL, or returns phones,
addresses, locations, tokens or links. Customers appear only as opaque references
(`privacy.customer_ref`). Results are compact aggregates, not ledger dumps. Results are memoized
for the duration of one request only.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from tawzeevo_api.errors import AppError
from tawzeevo_api.services import analytics
from tawzeevo_api.services.customer_ledger import customer_debts
from tawzeevo_api.services.customer_stats import customer_lifetime
from tawzeevo_api.services.intelligence import products, responses
from tawzeevo_api.services.intelligence.copilot.privacy import CustomerDirectory

PeriodKey = Literal["30d", "90d", "1y", "all"]
Currency = Field(default=None, pattern=r"^[A-Z]{3}$", description="ISO currency code, e.g. USD")
InactivityStatus = Literal["NORMAL", "WATCH", "AT_RISK", "LAPSED", "INSUFFICIENT_HISTORY"]
AnomalyType = Literal[
    "SALES_PERIOD_HIGH",
    "SALES_PERIOD_LOW",
    "CANCELLATION_SPIKE",
    "REVERSAL_SPIKE",
    "REFUND_SPIKE",
    "CUSTOMER_INVOICE_VALUE_HIGH",
    "BACKDATED_RECEIPT_LARGE",
    "OVERDUE_THRESHOLD_CROSSED",
    "SUPPLIER_PAYABLE_JUMP",
    "LINE_PRICE_BELOW_SNAPSHOT_COST",
]
# Anomaly detail keys that may leave the server; everything else (names, ids) is dropped.
_ANOMALY_DETAIL_KEYS = {
    "robust_z",
    "invoice_count",
    "event_count",
    "days_recorded_after_payment_date",
    "recorded_from_device",
    "overdue_age_days",
    "threshold_days",
    "days_past_threshold",
    "line_number",
    "product_name",
    "unit_cost_snapshot",
}


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PeriodOverviewArgs(_Args):
    period_key: PeriodKey = "30d"
    currency: str | None = Currency


class CustomerLifetimeArgs(_Args):
    customer_ref: str = Field(pattern=r"^C-[A-Z2-7]{6}$", description="Opaque customer reference")


class CustomerDebtsArgs(_Args):
    currency: str | None = Currency
    overdue_only: bool = False
    limit: int = Field(default=10, ge=1, le=50)


class PrioritiesArgs(_Args):
    currency: str | None = Currency
    limit: int = Field(default=10, ge=1, le=50)


class InactivityArgs(_Args):
    currency: str | None = Currency
    statuses: list[InactivityStatus] | None = None
    limit: int = Field(default=10, ge=1, le=50)


class AnomaliesArgs(_Args):
    currency: str | None = Currency
    types: list[AnomalyType] | None = None


class CashFlowArgs(_Args):
    period_key: PeriodKey = "90d"
    planned_collection_days: int = Field(default=7, ge=1, le=31)


class TopProductsArgs(_Args):
    period_key: PeriodKey = "90d"
    currency: str | None = Currency
    limit: int = Field(default=5, ge=1, le=20)


class LookupProductArgs(_Args):
    query: str = Field(min_length=2, max_length=80)
    currency: str | None = Currency


@dataclass
class ToolContext:
    db: Session
    tenant_id: UUID  # from the server-side tenant context only
    as_of: datetime
    directory: CustomerDirectory
    memo: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(v) for v in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _period_overview(ctx: ToolContext, args: PeriodOverviewArgs) -> dict[str, Any]:
    overview = analytics.overview(ctx.db, ctx.tenant_id, args.period_key, ctx.as_of)
    fields = (
        "invoiced_sales",
        "customer_receipts",
        "customer_refunds",
        "customer_outstanding",
        "supplier_payable",
    )
    by_currency: dict[str, dict[str, Decimal]] = {}
    for name in fields:
        for row in getattr(overview, name):
            if args.currency is None or row.currency == args.currency:
                by_currency.setdefault(row.currency, {})[name] = row.amount
    return {
        "period": overview.period.model_dump(),
        "confirmed_invoices_all_currencies": overview.confirmed_invoices,
        "currencies": [{"currency": c, **v} for c, v in sorted(by_currency.items())],
        "note": "customer_outstanding and supplier_payable are current balances, not period flows",
    }


def _customer_lifetime(ctx: ToolContext, args: CustomerLifetimeArgs) -> dict[str, Any]:
    customer_id = ctx.directory.resolve(args.customer_ref)
    if customer_id is None:
        return {"error": "UNKNOWN_CUSTOMER_REF"}
    stats = customer_lifetime(ctx.db, ctx.tenant_id, customer_id)
    return {
        "customer_ref": args.customer_ref,
        "current_grade": stats.current_grade,
        "invoice_count": stats.invoice_count,
        "cancelled_invoices": stats.cancelled_invoices,
        "cancellation_requests": stats.cancellation_requests,
        "first_purchase_at": stats.first_purchase_at,
        "latest_purchase_at": stats.latest_purchase_at,
        "average_days_between_purchases": stats.average_days_between_purchases,
        "financial": [
            {
                "currency": f.currency,
                "total_purchased": f.total_purchased,
                "invoice_count": f.invoice_count,
                "average_invoice": f.average_invoice,
                "total_receipts": f.total_receipts,
                "total_refunds": f.total_refunds,
                "outstanding": f.outstanding,
                "credit": f.credit,
            }
            for f in stats.financial
        ],
        "top_products_meaning": "by line sales before invoice-level discounts/markups; not net "
        "sales, revenue or margin",
        "top_products": [
            {
                "currency": p.currency,
                "name": p.name,
                "quantity": p.quantity,
                "line_sales_before_invoice_adjustments": p.value,
            }
            for p in stats.top_products
        ],
    }


def _customer_debts(ctx: ToolContext, args: CustomerDebtsArgs) -> dict[str, Any]:
    rows = [
        d
        for d in customer_debts(ctx.db, ctx.tenant_id, now=ctx.as_of).debts
        if (args.currency is None or d.currency == args.currency)
        and (not args.overdue_only or d.is_overdue)
    ]
    return {
        "overdue_threshold_days": rows[0].overdue_threshold_days if rows else None,
        "matching_customers": len(rows),
        "debts": [
            {
                "customer_ref": ctx.directory.ref(d.customer_id),
                "currency": d.currency,
                "balance": d.balance,
                "oldest_unpaid_at": d.oldest_unpaid_at,
                "overdue_age_days": d.overdue_age_days,
                "is_overdue": d.is_overdue,
            }
            for d in rows[: args.limit]
        ],
    }


def _priorities(ctx: ToolContext, args: PrioritiesArgs) -> dict[str, Any]:
    body = responses.priorities(
        ctx.db, ctx.tenant_id, currency=args.currency, limit=args.limit, as_of=ctx.as_of
    )
    return {
        "as_of": body.as_of,
        "score_meaning": "workflow priority 0-100 from the listed components; not a probability",
        "groups": [
            {
                "currency": group.currency,
                "items": [
                    {
                        "customer_ref": ctx.directory.ref(item.customer_id),
                        "score": item.score,
                        "band": item.band,
                        "components": item.components.model_dump(),
                        "reasons": [r.model_dump() for r in item.reasons],
                        "suggested_action_code": item.suggested_action_code,
                        "outstanding_balance": item.outstanding_balance,
                        "days_since_last_purchase": item.days_since_last_purchase,
                    }
                    for item in group.items
                ],
            }
            for group in body.groups
        ],
    }


def _inactivity(ctx: ToolContext, args: InactivityArgs) -> dict[str, Any]:
    body = responses.inactivity(
        ctx.db,
        ctx.tenant_id,
        currency=args.currency,
        statuses=args.statuses,
        limit=args.limit,
        as_of=ctx.as_of,
    )
    return {
        "as_of": body.as_of,
        "status_meaning": "purchase-cadence band vs the customer's own median interval; "
        "not a churn probability",
        "groups": [
            {
                "currency": group.currency,
                "items": [
                    {
                        "customer_ref": ctx.directory.ref(item.customer_id),
                        **item.model_dump(
                            exclude={"customer_id", "customer_name", "customer_grade", "currency"}
                        ),
                    }
                    for item in group.items
                ],
            }
            for group in body.groups
        ],
    }


def _anomalies(ctx: ToolContext, args: AnomaliesArgs) -> dict[str, Any]:
    body = responses.anomaly_report(
        ctx.db, ctx.tenant_id, currency=args.currency, types=args.types, as_of=ctx.as_of
    )

    def subject_ref(item: Any) -> str | None:
        if item.subject_type == "CUSTOMER":
            return ctx.directory.ref(item.subject_id)
        raw = item.details.get("customer_id")
        return ctx.directory.ref(UUID(raw)) if isinstance(raw, str) else None

    return {
        "as_of": body.as_of,
        "window": body.window.model_dump(),
        "meaning": "values unusual against the business's own history; never an accusation",
        "groups": [
            {
                "currency": group.currency,
                "insufficient_history": group.insufficient_history,
                "items": [
                    {
                        "type": item.type,
                        "severity": item.severity,
                        "subject_type": item.subject_type,
                        "customer_ref": subject_ref(item),
                        "metric": item.metric,
                        "observed_value": item.observed_value,
                        "baseline": item.baseline.model_dump(),
                        "reason_code": item.reason_code,
                        "details": {
                            k: v for k, v in item.details.items() if k in _ANOMALY_DETAIL_KEYS
                        },
                    }
                    for item in group.items
                ],
            }
            for group in body.groups
        ],
    }


def _cash_flow(ctx: ToolContext, args: CashFlowArgs) -> dict[str, Any]:
    body = responses.cash_flow(
        ctx.db,
        ctx.tenant_id,
        period=args.period_key,
        planned_days=args.planned_collection_days,
        as_of=ctx.as_of,
    )
    return {
        "meaning": "current position, ageing and past flows; planned_collections is a "
        "projection that ignores invoice adjustments; there is no forecast",
        **body.model_dump(),
    }


def _top_products(ctx: ToolContext, args: TopProductsArgs) -> dict[str, Any]:
    rows = products.top_products(
        ctx.db,
        ctx.tenant_id,
        args.period_key,
        currency=args.currency,
        limit=args.limit,
        as_of=ctx.as_of,
    )
    return {
        "period_key": args.period_key,
        "value_meaning": "line_sales_before_invoice_adjustments = sum of confirmed invoice line "
        "totals after line discounts/markups and before invoice-level discounts/markups; not net "
        "sales, revenue or margin; no stock or availability is known",
        "products": [row.__dict__ for row in rows],
    }


def _lookup_product(ctx: ToolContext, args: LookupProductArgs) -> dict[str, Any]:
    rows = products.lookup_products(ctx.db, ctx.tenant_id, args.query, currency=args.currency)
    return {
        "note": "catalog prices only; Tawzeevo keeps no stock or availability",
        "products": [row.__dict__ for row in rows],
    }


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args_model: type[_Args]
    handler: Callable[[ToolContext, Any], dict[str, Any]]

    def schema(self) -> dict[str, Any]:
        parameters = self.args_model.model_json_schema()
        parameters.pop("title", None)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": parameters,
            },
        }


TOOLS: dict[str, Tool] = {
    tool.name: tool
    for tool in (
        Tool(
            "get_period_overview",
            "Invoiced sales, customer receipts and refunds for a period ending today, plus "
            "current customer outstanding and supplier payable, per currency.",
            PeriodOverviewArgs,
            _period_overview,
        ),
        Tool(
            "get_customer_lifetime",
            "Lifetime purchase and payment statistics for one customer reference.",
            CustomerLifetimeArgs,
            _customer_lifetime,
        ),
        Tool(
            "get_customer_debts",
            "Customers with an outstanding balance: amount, oldest unpaid date, overdue age "
            "and overdue flag under the business's overdue threshold.",
            CustomerDebtsArgs,
            _customer_debts,
        ),
        Tool(
            "get_daily_priorities",
            "Customers ranked for attention today with score components, reason codes and a "
            "suggested action code, per currency.",
            PrioritiesArgs,
            _priorities,
        ),
        Tool(
            "get_inactivity_risk",
            "Purchase-cadence bands (NORMAL, WATCH, AT_RISK, LAPSED, INSUFFICIENT_HISTORY) "
            "per customer and currency.",
            InactivityArgs,
            _inactivity,
        ),
        Tool(
            "get_anomalies",
            "Unusual values in the last 7 days against the business's own history.",
            AnomaliesArgs,
            _anomalies,
        ),
        Tool(
            "get_cashflow_summary",
            "Receivables, overdue receivables, supplier payables, ageing, past receipts/refunds/"
            "supplier payments and planned delivery collections, per currency. No forecast.",
            CashFlowArgs,
            _cash_flow,
        ),
        Tool(
            "get_top_products",
            "Top products per currency by line sales before invoice-level discounts/markups "
            "(not net sales, revenue or margin) on confirmed invoices in a period.",
            TopProductsArgs,
            _top_products,
        ),
        Tool(
            "lookup_product",
            "Find catalog products by name and return their list price and currency.",
            LookupProductArgs,
            _lookup_product,
        ),
    )
}


def tool_schemas() -> list[dict[str, Any]]:
    return [tool.schema() for tool in TOOLS.values()]


def run_tool(
    ctx: ToolContext, name: str, raw_arguments: str | dict[str, Any] | None
) -> dict[str, Any]:
    """Validate and execute one model-requested call. Unknown tools and invalid arguments come
    back as structured errors for the model; they never raise into the request."""
    tool = TOOLS.get(name)
    if tool is None:
        return {"error": "UNKNOWN_TOOL"}
    try:
        payload = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
        args = tool.args_model.model_validate(payload or {})
    except (ValueError, ValidationError):
        return {"error": "INVALID_ARGUMENTS"}
    key = (name, args.model_dump_json())
    if key not in ctx.memo:
        try:
            ctx.memo[key] = _json_safe(tool.handler(ctx, args))
        except AppError as exc:
            ctx.memo[key] = {"error": exc.code}
    return ctx.memo[key]
