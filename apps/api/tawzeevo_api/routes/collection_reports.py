from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from tawzeevo_api.database import get_db
from tawzeevo_api.dependencies import TenantContext, require_tenant_owner
from tawzeevo_api.schemas.collection_reports import (
    CollectionRejectRequest,
    CollectionReportListResponse,
    CollectionReportResponse,
    CustomerNotificationListResponse,
)
from tawzeevo_api.services import collection_reports, customer_access

collection_reports_router = APIRouter(prefix="/api/v1/collection-reports", tags=["delivery"])
customer_notifications_router = APIRouter(prefix="/api/v1/public", tags=["storefront"])

Owner = Annotated[TenantContext, Depends(require_tenant_owner)]
Db = Annotated[Session, Depends(get_db)]
PRIVATE_CACHE = "private, no-store"
CAPABILITY_HEADER = "X-Customer-Capability"
SESSION_HEADER = customer_access.SESSION_HEADER


@collection_reports_router.get("", response_model=CollectionReportListResponse)
def get_reports(
    db: Db, context: Owner, status: Literal["PENDING", "CONFIRMED", "REJECTED"] | None = None
) -> CollectionReportListResponse:
    """What drivers reported collecting (D-114); PENDING ones wait for the owner."""
    rows = collection_reports.list_reports(db, context.tenant.id, status)
    return CollectionReportListResponse(
        reports=[collection_reports.report_response(db, row) for row in rows]
    )


@collection_reports_router.post("/{report_id}/confirm", response_model=CollectionReportResponse)
def confirm(report_id: UUID, db: Db, context: Owner) -> CollectionReportResponse:
    report = collection_reports.confirm_report(
        db, context.tenant.id, context.membership.user_id, report_id
    )
    return collection_reports.report_response(db, report)


@collection_reports_router.post("/{report_id}/reject", response_model=CollectionReportResponse)
def reject(
    report_id: UUID, request: CollectionRejectRequest, db: Db, context: Owner
) -> CollectionReportResponse:
    report = collection_reports.reject_report(
        db, context.tenant.id, context.membership.user_id, report_id, request.reason
    )
    return collection_reports.report_response(db, report)


def _customer(db: Session, capability: str | None, session: str | None) -> tuple[UUID, UUID]:
    context = customer_access.resolve_context(db, capability, session)
    if context is None:
        raise customer_access._unavailable()  # the same constant 404 as the context call
    return context.tenant_id, context.customer_id


@customer_notifications_router.get(
    "/notifications", response_model=CustomerNotificationListResponse
)
def read_notifications(
    response: Response,
    db: Db,
    capability: Annotated[str | None, Header(alias=CAPABILITY_HEADER)] = None,
    session: Annotated[str | None, Header(alias=SESSION_HEADER)] = None,
) -> CustomerNotificationListResponse:
    """The granted customer's own notifications only (D-114); anything else is a constant 404."""
    response.headers["Cache-Control"] = PRIVATE_CACHE
    tenant_id, customer_id = _customer(db, capability, session)
    return collection_reports.customer_notifications(db, tenant_id, customer_id)


@customer_notifications_router.post("/notifications/read", status_code=204)
def mark_read(
    db: Db,
    capability: Annotated[str | None, Header(alias=CAPABILITY_HEADER)] = None,
    session: Annotated[str | None, Header(alias=SESSION_HEADER)] = None,
) -> Response:
    tenant_id, customer_id = _customer(db, capability, session)
    collection_reports.mark_notifications_read(db, tenant_id, customer_id)
    return Response(status_code=204, headers={"Cache-Control": PRIVATE_CACHE})
