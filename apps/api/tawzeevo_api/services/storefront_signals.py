"""Storefront interactions, deterministic recommendations and featured campaigns.

PHASE_05.md D/K; D-048 (purchase = 10, view = 1), D-062 (one view per session/product per 30 min),
D-051 (raw views kept 90 days, then rolled up monthly without session keys). A purchase is a line
of the current confirmed revision of a CONFIRMED (not cancelled) invoice. No generative AI; the
ordering is a fixed sort so the same data always gives the same list.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, func, literal_column, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    AuditEvent,
    FeaturedCampaign,
    Invoice,
    InvoiceRevisionItem,
    InvoiceStatus,
    ProductInteraction,
    ProductInteractionRollup,
    Tenant,
    TenantProduct,
)
from tawzeevo_api.repositories.tenancy import all_tenant_ids, set_tenant_scope

PURCHASE_WEIGHT = 10
VIEW_WEIGHT = 1
VIEW_DEDUPE_WINDOW = timedelta(minutes=30)
RAW_VIEW_RETENTION = timedelta(days=90)
CAMPAIGN_DEFAULT_LENGTH = timedelta(days=7)


def _now() -> datetime:
    return datetime.now(UTC)


def session_key(session_id: str) -> str:
    """Pseudonymous: the storefront's random session id is stored only as a hash."""
    return hashlib.sha256(session_id.strip().encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------------------------


def record_view(
    db: Session, tenant_id: UUID, product_id: UUID, session_id: str, now: datetime | None = None
) -> bool:
    """Count one view per session/product per 30 minutes (D-062). Returns whether it counted."""
    moment = now or _now()
    if not session_id.strip():
        raise AppError(422, "SESSION_REQUIRED", "A storefront session id is required")
    key = session_key(session_id)
    published = db.scalar(
        select(TenantProduct.id).where(
            TenantProduct.id == product_id,
            TenantProduct.tenant_id == tenant_id,
            TenantProduct.is_published.is_(True),
        )
    )
    if published is None:
        raise AppError(404, "PRODUCT_NOT_FOUND", "Product was not found")
    recent = db.scalar(
        select(ProductInteraction.id).where(
            ProductInteraction.tenant_id == tenant_id,
            ProductInteraction.tenant_product_id == product_id,
            ProductInteraction.session_key == key,
            ProductInteraction.occurred_at > moment - VIEW_DEDUPE_WINDOW,
        )
    )
    if recent is not None:
        return False
    db.add(
        ProductInteraction(
            id=uuid4(),
            tenant_id=tenant_id,
            tenant_product_id=product_id,
            session_key=key,
            kind="VIEW",
            occurred_at=moment,
        )
    )
    db.commit()
    set_tenant_scope(db, tenant_id)
    return True


def rollup_views(db: Session, now: datetime | None = None) -> int:
    """D-051: fold raw views older than 90 days into monthly per-product counts, drop the rows.

    Tenant by tenant, from the global tenant list, with this tenant's RLS scope bound before the
    grouping read and before the rollup write, so the job folds the same rows under a database
    role that is subject to row-level security as under one that bypasses it.
    """
    moment = now or _now()
    cutoff = moment - RAW_VIEW_RETENTION
    folded = 0
    for tenant_id in all_tenant_ids(db):
        folded += _rollup_tenant_views(db, tenant_id, cutoff)
    return folded


def _rollup_tenant_views(db: Session, tenant_id: UUID, cutoff: datetime) -> int:
    set_tenant_scope(db, tenant_id)
    month_of = func.date_trunc(literal_column("'month'"), ProductInteraction.occurred_at)
    grouped = db.execute(
        select(
            ProductInteraction.tenant_product_id,
            month_of.label("month"),
            func.count().label("views"),
        )
        .where(
            ProductInteraction.tenant_id == tenant_id,
            ProductInteraction.occurred_at < cutoff,
        )
        .group_by(ProductInteraction.tenant_product_id, month_of)
    ).all()
    folded = 0
    for product_id, month, views in grouped:
        month_date = month.date() if isinstance(month, datetime) else date.fromisoformat(str(month))
        statement = pg_insert(ProductInteractionRollup).values(
            tenant_id=tenant_id, tenant_product_id=product_id, month=month_date, views=int(views)
        )
        db.execute(
            statement.on_conflict_do_update(
                index_elements=["tenant_id", "tenant_product_id", "month"],
                set_={"views": ProductInteractionRollup.views + int(views)},
            )
        )
        folded += int(views)
    if grouped:
        db.execute(
            delete(ProductInteraction).where(
                ProductInteraction.tenant_id == tenant_id,
                ProductInteraction.occurred_at < cutoff,
            )
        )
    db.commit()
    return folded


# ---------------------------------------------------------------------------------------------
# Scores and recommendations
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ProductScore:
    product_id: UUID
    views: int
    purchases: int

    @property
    def score(self) -> int:
        return PURCHASE_WEIGHT * self.purchases + VIEW_WEIGHT * self.views


def product_scores(db: Session, tenant_id: UUID) -> dict[UUID, ProductScore]:
    """Views (raw + rolled up) and valid purchases per published product of one business."""
    published = list(
        db.scalars(
            select(TenantProduct.id).where(
                TenantProduct.tenant_id == tenant_id, TenantProduct.is_published.is_(True)
            )
        )
    )
    if not published:
        return {}
    raw_views: dict[UUID, int] = {
        key: value
        for key, value in db.execute(
            select(ProductInteraction.tenant_product_id, func.count())
            .where(
                ProductInteraction.tenant_id == tenant_id,
                ProductInteraction.tenant_product_id.in_(published),
            )
            .group_by(ProductInteraction.tenant_product_id)
        ).all()
        if key is not None
    }
    rolled: dict[UUID, int] = {
        key: value
        for key, value in db.execute(
            select(
                ProductInteractionRollup.tenant_product_id,
                func.sum(ProductInteractionRollup.views),
            )
            .where(
                ProductInteractionRollup.tenant_id == tenant_id,
                ProductInteractionRollup.tenant_product_id.in_(published),
            )
            .group_by(ProductInteractionRollup.tenant_product_id)
        ).all()
        if key is not None
    }
    # A purchase: a line of the current confirmed revision of a confirmed, non-cancelled invoice.
    purchases: dict[UUID, int] = {
        key: value
        for key, value in db.execute(
            select(InvoiceRevisionItem.tenant_product_id, func.count())
            .join(
                Invoice,
                (Invoice.confirmed_revision_id == InvoiceRevisionItem.invoice_revision_id)
                & (Invoice.tenant_id == InvoiceRevisionItem.tenant_id),
            )
            .where(
                InvoiceRevisionItem.tenant_id == tenant_id,
                InvoiceRevisionItem.tenant_product_id.in_(published),
                Invoice.status == InvoiceStatus.CONFIRMED,
            )
            .group_by(InvoiceRevisionItem.tenant_product_id)
        ).all()
        if key is not None
    }
    return {
        product_id: ProductScore(
            product_id=product_id,
            views=int(raw_views.get(product_id, 0)) + int(rolled.get(product_id, 0) or 0),
            purchases=int(purchases.get(product_id, 0)),
        )
        for product_id in published
    }


def ranked_product_ids(db: Session, tenant_id: UUID, limit: int) -> list[UUID]:
    """Deterministic: score, then purchases, then name, then id."""
    scores = product_scores(db, tenant_id)
    if not scores:
        return []
    names: dict[UUID, str] = {
        key: value
        for key, value in db.execute(
            select(TenantProduct.id, TenantProduct.name).where(TenantProduct.id.in_(list(scores)))
        ).all()
        if key is not None
    }
    ordered = sorted(
        scores.values(),
        key=lambda row: (
            -row.score,
            -row.purchases,
            str(names.get(row.product_id, "")).lower(),
            str(row.product_id),
        ),
    )
    return [row.product_id for row in ordered[: max(1, limit)] if row.score > 0]


# ---------------------------------------------------------------------------------------------
# Featured campaigns
# ---------------------------------------------------------------------------------------------


def create_campaign(
    db: Session,
    tenant: Tenant,
    actor_id: UUID,
    product_id: UUID,
    starts_at: datetime | None,
    ends_at: datetime | None,
    priority: int,
) -> FeaturedCampaign:
    set_tenant_scope(db, tenant.id)
    product = db.scalar(
        select(TenantProduct).where(
            TenantProduct.id == product_id, TenantProduct.tenant_id == tenant.id
        )
    )
    if product is None:
        raise AppError(
            404, "PRODUCT_NOT_FOUND", "Only this business's own products can be featured"
        )
    start = starts_at or _now()
    end = ends_at or start + CAMPAIGN_DEFAULT_LENGTH
    if end <= start:
        raise AppError(422, "CAMPAIGN_INTERVAL", "A campaign must end after it starts")
    campaign = FeaturedCampaign(
        id=uuid4(),
        tenant_id=tenant.id,
        tenant_product_id=product.id,
        starts_at=start,
        ends_at=end,
        priority=priority,
        created_by_user_id=actor_id,
        created_at=_now(),
    )
    db.add(campaign)
    db.add(
        AuditEvent(
            tenant_id=tenant.id,
            actor_user_id=actor_id,
            action="FEATURED_CAMPAIGN_CREATED",
            entity_type="featured_campaign",
            entity_id=campaign.id,
            details={
                "product_id": str(product.id),
                "starts_at": start.isoformat(),
                "ends_at": end.isoformat(),
                "priority": priority,
            },
        )
    )
    db.commit()
    set_tenant_scope(db, tenant.id)
    return campaign


def cancel_campaign(
    db: Session, tenant_id: UUID, actor_id: UUID, campaign_id: UUID
) -> FeaturedCampaign:
    set_tenant_scope(db, tenant_id)
    campaign = db.get(FeaturedCampaign, campaign_id)
    if campaign is None or campaign.tenant_id != tenant_id:
        raise AppError(404, "CAMPAIGN_NOT_FOUND", "Campaign was not found")
    if campaign.cancelled_at is None:
        campaign.cancelled_at = _now()
        db.add(
            AuditEvent(
                tenant_id=tenant_id,
                actor_user_id=actor_id,
                action="FEATURED_CAMPAIGN_CANCELLED",
                entity_type="featured_campaign",
                entity_id=campaign.id,
                details={},
            )
        )
        db.commit()
        set_tenant_scope(db, tenant_id)
    return campaign


def list_campaigns(db: Session, tenant_id: UUID) -> list[FeaturedCampaign]:
    set_tenant_scope(db, tenant_id)
    return list(
        db.scalars(
            select(FeaturedCampaign)
            .where(FeaturedCampaign.tenant_id == tenant_id)
            .order_by(FeaturedCampaign.starts_at.desc(), FeaturedCampaign.created_at.desc())
        )
    )


def active_featured_product_ids(
    db: Session, tenant_id: UUID, now: datetime | None = None
) -> list[UUID]:
    """`starts_at <= now < ends_at`, ordered by priority, newer creation, then stable id."""
    moment = now or _now()
    rows = list(
        db.scalars(
            select(FeaturedCampaign)
            .where(
                FeaturedCampaign.tenant_id == tenant_id,
                FeaturedCampaign.cancelled_at.is_(None),
                FeaturedCampaign.starts_at <= moment,
                FeaturedCampaign.ends_at > moment,
            )
            .order_by(
                FeaturedCampaign.priority.desc(),
                FeaturedCampaign.created_at.desc(),
                FeaturedCampaign.id.asc(),
            )
        )
    )
    seen: set[UUID] = set()
    ordered: list[UUID] = []
    for row in rows:
        if row.tenant_product_id not in seen:
            seen.add(row.tenant_product_id)
            ordered.append(row.tenant_product_id)
    return ordered
