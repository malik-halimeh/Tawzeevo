from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from tawzeevo_api.database import get_db
from tawzeevo_api.dependencies import TenantContext, require_tenant_owner
from tawzeevo_api.schemas.intelligence import (
    AnomaliesResponse,
    CashFlowResponse,
    CopilotGrounding,
    CopilotQueryRequest,
    CopilotReference,
    CopilotResponse,
    CopilotStatus,
    InactivityResponse,
    PrioritiesResponse,
)
from tawzeevo_api.services.intelligence import responses
from tawzeevo_api.services.intelligence.copilot import service as copilot

intelligence_router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])

Owner = Annotated[TenantContext, Depends(require_tenant_owner)]
Db = Annotated[Session, Depends(get_db)]
CurrencyQuery = Annotated[str | None, Query(pattern=r"^[A-Z]{3}$")]
PeriodQuery = Annotated[str, Query(pattern=r"^(30d|90d|1y|all)$")]
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


@intelligence_router.get("/priorities", response_model=PrioritiesResponse)
def get_priorities(
    db: Db,
    context: Owner,
    currency: CurrencyQuery = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> PrioritiesResponse:
    """Owner-only daily customer priorities, ranked separately per currency (D-089)."""
    return responses.priorities(db, context.tenant.id, currency=currency, limit=limit)


@intelligence_router.get("/inactivity", response_model=InactivityResponse)
def get_inactivity(
    db: Db,
    context: Owner,
    currency: CurrencyQuery = None,
    status: Annotated[list[InactivityStatus] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> InactivityResponse:
    """Owner-only purchase-cadence bands per customer and currency; never a probability."""
    return responses.inactivity(
        db, context.tenant.id, currency=currency, statuses=status, limit=limit
    )


@intelligence_router.get("/anomalies", response_model=AnomaliesResponse)
def get_anomalies(
    db: Db,
    context: Owner,
    currency: CurrencyQuery = None,
    type: Annotated[list[AnomalyType] | None, Query()] = None,  # noqa: A002 - public query name
) -> AnomaliesResponse:
    """Owner-only unusual values against the tenant's own history (last 7 tenant days)."""
    return responses.anomaly_report(db, context.tenant.id, currency=currency, types=type)


@intelligence_router.get("/cash-flow", response_model=CashFlowResponse)
def get_cash_flow(
    db: Db,
    context: Owner,
    period: PeriodQuery = "90d",
    planned_days: Annotated[int, Query(ge=1, le=31)] = 7,
    currency: CurrencyQuery = None,
) -> CashFlowResponse:
    """Owner-only position, ageing and history per currency; planned collections are a
    labelled projection. No forecast."""
    return responses.cash_flow(
        db,
        context.tenant.id,
        period=period,
        planned_days=planned_days,
        currency=currency,
    )


@intelligence_router.get("/copilot/status", response_model=CopilotStatus)
def get_copilot_status(context: Owner) -> CopilotStatus:
    """Whether the business assistant is configured; never reveals the key."""
    return CopilotStatus(**copilot.status())


@intelligence_router.post("/copilot/query", response_model=CopilotResponse)
def post_copilot_query(request: CopilotQueryRequest, db: Db, context: Owner) -> CopilotResponse:
    """Owner-only, read-only natural-language answer grounded in the deterministic tools. The
    tenant comes from the server-side context; nothing is stored (D-089)."""
    result = copilot.ask(
        db,
        context.tenant.id,
        context.membership.user_id,
        request.message,
        [turn.model_dump() for turn in request.conversation],
        conversation_id=request.conversation_id,
    )
    return CopilotResponse(
        conversation_id=result.conversation_id,
        answer=result.answer,
        conversation_text=result.conversation_text,
        references=[CopilotReference(**row) for row in result.references],
        grounding=[CopilotGrounding(**row) for row in result.grounding],
        warnings=result.warnings,
        unverified_numbers=result.unverified_numbers,
    )
