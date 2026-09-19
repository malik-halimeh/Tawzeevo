from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from tawzeevo_api.database import get_db
from tawzeevo_api.dependencies import TenantContext, require_tenant_owner
from tawzeevo_api.schemas.supplier_purchases import (
    OutstandingTotalsResponse,
    PurchaseCreateRequest,
    PurchaseListResponse,
    PurchaseResponse,
    PurchaseReverseRequest,
)
from tawzeevo_api.services import supplier_purchases

supplier_purchases_router = APIRouter(prefix="/api/v1/supplier-purchases", tags=["suppliers"])
outstanding_router = APIRouter(prefix="/api/v1/supplier-ledger", tags=["supplier ledger"])

Owner = Annotated[TenantContext, Depends(require_tenant_owner)]
Db = Annotated[Session, Depends(get_db)]


@supplier_purchases_router.get("", response_model=PurchaseListResponse)
def get_purchases(
    db: Db, context: Owner, supplier_id: Annotated[UUID | None, Query()] = None
) -> PurchaseListResponse:
    rows = supplier_purchases.list_purchases(db, context.tenant.id, supplier_id)
    return PurchaseListResponse(
        purchases=[supplier_purchases.purchase_response(db, context.tenant.id, r) for r in rows]
    )


@supplier_purchases_router.post("", response_model=PurchaseResponse)
def post_purchase(
    request: PurchaseCreateRequest, response: Response, db: Db, context: Owner
) -> PurchaseResponse:
    """Finalize an actual purchase: history + payable + procurement progress, atomically."""
    purchase, replayed = supplier_purchases.record_purchase(
        db, context.tenant.id, context.membership.user_id, request
    )
    response.status_code = status.HTTP_200_OK if replayed else status.HTTP_201_CREATED
    return supplier_purchases.purchase_response(db, context.tenant.id, purchase, replayed)


@supplier_purchases_router.get("/{purchase_id}", response_model=PurchaseResponse)
def get_purchase(purchase_id: UUID, db: Db, context: Owner) -> PurchaseResponse:
    row = supplier_purchases.get_purchase(db, context.tenant.id, purchase_id)
    return supplier_purchases.purchase_response(db, context.tenant.id, row)


@supplier_purchases_router.post("/{purchase_id}/reverse", response_model=PurchaseResponse)
def reverse_purchase(
    purchase_id: UUID, request: PurchaseReverseRequest, db: Db, context: Owner
) -> PurchaseResponse:
    row = supplier_purchases.reverse_purchase(
        db,
        context.tenant.id,
        context.membership.user_id,
        purchase_id,
        request.idempotency_key,
        request.reason,
    )
    return supplier_purchases.purchase_response(db, context.tenant.id, row)


@outstanding_router.get("/totals", response_model=OutstandingTotalsResponse)
def get_outstanding_totals(db: Db, context: Owner) -> OutstandingTotalsResponse:
    """Customer outstanding and supplier payable by currency; never summed across currencies."""
    return supplier_purchases.outstanding_totals(db, context.tenant.id)
