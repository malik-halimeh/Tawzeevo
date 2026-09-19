"""Owner team management (PHASE_07.md A/C/J): add a registered user as a driver, list the
members, revoke a membership. One membership keeps one role; the last active owner is protected by
the membership service; a revoked member loses its sync devices in the same transaction."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from tawzeevo_api.database import get_db
from tawzeevo_api.dependencies import TenantContext, require_tenant_owner
from tawzeevo_api.errors import AppError
from tawzeevo_api.models import SystemUserType, TenantMembership, TenantRole, User
from tawzeevo_api.repositories.auth import get_user_by_email
from tawzeevo_api.repositories.tenancy import set_tenant_scope
from tawzeevo_api.services.memberships import create_membership, revoke_membership

team_router = APIRouter(prefix="/api/v1/tenants/{tenant_id}/memberships", tags=["team"])

Owner = Annotated[TenantContext, Depends(require_tenant_owner)]
Db = Annotated[Session, Depends(get_db)]


class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: TenantRole
    is_active: bool
    display_name: str
    email: str
    is_self: bool
    created_at: datetime
    revoked_at: datetime | None


class MemberListResponse(BaseModel):
    members: list[MemberResponse]


class AddDriverRequest(BaseModel):
    """The driver must already have a Tawzeevo account (registered themself); the owner attaches
    it to the business as a driver. Owners are created only through platform approval."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr


def _member(db: Session, membership: TenantMembership, viewer_id: UUID) -> MemberResponse:
    user = db.get(User, membership.user_id)
    return MemberResponse(
        id=membership.id,
        role=membership.role,
        is_active=membership.is_active,
        display_name=f"{user.first_name} {user.last_name}".strip() if user else "?",
        email=user.email if user else "",
        is_self=membership.id == viewer_id,
        created_at=membership.created_at,
        revoked_at=membership.revoked_at,
    )


@team_router.get("", response_model=MemberListResponse)
def list_members(db: Db, context: Owner) -> MemberListResponse:
    set_tenant_scope(db, context.tenant.id)
    rows = db.scalars(
        select(TenantMembership)
        .where(TenantMembership.tenant_id == context.tenant.id)
        .order_by(TenantMembership.created_at.asc())
    )
    return MemberListResponse(members=[_member(db, row, context.membership.id) for row in rows])


@team_router.post("", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
def add_driver(request: AddDriverRequest, db: Db, context: Owner) -> MemberResponse:
    user = get_user_by_email(db, str(request.email))
    if user is None or user.is_deleted or user.type is not SystemUserType.CLIENT:
        raise AppError(
            404,
            "DRIVER_ACCOUNT_NOT_FOUND",
            "No client account with this e-mail; they must register first",
        )
    membership = create_membership(db, context.tenant.id, user.id, TenantRole.DRIVER)
    return _member(db, membership, context.membership.id)


@team_router.post("/{membership_id}/revoke", response_model=MemberResponse)
def revoke_member(membership_id: UUID, db: Db, context: Owner) -> MemberResponse:
    if membership_id == context.membership.id:
        raise AppError(409, "CANNOT_REVOKE_SELF", "You cannot revoke your own membership")
    membership = revoke_membership(db, context.tenant.id, membership_id)
    return _member(db, membership, context.membership.id)
