from __future__ import annotations

import math
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    AuditEvent,
    Tenant,
    TenantApplication,
    TenantApplicationStatus,
    TenantMembership,
    TenantRole,
    TenantStatus,
    User,
)
from tawzeevo_api.schemas.platform import (
    AccessPeriodRequest,
    AccessState,
    ReactivateTenantRequest,
    SuspendTenantRequest,
    TenantApplicationApproveRequest,
    TenantApplicationCreateRequest,
    TenantApplicationReviewRequest,
    TenantResponse,
)


def _set_tenant_scope(db: Session, tenant_id: UUID) -> None:
    db.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


def _set_platform_audit_scope(db: Session) -> None:
    db.execute(text("SELECT set_config('app.platform_audit', 'true', true)"))


def _access_state(tenant: Tenant, today: date | None = None) -> AccessState:
    current_date = today or date.today()
    if tenant.access_until is None or current_date <= tenant.access_until:
        return AccessState.CURRENT
    if tenant.grace_until is not None and current_date <= tenant.grace_until:
        return AccessState.GRACE
    return AccessState.OVERDUE


def tenant_response(tenant: Tenant) -> TenantResponse:
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        status=tenant.status,
        access_until=tenant.access_until,
        grace_until=tenant.grace_until,
        access_status=_access_state(tenant),
        suspension_reason=tenant.suspension_reason,
        activated_at=tenant.activated_at,
        suspended_at=tenant.suspended_at,
        reactivated_at=tenant.reactivated_at,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
    )


