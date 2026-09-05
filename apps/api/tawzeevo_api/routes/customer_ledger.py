from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from tawzeevo_api.database import get_db
from tawzeevo_api.dependencies import TenantContext, require_tenant_owner
from tawzeevo_api.schemas.customer_ledger import (
    CustomerBalancesResponse,
    CustomerDebtListResponse,
    CustomerLedgerEntryResponse,
    FinancialSettingsRequest,
    FinancialSettingsResponse,
    OpeningBalanceRequest,
)
from tawzeevo_api.services.customer_ledger import (
    create_opening_balance,
    customer_balances,
    customer_debts,
    get_financial_settings,
    set_overdue_threshold,
)

customer_ledger_router = APIRouter(prefix="/api/v1/customer-ledger", tags=["customer ledger"])


@customer_ledger_router.post(
    "/opening-balances",
    response_model=CustomerLedgerEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_opening_balance(
    request: OpeningBalanceRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> CustomerLedgerEntryResponse:
    return create_opening_balance(
        db,
        context.tenant.id,
        context.membership.user_id,
        request,
    )


@customer_ledger_router.get(
    "/customers/{customer_id}/balances", response_model=CustomerBalancesResponse
)
def get_customer_balances(
    customer_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> CustomerBalancesResponse:
    return customer_balances(db, context.tenant.id, customer_id)


@customer_ledger_router.get("/settings", response_model=FinancialSettingsResponse)
def get_customer_ledger_settings(
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> FinancialSettingsResponse:
    return get_financial_settings(db, context.tenant.id)


@customer_ledger_router.put("/settings", response_model=FinancialSettingsResponse)
def update_customer_ledger_settings(
    request: FinancialSettingsRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> FinancialSettingsResponse:
    return set_overdue_threshold(
        db,
        context.tenant.id,
        context.membership.user_id,
        request.customer_overdue_threshold_days,
    )


@customer_ledger_router.get("/debts", response_model=CustomerDebtListResponse)
def list_customer_debts(
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> CustomerDebtListResponse:
    return customer_debts(db, context.tenant.id)
