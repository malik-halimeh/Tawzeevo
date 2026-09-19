from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy.orm import Session

from tawzeevo_api.config import get_settings
from tawzeevo_api.database import get_db
from tawzeevo_api.dependencies import TenantContext, require_tenant_owner
from tawzeevo_api.schemas.branding import BrandingResponse, BrandingUpdateRequest
from tawzeevo_api.services import branding

branding_router = APIRouter(prefix="/api/v1/tenants/{tenant_id}/branding", tags=["branding"])

Owner = Annotated[TenantContext, Depends(require_tenant_owner)]
Db = Annotated[Session, Depends(get_db)]


@branding_router.get("", response_model=BrandingResponse)
def get_branding(db: Db, context: Owner) -> BrandingResponse:
    return branding.branding_response(db, context.tenant.id)


@branding_router.put("", response_model=BrandingResponse)
def put_branding(request: BrandingUpdateRequest, db: Db, context: Owner) -> BrandingResponse:
    """Presentation only (PHASE_08.md F): never roles, scoping, pricing or ledgers."""
    return branding.update_branding(db, context.tenant.id, context.membership.user_id, request)


@branding_router.post("/logo", response_model=BrandingResponse)
async def post_logo(
    db: Db, context: Owner, file: Annotated[UploadFile, File()]
) -> BrandingResponse:
    content = await file.read(get_settings().media_max_upload_bytes + 1)
    return branding.upload_logo(
        db, context.tenant.id, context.membership.user_id, content, file.content_type
    )


def logo_response(content: bytes, content_type: str, _tenant_id: UUID | None = None) -> Response:
    return Response(
        content=content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=3600", "X-Content-Type-Options": "nosniff"},
    )
