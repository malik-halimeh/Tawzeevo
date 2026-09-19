from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from tawzeevo_api.database import get_db
from tawzeevo_api.dependencies import TenantContext, get_tenant_context, require_tenant_owner
from tawzeevo_api.models import TenantRole
from tawzeevo_api.schemas.delivery import (
    EligibleInvoiceListResponse,
    LocationUpdateRequest,
    LocationUpdateResponse,
    MyWorkResponse,
    MyWorkTask,
    NearbyResponse,
    SaveOrderRequest,
    SuggestOrderRequest,
    SuggestOrderResponse,
    TaskAssignRequest,
    TaskCancelRequest,
    TaskCompleteRequest,
    TaskCreateRequest,
    TaskListResponse,
    TaskResponse,
    TaskUpdateRequest,
)
from tawzeevo_api.services import delivery

delivery_router = APIRouter(prefix="/api/v1/delivery-tasks", tags=["delivery"])
routes_router = APIRouter(prefix="/api/v1/routes", tags=["delivery"])

Owner = Annotated[TenantContext, Depends(require_tenant_owner)]
Member = Annotated[TenantContext, Depends(get_tenant_context)]
Db = Annotated[Session, Depends(get_db)]


@delivery_router.get("", response_model=TaskListResponse)
def get_tasks(
    db: Db,
    context: Owner,
    status_filter: Annotated[str | None, Query(alias="status", max_length=12)] = None,
    delivery_date: Annotated[date | None, Query()] = None,
) -> TaskListResponse:
    rows = delivery.list_tasks(
        db, context.tenant.id, status=status_filter, delivery_date=delivery_date
    )
    return delivery.list_response(db, context.tenant.id, rows, context.membership.id)


@delivery_router.get("/my-work", response_model=MyWorkResponse)
def get_my_work(db: Db, context: Member) -> MyWorkResponse:
    """Assigned-only projection for drivers and for the owner as operator (PHASE_07.md D/J)."""
    return delivery.my_work(db, context.tenant.id, context.membership)


@delivery_router.get("/eligible-invoices", response_model=EligibleInvoiceListResponse)
def get_eligible_invoices(db: Db, context: Owner) -> EligibleInvoiceListResponse:
    return EligibleInvoiceListResponse(invoices=delivery.eligible_invoices(db, context.tenant.id))


@delivery_router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def post_task(request: TaskCreateRequest, db: Db, context: Owner) -> TaskResponse:
    task = delivery.create_task(db, context.tenant.id, context.membership.user_id, request)
    return delivery.task_response(db, context.tenant.id, task, context.membership.id)


@delivery_router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: UUID, db: Db, context: Owner) -> TaskResponse:
    task = delivery.get_task(db, context.tenant.id, task_id)
    return delivery.task_response(db, context.tenant.id, task, context.membership.id)


@delivery_router.put("/{task_id}/assignee", response_model=TaskResponse)
def put_assignee(task_id: UUID, request: TaskAssignRequest, db: Db, context: Owner) -> TaskResponse:
    """Owner only (PHASE_07.md A rule 7): drivers never assign or reassign."""
    task = delivery.assign_task(
        db,
        context.tenant.id,
        context.membership.user_id,
        task_id,
        request.assigned_membership_id,
        request.expected_version,
    )
    return delivery.task_response(db, context.tenant.id, task, context.membership.id)


@delivery_router.patch("/{task_id}", response_model=TaskResponse)
def patch_task(task_id: UUID, request: TaskUpdateRequest, db: Db, context: Owner) -> TaskResponse:
    task = delivery.update_task(
        db,
        context.tenant.id,
        context.membership.user_id,
        task_id,
        request.expected_version,
        request.delivery_date,
        request.notes,
        touch_date="delivery_date" in request.model_fields_set,
    )
    return delivery.task_response(db, context.tenant.id, task, context.membership.id)


@delivery_router.post("/{task_id}/complete", response_model=TaskResponse | MyWorkTask)
def complete_task(
    task_id: UUID, request: TaskCompleteRequest, db: Db, context: Member
) -> TaskResponse | MyWorkTask:
    """Owner or the assigned member. A driver gets back the least-privilege projection only."""
    task = delivery.complete_task(
        db, context.tenant.id, context.membership, task_id, request.expected_version, request.note
    )
    if context.membership.role is not TenantRole.OWNER:
        return delivery.my_work_task(db, context.tenant.id, task)
    return delivery.task_response(db, context.tenant.id, task, context.membership.id)


@delivery_router.post("/{task_id}/cancel", response_model=TaskResponse)
def cancel_task(task_id: UUID, request: TaskCancelRequest, db: Db, context: Owner) -> TaskResponse:
    task = delivery.cancel_task(
        db,
        context.tenant.id,
        context.membership.user_id,
        task_id,
        request.expected_version,
        request.reason,
    )
    return delivery.task_response(db, context.tenant.id, task, context.membership.id)


@delivery_router.post("/{task_id}/location", response_model=LocationUpdateResponse)
def post_task_location(
    task_id: UUID, request: LocationUpdateRequest, db: Db, context: Member
) -> LocationUpdateResponse:
    """A reading for the task's customer by the owner or the assigned member (D-061 precedence).
    `confirm` is the operator's explicit confirmation; nothing confirmed is replaced without it."""
    applied, reason, customer = delivery.update_task_location(
        db, context.tenant.id, context.membership, task_id, request
    )
    return LocationUpdateResponse(
        applied=applied, reason=reason, location=delivery.location_view(customer)
    )


@routes_router.post("/suggest-order", response_model=SuggestOrderResponse)
def post_suggest_order(
    request: SuggestOrderRequest, db: Db, context: Member
) -> SuggestOrderResponse:
    """Stop order for the given open deliveries: provider when configured and reachable,
    otherwise the labelled offline heuristic (D-060). Manual reorder stays available."""
    return delivery.suggest_stop_order(db, context.tenant.id, context.membership, request)


@routes_router.put("/order", response_model=MyWorkResponse)
def put_route_order(request: SaveOrderRequest, db: Db, context: Member) -> MyWorkResponse:
    """Persist a manual or accepted order as route_sequence 1..n."""
    delivery.save_stop_order(db, context.tenant.id, context.membership, request.task_ids)
    return delivery.my_work(db, context.tenant.id, context.membership)


@routes_router.get("/nearby-suppliers", response_model=NearbyResponse)
def get_nearby_suppliers(
    db: Db,
    context: Member,
    latitude: Annotated[float, Query(ge=-90, le=90)],
    longitude: Annotated[float, Query(ge=-180, le=180)],
    radius_meters: Annotated[int, Query(ge=50, le=20000)] = 1500,
) -> NearbyResponse:
    """One position check on request: suppliers nearby with an open pickup need (PHASE_07.md H).
    No background tracking; drivers see only their assigned lists and never a price."""
    return delivery.nearby_suppliers(
        db, context.tenant.id, context.membership, latitude, longitude, radius_meters
    )
