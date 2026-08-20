from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query, status
from sqlalchemy.orm import Session

from tawzeevo_api.database import get_db
from tawzeevo_api.dependencies import require_client, require_system_admin
from tawzeevo_api.models import TenantApplicationStatus, TenantStatus, User
from tawzeevo_api.schemas.platform import (
    AccessPeriodRequest,
    ReactivateTenantRequest,
    SuspendTenantRequest,
    TenantApplicationApproveRequest,
    TenantApplicationCreateRequest,
    TenantApplicationListResponse,
    TenantApplicationResponse,
    TenantApplicationReviewRequest,
    TenantListResponse,
    TenantResponse,
)
from tawzeevo_api.services.platform import (
    approve_application,
    list_applications,
    list_tenants,
    reactivate_tenant,
    reject_application,
    set_access_period,
    submit_application,
    suspend_tenant,
    tenant_response,
)

tenant_applications_router = APIRouter(prefix="/api/v1", tags=["tenant applications"])
platform_router = APIRouter(prefix="/api/v1/platform", tags=["platform administration"])


@tenant_applications_router.post(
    "/tenant-applications",
    response_model=TenantApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_tenant_application(
    request: TenantApplicationCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    applicant: Annotated[User, Depends(require_client)],
) -> TenantApplicationResponse:
    return TenantApplicationResponse.model_validate(submit_application(db, applicant, request))


@platform_router.get("/tenant-applications", response_model=TenantApplicationListResponse)
def platform_list_applications(
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(require_system_admin)],
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    application_status: Annotated[TenantApplicationStatus | None, Query(alias="status")] = None,
) -> TenantApplicationListResponse:
    applications, total, total_pages = list_applications(
        db,
        page=page,
        limit=limit,
        application_status=application_status,
    )
    return TenantApplicationListResponse(
        page=page,
        limit=limit,
        total=total,
        total_pages=total_pages,
        applications=[TenantApplicationResponse.model_validate(item) for item in applications],
    )


@platform_router.post(
    "/tenant-applications/{application_id}/approve",
    response_model=TenantApplicationResponse,
)
def platform_approve_application(
    application_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_system_admin)],
    request: TenantApplicationApproveRequest = Body(
        default_factory=TenantApplicationApproveRequest
    ),
) -> TenantApplicationResponse:
    return TenantApplicationResponse.model_validate(
        approve_application(db, application_id, admin, request)
    )


@platform_router.post(
    "/tenant-applications/{application_id}/reject",
    response_model=TenantApplicationResponse,
)
def platform_reject_application(
    application_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_system_admin)],
    request: TenantApplicationReviewRequest = Body(default_factory=TenantApplicationReviewRequest),
) -> TenantApplicationResponse:
    return TenantApplicationResponse.model_validate(
        reject_application(db, application_id, admin, request)
    )


@platform_router.get("/tenants", response_model=TenantListResponse)
def platform_list_tenants(
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(require_system_admin)],
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    search: str | None = None,
    tenant_status: Annotated[TenantStatus | None, Query(alias="status")] = None,
) -> TenantListResponse:
    tenants, total, total_pages = list_tenants(
        db,
        page=page,
        limit=limit,
        name_search=search,
        tenant_status=tenant_status,
    )
    return TenantListResponse(
        page=page,
        limit=limit,
        total=total,
        total_pages=total_pages,
        tenants=[tenant_response(tenant) for tenant in tenants],
    )


@platform_router.put("/tenants/{tenant_id}/access-period", response_model=TenantResponse)
def platform_set_access_period(
    tenant_id: UUID,
    request: AccessPeriodRequest,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_system_admin)],
) -> TenantResponse:
    return tenant_response(set_access_period(db, tenant_id, admin, request))


@platform_router.post("/tenants/{tenant_id}/suspend", response_model=TenantResponse)
def platform_suspend_tenant(
    tenant_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_system_admin)],
    request: SuspendTenantRequest = Body(default_factory=SuspendTenantRequest),
) -> TenantResponse:
    return tenant_response(suspend_tenant(db, tenant_id, admin, request))


@platform_router.post("/tenants/{tenant_id}/reactivate", response_model=TenantResponse)
def platform_reactivate_tenant(
    tenant_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_system_admin)],
    request: ReactivateTenantRequest = Body(default_factory=ReactivateTenantRequest),
) -> TenantResponse:
    return tenant_response(reactivate_tenant(db, tenant_id, admin, request))
