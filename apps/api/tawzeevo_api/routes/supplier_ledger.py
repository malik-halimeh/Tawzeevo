from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from tawzeevo_api.database import get_db
from tawzeevo_api.dependencies import TenantContext, require_tenant_owner
from tawzeevo_api.schemas.payments import PaymentReversalRequest
from tawzeevo_api.schemas.supplier_ledger import (
    SupplierBalancesResponse,
    SupplierLedgerEntryResponse,
    SupplierOpeningCorrectionRequest,
    SupplierOpeningRequest,
    SupplierPaymentRequest,
    SupplierPaymentResponse,
)
from tawzeevo_api.services.supplier_ledger import (
    correct_supplier_opening,
    record_supplier_opening,
    record_supplier_payment,
    reverse_supplier_payment,
    supplier_balances,
)

supplier_ledger_router = APIRouter(prefix="/api/v1/supplier-ledger", tags=["supplier ledger"])
supplier_payments_router = APIRouter(prefix="/api/v1/payments", tags=["supplier ledger"])


@supplier_ledger_router.get("/{supplier_id}/balances", response_model=SupplierBalancesResponse)
def get_balances(
    supplier_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> SupplierBalancesResponse:
    return supplier_balances(db, context.tenant.id, supplier_id)


@supplier_ledger_router.post(
    "/opening-balances", response_model=SupplierBalancesResponse, status_code=201
)
def create_opening(
    request: SupplierOpeningRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> SupplierBalancesResponse:
    return record_supplier_opening(db, context.tenant.id, context.membership.user_id, request)


@supplier_ledger_router.post(
    "/opening-balances/{entry_id}/correct",
    response_model=SupplierLedgerEntryResponse,
    status_code=201,
)
def correct_opening(
    entry_id: UUID,
    request: SupplierOpeningCorrectionRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> SupplierLedgerEntryResponse:
    return correct_supplier_opening(
        db,
        context.tenant.id,
        context.membership.user_id,
        entry_id,
        request,
    )


@supplier_payments_router.post(
    "/supplier-payments", response_model=SupplierPaymentResponse, status_code=201
)
def create_payment(
    request: SupplierPaymentRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> SupplierPaymentResponse:
    return record_supplier_payment(db, context.tenant.id, context.membership.user_id, request)


@supplier_payments_router.post(
    "/supplier-payments/{payment_id}/reverse",
    response_model=SupplierPaymentResponse,
    status_code=201,
)
def reverse_payment(
    payment_id: UUID,
    request: PaymentReversalRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> SupplierPaymentResponse:
    return reverse_supplier_payment(
        db, context.tenant.id, context.membership.user_id, payment_id, request
    )
