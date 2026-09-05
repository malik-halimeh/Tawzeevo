from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from tawzeevo_api.config import get_settings
from tawzeevo_api.database import get_db
from tawzeevo_api.dependencies import TenantContext, require_tenant_owner
from tawzeevo_api.models import ProductPriceBasis
from tawzeevo_api.schemas.invoice_editor import (
    CalculatorRequest,
    CalculatorResponse,
    CatalogSearchResponse,
    InvoiceCancelRequest,
    InvoiceConfirmRequest,
    InvoiceEditorDraftRequest,
    InvoiceEditorResponse,
    InvoiceHistoryResponse,
    ItemParserRequest,
    ItemParserResponse,
    ProductCostOptionsResponse,
)
from tawzeevo_api.services.invoice_editor import (
    calculate_expression,
    create_editor_draft,
    get_editor_draft,
    parse_item_text,
    product_cost_options,
    search_catalog,
)
from tawzeevo_api.services.invoice_finance import (
    cancel_invoice,
    confirm_invoice,
    get_invoice_history,
    update_invoice,
)

invoices_router = APIRouter(prefix="/api/v1/invoices", tags=["invoice editor"])


@invoices_router.post("/calculator", response_model=CalculatorResponse)
def invoice_calculator(
    request: CalculatorRequest,
    _context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> CalculatorResponse:
    return CalculatorResponse(
        expression=request.expression,
        value=calculate_expression(request.expression),
    )


@invoices_router.get("/catalog-search", response_model=CatalogSearchResponse)
def invoice_catalog_search(
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
    query: Annotated[str, Query(min_length=1, max_length=200)],
    limit: Annotated[int, Query(ge=1, le=50)] = 12,
) -> CatalogSearchResponse:
    return search_catalog(db, context.tenant.id, query, limit=limit)


@invoices_router.post("/item-parser", response_model=ItemParserResponse)
def invoice_item_parser(
    request: ItemParserRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> ItemParserResponse:
    return parse_item_text(
        db,
        context.tenant.id,
        request.text,
        threshold=get_settings().invoice_fuzzy_match_threshold,
    )


@invoices_router.get(
    "/products/{product_id}/cost-options", response_model=ProductCostOptionsResponse
)
def invoice_product_cost_options(
    product_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
    currency: Annotated[str, Query(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")],
    basis: ProductPriceBasis,
) -> ProductCostOptionsResponse:
    return product_cost_options(db, context.tenant.id, product_id, currency, basis)


@invoices_router.post("", response_model=InvoiceEditorResponse, status_code=status.HTTP_201_CREATED)
def create_invoice_editor_draft(
    request: InvoiceEditorDraftRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> InvoiceEditorResponse:
    return create_editor_draft(
        db,
        context.tenant.id,
        context.membership.user_id,
        request,
        fuzzy_threshold=get_settings().invoice_fuzzy_match_threshold,
    )


@invoices_router.get("/{invoice_id}", response_model=InvoiceEditorResponse)
def get_invoice_editor_draft(
    invoice_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> InvoiceEditorResponse:
    return get_editor_draft(db, context.tenant.id, invoice_id)


@invoices_router.put("/{invoice_id}", response_model=InvoiceEditorResponse)
def update_invoice_editor_draft(
    invoice_id: UUID,
    request: InvoiceEditorDraftRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> InvoiceEditorResponse:
    return update_invoice(
        db,
        context.tenant.id,
        context.membership.user_id,
        invoice_id,
        request,
        fuzzy_threshold=get_settings().invoice_fuzzy_match_threshold,
    )


@invoices_router.post("/{invoice_id}/confirm", response_model=InvoiceEditorResponse)
def confirm_invoice_editor(
    invoice_id: UUID,
    request: InvoiceConfirmRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> InvoiceEditorResponse:
    return confirm_invoice(
        db,
        context.tenant.id,
        context.membership.user_id,
        invoice_id,
        request.expected_revision_id,
    )


@invoices_router.post("/{invoice_id}/cancel", response_model=InvoiceEditorResponse)
def cancel_invoice_editor(
    invoice_id: UUID,
    request: InvoiceCancelRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> InvoiceEditorResponse:
    return cancel_invoice(
        db,
        context.tenant.id,
        context.membership.user_id,
        invoice_id,
        request,
    )


@invoices_router.get("/{invoice_id}/history", response_model=InvoiceHistoryResponse)
def invoice_revision_history(
    invoice_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> InvoiceHistoryResponse:
    return get_invoice_history(db, context.tenant.id, invoice_id)
