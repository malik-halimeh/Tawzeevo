from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from tawzeevo_api.database import get_db
from tawzeevo_api.dependencies import TenantContext, require_tenant_owner
from tawzeevo_api.schemas.payments import (
    CustomerObligationListResponse,
    CustomerPaymentResponse,
    CustomerReceiptRequest,
    CustomerRefundRequest,
    PaymentReversalRequest,
)
from tawzeevo_api.services.payments import (
    customer_obligations,
    record_customer_receipt,
    record_customer_refund,
    reverse_customer_receipt,
)

payments_router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


@payments_router.get(
    "/customers/{customer_id}/obligations",
    response_model=CustomerObligationListResponse,
)
def list_customer_obligations(
    customer_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
    currency: Annotated[str, Query(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")],
) -> CustomerObligationListResponse:
    return customer_obligations(db, context.tenant.id, customer_id, currency)


@payments_router.post(
    "/customer-receipts",
    response_model=CustomerPaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_customer_receipt(
    request: CustomerReceiptRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> CustomerPaymentResponse:
    return record_customer_receipt(
        db,
        context.tenant.id,
        context.membership.user_id,
        request,
    )


@payments_router.post(
    "/{payment_id}/reverse",
    response_model=CustomerPaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def reverse_receipt(
    payment_id: UUID,
    request: PaymentReversalRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> CustomerPaymentResponse:
    return reverse_customer_receipt(
        db,
        context.tenant.id,
        context.membership.user_id,
        payment_id,
        request,
    )


@payments_router.post(
    "/customer-refunds",
    response_model=CustomerPaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_customer_refund(
    request: CustomerRefundRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> CustomerPaymentResponse:
    return record_customer_refund(
        db,
        context.tenant.id,
        context.membership.user_id,
        request,
    )
