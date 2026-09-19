from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from tawzeevo_api.database import get_db
from tawzeevo_api.dependencies import TenantContext, get_tenant_context, require_tenant_owner
from tawzeevo_api.schemas.procurement import (
    AssigneeListResponse,
    AssigneeRequest,
    CarryForwardRequest,
    GenerateListRequest,
    ItemRemoveRequest,
    ItemUpdateRequest,
    ItemWaiveRequest,
    ListCancelRequest,
    ManualItemRequest,
    PickupResponse,
    ProcurementListPage,
    ProcurementListResponse,
)
from tawzeevo_api.services import procurement

procurement_router = APIRouter(prefix="/api/v1/procurement", tags=["procurement"])

Owner = Annotated[TenantContext, Depends(require_tenant_owner)]
Member = Annotated[TenantContext, Depends(get_tenant_context)]
Db = Annotated[Session, Depends(get_db)]


def _view(db: Session, context: TenantContext, list_id: UUID) -> ProcurementListResponse:
    row = procurement.get_list(db, context.tenant.id, list_id)
    return procurement.list_response(db, context.tenant.id, row, context.membership.id)


@procurement_router.get("/assignees", response_model=AssigneeListResponse)
def get_assignees(db: Db, context: Owner) -> AssigneeListResponse:
    return AssigneeListResponse(
        assignees=procurement.list_assignees(db, context.tenant.id, context.membership.id)
    )


@procurement_router.get("/my-pickups", response_model=PickupResponse)
def get_my_pickups(db: Db, context: Member) -> PickupResponse:
    """Runner projection for any active member (owner or driver): no prices, ever."""
    return procurement.my_pickups(db, context.tenant.id, context.membership.id)


@procurement_router.get("/lists", response_model=ProcurementListPage)
def get_lists(
    db: Db,
    context: Owner,
    status_filter: Annotated[str | None, Query(alias="status", max_length=24)] = None,
) -> ProcurementListPage:
    rows = procurement.list_lists(db, context.tenant.id, status_filter)
    return ProcurementListPage(
        lists=procurement.summaries(db, context.tenant.id, rows, context.membership.id)
    )


@procurement_router.post(
    "/lists", response_model=ProcurementListResponse, status_code=status.HTTP_201_CREATED
)
def post_list(request: GenerateListRequest, db: Db, context: Owner) -> ProcurementListResponse:
    row = procurement.generate_list(db, context.tenant.id, context.membership.user_id, request)
    return procurement.list_response(db, context.tenant.id, row, context.membership.id)


@procurement_router.get("/lists/{list_id}", response_model=ProcurementListResponse)
def get_list(list_id: UUID, db: Db, context: Owner) -> ProcurementListResponse:
    return _view(db, context, list_id)


@procurement_router.get("/lists/{list_id}/export.csv")
def export_list(list_id: UUID, db: Db, context: Owner) -> Response:
    row = procurement.get_list(db, context.tenant.id, list_id)
    body = procurement.export_csv(db, context.tenant.id, row, context.membership.id)
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="procurement-{list_id}.csv"'},
    )


@procurement_router.post("/lists/{list_id}/items", response_model=ProcurementListResponse)
def post_item(
    list_id: UUID, request: ManualItemRequest, db: Db, context: Owner
) -> ProcurementListResponse:
    procurement.add_manual_item(db, context.tenant.id, context.membership.user_id, list_id, request)
    return _view(db, context, list_id)


@procurement_router.patch(
    "/lists/{list_id}/items/{item_id}", response_model=ProcurementListResponse
)
def patch_item(
    list_id: UUID, item_id: UUID, request: ItemUpdateRequest, db: Db, context: Owner
) -> ProcurementListResponse:
    procurement.update_item(
        db, context.tenant.id, context.membership.user_id, list_id, item_id, request
    )
    return _view(db, context, list_id)


@procurement_router.post(
    "/lists/{list_id}/items/{item_id}/remove", response_model=ProcurementListResponse
)
def remove_item(
    list_id: UUID, item_id: UUID, request: ItemRemoveRequest, db: Db, context: Owner
) -> ProcurementListResponse:
    procurement.remove_item(
        db, context.tenant.id, context.membership.user_id, list_id, item_id, request.reason
    )
    return _view(db, context, list_id)


@procurement_router.post(
    "/lists/{list_id}/items/{item_id}/waive", response_model=ProcurementListResponse
)
def waive_item(
    list_id: UUID, item_id: UUID, request: ItemWaiveRequest, db: Db, context: Owner
) -> ProcurementListResponse:
    procurement.waive_item(
        db, context.tenant.id, context.membership.user_id, list_id, item_id, request.reason
    )
    return _view(db, context, list_id)


@procurement_router.put("/lists/{list_id}/assignee", response_model=ProcurementListResponse)
def put_assignee(
    list_id: UUID, request: AssigneeRequest, db: Db, context: Owner
) -> ProcurementListResponse:
    procurement.set_assignee(
        db, context.tenant.id, context.membership.user_id, list_id, request.membership_id
    )
    return _view(db, context, list_id)


@procurement_router.post("/lists/{list_id}/complete", response_model=ProcurementListResponse)
def complete_list(list_id: UUID, db: Db, context: Owner) -> ProcurementListResponse:
    procurement.complete_list(db, context.tenant.id, context.membership.user_id, list_id)
    return _view(db, context, list_id)


@procurement_router.post("/lists/{list_id}/cancel", response_model=ProcurementListResponse)
def cancel_list(
    list_id: UUID, request: ListCancelRequest, db: Db, context: Owner
) -> ProcurementListResponse:
    procurement.cancel_list(
        db, context.tenant.id, context.membership.user_id, list_id, request.reason
    )
    return _view(db, context, list_id)


@procurement_router.post(
    "/lists/{list_id}/carry-forward",
    response_model=ProcurementListResponse,
    status_code=status.HTTP_201_CREATED,
)
def carry_forward(
    list_id: UUID, request: CarryForwardRequest, db: Db, context: Owner
) -> ProcurementListResponse:
    target = procurement.carry_forward(
        db, context.tenant.id, context.membership.user_id, list_id, request
    )
    return procurement.list_response(db, context.tenant.id, target, context.membership.id)
