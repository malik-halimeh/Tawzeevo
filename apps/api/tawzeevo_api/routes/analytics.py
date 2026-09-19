from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from tawzeevo_api.database import get_db
from tawzeevo_api.dependencies import TenantContext, require_tenant_owner
from tawzeevo_api.schemas.analytics import EventFlowResponse, InvoiceAnalytics, OverviewResponse
from tawzeevo_api.schemas.customer_stats import CustomerLifetimeResponse
from tawzeevo_api.services import analytics
from tawzeevo_api.services.customer_stats import customer_lifetime

analytics_router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

Owner = Annotated[TenantContext, Depends(require_tenant_owner)]
Db = Annotated[Session, Depends(get_db)]
PeriodQuery = Annotated[str, Query(pattern=r"^(30d|90d|1y|all)$")]


@analytics_router.get("/overview", response_model=OverviewResponse)
def get_overview(db: Db, context: Owner, period: PeriodQuery = "30d") -> OverviewResponse:
    """Owner-only current-state figures by currency for the period (D-064–D-068)."""
    return analytics.overview(db, context.tenant.id, period)


@analytics_router.get("/events", response_model=EventFlowResponse)
def get_events(db: Db, context: Owner, period: PeriodQuery = "90d") -> EventFlowResponse:
    """Owner-only event flow: confirmations, edit deltas, cancellations by effect date."""
    return analytics.event_flow(db, context.tenant.id, period)


@analytics_router.get("/invoices/{invoice_id}", response_model=InvoiceAnalytics)
def get_invoice_analytics(invoice_id: UUID, db: Db, context: Owner) -> InvoiceAnalytics:
    return analytics.invoice_analytics(db, context.tenant.id, invoice_id)


@analytics_router.get("/customers/{customer_id}", response_model=CustomerLifetimeResponse)
def get_customer_lifetime(customer_id: UUID, db: Db, context: Owner) -> CustomerLifetimeResponse:
    """Owner-only lifetime statistics for one customer (D-069); duplicates never merged."""
    return customer_lifetime(db, context.tenant.id, customer_id)
