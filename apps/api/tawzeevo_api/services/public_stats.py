"""Safe public aggregates (PHASE_08.md G; D-070).

Only platform-wide counts that identify nobody: active businesses, published products, confirmed
invoices in the last 30 days, registered customers. Never revenue, debt, supplier prices,
customer history or anything per business. When the platform is too small to hide anyone —
fewer than 5 active businesses or fewer than 20 customers — the figures are withheld and the
response says so (D-070). Computed without any tenant scope: counts only, across the platform.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from tawzeevo_api.models import (
    Customer,
    Invoice,
    InvoiceStatus,
    Tenant,
    TenantProduct,
    TenantStatus,
)
from tawzeevo_api.schemas.public_stats import PlatformStatsResponse

MIN_TENANTS = 5
MIN_CUSTOMERS = 20


def _platform_wide(db: Session) -> None:
    # Platform counts must not be filtered by a tenant scope left on the connection.
    db.execute(text("SELECT set_config('app.current_tenant_id', '', true)"))


def platform_stats(db: Session, now: datetime | None = None) -> PlatformStatsResponse:
    _platform_wide(db)
    moment = now or datetime.now(UTC)
    tenants = int(
        db.scalar(
            select(func.count()).select_from(Tenant).where(Tenant.status == TenantStatus.ACTIVE)
        )
        or 0
    )
    # Tenant-owned tables are RLS-forced: count them per active business under its own scope.
    customers = 0
    products = 0
    invoices = 0
    for tenant_id in db.scalars(select(Tenant.id).where(Tenant.status == TenantStatus.ACTIVE)):
        db.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, true)"), {"tid": str(tenant_id)}
        )
        customers += int(
            db.scalar(
                select(func.count()).select_from(Customer).where(Customer.tenant_id == tenant_id)
            )
            or 0
        )
        products += int(
            db.scalar(
                select(func.count())
                .select_from(TenantProduct)
                .where(TenantProduct.tenant_id == tenant_id, TenantProduct.is_published.is_(True))
            )
            or 0
        )
        invoices += int(
            db.scalar(
                select(func.count())
                .select_from(Invoice)
                .where(
                    Invoice.tenant_id == tenant_id,
                    Invoice.status == InvoiceStatus.CONFIRMED,
                    Invoice.confirmed_at >= moment - timedelta(days=30),
                )
            )
            or 0
        )
    _platform_wide(db)
    sufficient = tenants >= MIN_TENANTS and customers >= MIN_CUSTOMERS
    return PlatformStatsResponse(
        sufficient_data=sufficient,
        minimum_businesses=MIN_TENANTS,
        minimum_customers=MIN_CUSTOMERS,
        active_businesses=tenants if sufficient else None,
        registered_customers=customers if sufficient else None,
        published_products=products if sufficient else None,
        confirmed_invoices_last_30_days=invoices if sufficient else None,
        generated_at=moment,
    )