def submit_application(
    db: Session, applicant: User, request: TenantApplicationCreateRequest
) -> TenantApplication:
    application = TenantApplication(
        applicant_user_id=applicant.id,
        business_name=request.business_name,
        status=TenantApplicationStatus.PENDING,
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


def list_applications(
    db: Session,
    *,
    page: int,
    limit: int,
    application_status: TenantApplicationStatus | None,
) -> tuple[list[TenantApplication], int, int]:
    conditions: list[ColumnElement[bool]] = []
    if application_status is not None:
        conditions.append(TenantApplication.status == application_status)
    total = int(
        db.scalar(select(func.count()).select_from(TenantApplication).where(*conditions)) or 0
    )
    applications = list(
        db.scalars(
            select(TenantApplication)
            .where(*conditions)
            .order_by(TenantApplication.created_at.asc(), TenantApplication.id.asc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    )
    return applications, total, math.ceil(total / limit) if total else 0


def _pending_application_for_update(db: Session, application_id: UUID) -> TenantApplication:
    application = db.scalar(
        select(TenantApplication).where(TenantApplication.id == application_id).with_for_update()
    )
    if application is None:
        raise AppError(404, "TENANT_APPLICATION_NOT_FOUND", "Tenant application was not found")
    if application.status is not TenantApplicationStatus.PENDING:
        raise AppError(
            409,
            "TENANT_APPLICATION_ALREADY_REVIEWED",
            "Tenant application has already been reviewed",
        )
    return application


def approve_application(
    db: Session,
    application_id: UUID,
    reviewer: User,
    request: TenantApplicationApproveRequest,
) -> TenantApplication:
    application = _pending_application_for_update(db, application_id)
    applicant = db.scalar(
        select(User).where(User.id == application.applicant_user_id).with_for_update()
    )
    if applicant is None or applicant.is_deleted:
        raise AppError(
            409,
            "APPLICANT_UNAVAILABLE",
            "The applicant is not available to become the tenant owner",
        )

    now = datetime.now(UTC)
    tenant = Tenant(
        name=application.business_name,
        status=TenantStatus.ACTIVE,
        access_until=request.access_until,
        grace_until=request.grace_until,
        activated_at=now,
    )
    db.add(tenant)
    db.flush()
    _set_tenant_scope(db, tenant.id)
    db.add(
        TenantMembership(
            tenant_id=tenant.id,
            user_id=applicant.id,
            role=TenantRole.OWNER,
            is_active=True,
        )
    )
    application.status = TenantApplicationStatus.APPROVED
    application.reviewed_by_user_id = reviewer.id
    application.reviewed_at = now
    application.review_notes = request.review_notes
    application.tenant_id = tenant.id
    db.add(
        AuditEvent(
            tenant_id=tenant.id,
            actor_user_id=reviewer.id,
            action="TENANT_APPLICATION_APPROVED",
            entity_type="tenant_application",
            entity_id=application.id,
            details={"tenant_id": str(tenant.id), "applicant_user_id": str(applicant.id)},
        )
    )
    db.commit()
    db.refresh(application)
    return application


def reject_application(
    db: Session,
    application_id: UUID,
    reviewer: User,
    request: TenantApplicationReviewRequest,
) -> TenantApplication:
    application = _pending_application_for_update(db, application_id)
    now = datetime.now(UTC)
    application.status = TenantApplicationStatus.REJECTED
    application.reviewed_by_user_id = reviewer.id
    application.reviewed_at = now
    application.review_notes = request.review_notes
    _set_platform_audit_scope(db)
    db.add(
        AuditEvent(
            tenant_id=None,
            actor_user_id=reviewer.id,
            action="TENANT_APPLICATION_REJECTED",
            entity_type="tenant_application",
            entity_id=application.id,
            details={"applicant_user_id": str(application.applicant_user_id)},
        )
    )
    db.commit()
    db.refresh(application)
    return application


def list_tenants(
    db: Session,
    *,
    page: int,
    limit: int,
    name_search: str | None,
    tenant_status: TenantStatus | None,
) -> tuple[list[Tenant], int, int]:
    conditions: list[ColumnElement[bool]] = []
    if name_search is not None and name_search.strip():
        conditions.append(Tenant.name.ilike(f"%{name_search.strip()}%"))
    if tenant_status is not None:
        conditions.append(Tenant.status == tenant_status)
    total = int(db.scalar(select(func.count()).select_from(Tenant).where(*conditions)) or 0)
    tenants = list(
        db.scalars(
            select(Tenant)
            .where(*conditions)
            .order_by(Tenant.created_at.asc(), Tenant.id.asc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    )
    return tenants, total, math.ceil(total / limit) if total else 0


def _tenant_for_update(db: Session, tenant_id: UUID) -> Tenant:
    tenant = db.scalar(select(Tenant).where(Tenant.id == tenant_id).with_for_update())
    if tenant is None:
        raise AppError(404, "TENANT_NOT_FOUND", "Tenant was not found")
    return tenant


def _ensure_not_shortened(tenant: Tenant, new_access_until: date) -> None:
    if tenant.access_until is not None and new_access_until < tenant.access_until:
        raise AppError(
            409,
            "ACCESS_PERIOD_CANNOT_BE_SHORTENED",
            "The tenant access period may only be set or extended",
        )


def _audit_tenant_change(
    db: Session,
    tenant: Tenant,
    actor: User,
    action: str,
    details: dict[str, str | None],
) -> None:
    _set_tenant_scope(db, tenant.id)
    db.add(
        AuditEvent(
            tenant_id=tenant.id,
            actor_user_id=actor.id,
            action=action,
            entity_type="tenant",
            entity_id=tenant.id,
            details=details,
        )
    )


def set_access_period(
    db: Session, tenant_id: UUID, actor: User, request: AccessPeriodRequest
) -> Tenant:
    tenant = _tenant_for_update(db, tenant_id)
    _ensure_not_shortened(tenant, request.access_until)
    previous_access = tenant.access_until
    previous_grace = tenant.grace_until
    tenant.access_until = request.access_until
    tenant.grace_until = request.grace_until
    _audit_tenant_change(
        db,
        tenant,
        actor,
        "TENANT_ACCESS_PERIOD_UPDATED",
        {
            "previous_access_until": str(previous_access) if previous_access else None,
            "access_until": str(tenant.access_until),
            "previous_grace_until": str(previous_grace) if previous_grace else None,
            "grace_until": str(tenant.grace_until) if tenant.grace_until else None,
        },
    )
    db.commit()
    db.refresh(tenant)
    return tenant


def suspend_tenant(
    db: Session, tenant_id: UUID, actor: User, request: SuspendTenantRequest
) -> Tenant:
    tenant = _tenant_for_update(db, tenant_id)
    if tenant.status is not TenantStatus.ACTIVE:
        raise AppError(409, "TENANT_NOT_ACTIVE", "Only an active tenant can be suspended")
    tenant.status = TenantStatus.SUSPENDED
    tenant.suspension_reason = request.reason
    tenant.suspended_at = datetime.now(UTC)
    _audit_tenant_change(
        db,
        tenant,
        actor,
        "TENANT_SUSPENDED",
        {"reason": request.reason.value},
    )
    db.commit()
    db.refresh(tenant)
    return tenant


def reactivate_tenant(
    db: Session, tenant_id: UUID, actor: User, request: ReactivateTenantRequest
) -> Tenant:
    tenant = _tenant_for_update(db, tenant_id)
    if tenant.status is not TenantStatus.SUSPENDED:
        raise AppError(409, "TENANT_NOT_SUSPENDED", "Only a suspended tenant can be reactivated")
    if request.access_until is not None:
        _ensure_not_shortened(tenant, request.access_until)
        tenant.access_until = request.access_until
    if "grace_until" in request.model_fields_set:
        tenant.grace_until = request.grace_until
    if (
        tenant.access_until is not None
        and tenant.grace_until is not None
        and tenant.grace_until < tenant.access_until
    ):
        raise AppError(400, "INVALID_ACCESS_PERIOD", "grace_until must not precede access_until")
    tenant.status = TenantStatus.ACTIVE
    tenant.suspension_reason = None
    tenant.reactivated_at = datetime.now(UTC)
    _audit_tenant_change(
        db,
        tenant,
        actor,
        "TENANT_REACTIVATED",
        {
            "access_until": str(tenant.access_until) if tenant.access_until else None,
            "grace_until": str(tenant.grace_until) if tenant.grace_until else None,
        },
    )
    db.commit()
    db.refresh(tenant)
    return tenant
