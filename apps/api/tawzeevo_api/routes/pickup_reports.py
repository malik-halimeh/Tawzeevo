from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Response, status
from sqlalchemy.orm import Session

from tawzeevo_api.database import get_db
from tawzeevo_api.dependencies import TenantContext, get_tenant_context, require_tenant_owner
from tawzeevo_api.schemas.pickup_reports import (
    PickupReportCreateRequest,
    PickupReportListResponse,
    PickupReportRejectRequest,
    PickupReportResponse,
)
from tawzeevo_api.services import pickup_reports, push

pickup_reports_router = APIRouter(prefix="/api/v1/procurement/pickup-reports", tags=["procurement"])

Owner = Annotated[TenantContext, Depends(require_tenant_owner)]
Member = Annotated[TenantContext, Depends(get_tenant_context)]
Db = Annotated[Session, Depends(get_db)]


@pickup_reports_router.post("", response_model=PickupReportResponse)
def post_report(
    request: PickupReportCreateRequest,
    response: Response,
    db: Db,
    context: Member,
    background: BackgroundTasks,
) -> PickupReportResponse:
    """The list's runner (or the owner) reports a pickup; nothing is purchased yet (D-106)."""
    report, replayed = pickup_reports.create_report(
        db, context.tenant.id, context.membership, request
    )
    response.status_code = status.HTTP_200_OK if replayed else status.HTTP_201_CREATED
    if not replayed:
        background.add_task(
            push.notify_owners,
            context.tenant.id,
            *push.PICKUP,
            push.workspace(context.tenant.id, "procurement"),
        )
    return pickup_reports.report_response(db, context.tenant.id, report)


@pickup_reports_router.get("", response_model=PickupReportListResponse)
def get_reports(
    db: Db, context: Owner, status: Literal["PENDING", "CONFIRMED", "REJECTED"] | None = None
) -> PickupReportListResponse:
    rows = pickup_reports.list_reports(db, context.tenant.id, status)
    return PickupReportListResponse(
        reports=[pickup_reports.report_response(db, context.tenant.id, row) for row in rows]
    )


@pickup_reports_router.post("/{report_id}/confirm", response_model=PickupReportResponse)
def confirm_report(report_id: UUID, db: Db, context: Owner) -> PickupReportResponse:
    report = pickup_reports.confirm_report(
        db, context.tenant.id, context.membership.user_id, report_id
    )
    return pickup_reports.report_response(db, context.tenant.id, report)


@pickup_reports_router.post("/{report_id}/reject", response_model=PickupReportResponse)
def reject_report(
    report_id: UUID, request: PickupReportRejectRequest, db: Db, context: Owner
) -> PickupReportResponse:
    report = pickup_reports.reject_report(
        db, context.tenant.id, context.membership.user_id, report_id, request.reason
    )
    return pickup_reports.report_response(db, context.tenant.id, report)
