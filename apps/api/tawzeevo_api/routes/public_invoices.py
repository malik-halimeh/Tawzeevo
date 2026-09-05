from base64 import b64encode
from hashlib import sha256
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from tawzeevo_api.database import get_db
from tawzeevo_api.dependencies import TenantContext, require_tenant_owner
from tawzeevo_api.schemas.public_invoices import (
    CapabilityResponse,
    IssuedCapabilityResponse,
    PublicInvoiceResponse,
)
from tawzeevo_api.services.public_invoices import (
    issue_capability,
    list_capabilities,
    resolve_public_invoice,
    revoke_capability,
)

capabilities_router = APIRouter(prefix="/api/v1/invoices", tags=["invoice sharing"])
public_invoices_router = APIRouter(prefix="/api/v1/public", tags=["public invoices"])
_PAGE = (Path(__file__).parents[1] / "templates" / "public_invoice.html").read_text(
    encoding="utf-8"
)
_SCRIPT = _PAGE.split("<script>", 1)[1].split("</script>", 1)[0]
_SCRIPT_HASH = b64encode(sha256(_SCRIPT.encode()).digest()).decode()


@capabilities_router.get("/{invoice_id}/capabilities", response_model=list[CapabilityResponse])
def invoice_links(
    invoice_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> list[CapabilityResponse]:
    return list_capabilities(db, context.tenant.id, invoice_id)


@capabilities_router.post(
    "/{invoice_id}/capabilities", response_model=IssuedCapabilityResponse, status_code=201
)
def create_invoice_link(
    invoice_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> IssuedCapabilityResponse:
    return issue_capability(db, context.tenant.id, context.membership.user_id, invoice_id)


@capabilities_router.post(
    "/{invoice_id}/capabilities/{capability_id}/rotate",
    response_model=IssuedCapabilityResponse,
    status_code=201,
)
def rotate_invoice_link(
    invoice_id: UUID,
    capability_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> IssuedCapabilityResponse:
    return issue_capability(
        db, context.tenant.id, context.membership.user_id, invoice_id, rotate_id=capability_id
    )


@capabilities_router.delete("/{invoice_id}/capabilities/{capability_id}", status_code=204)
def revoke_invoice_link(
    invoice_id: UUID,
    capability_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> Response:
    revoke_capability(db, context.tenant.id, context.membership.user_id, invoice_id, capability_id)
    return Response(status_code=204)


@public_invoices_router.get("/invoice", response_class=HTMLResponse, include_in_schema=False)
def public_invoice_page() -> HTMLResponse:
    return HTMLResponse(
        _PAGE,
        headers={
            "Content-Security-Policy": (
                f"default-src 'none'; script-src 'sha256-{_SCRIPT_HASH}'; "
                "style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; "
                "frame-ancestors 'none'; form-action 'none'"
            ),
        },
    )


@public_invoices_router.get(
    "/invoice/data",
    response_model=PublicInvoiceResponse,
    description="Supply X-Invoice-Capability. Never put the token in a URL.",
)
def public_invoice_data(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> PublicInvoiceResponse:
    # Deliberately avoid validation errors echoing a secret header into the response/logs.
    return resolve_public_invoice(db, request.headers.get("X-Invoice-Capability", ""))
