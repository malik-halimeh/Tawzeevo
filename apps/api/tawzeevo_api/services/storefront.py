"""Public per-business storefront catalog and owner slug management (PHASE_05.md A/B/C; D-047).

A product is public only when it belongs to the business assortment, is published, and the
business is ACTIVE. Master products are never shown on their own. The storefront shows the public
standard price and packaging; it never shows or derives stock, availability, grades or costs.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    AuditEvent,
    Category,
    MasterProductImage,
    Tenant,
    TenantBarcode,
    TenantProduct,
    TenantProductImage,
    TenantSlugRedirect,
    TenantStatus,
)
from tawzeevo_api.repositories.tenancy import set_tenant_scope
from tawzeevo_api.schemas.storefront import (
    PublicCategory,
    PublicImage,
    PublicPackaging,
    PublicProduct,
    PublicProductPage,
    PublicStorefront,
    SlugResolution,
    StorefrontSettings,
)
from tawzeevo_api.services.branding import public_branding
from tawzeevo_api.services.customer_access import CustomerContext
from tawzeevo_api.services.pricing import derive_counterpart_prices, resolve_product_pricing

SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,48}[a-z0-9])?$")
RESERVED_SLUGS = frozenset(
    {
        "api", "admin", "app", "apps", "assets", "backup", "docs", "health", "login", "logout",
        "platform", "profile", "public", "register", "static", "stats", "storefront",
        "tawzeevo", "workspace", "www",
    }
)  # fmt: skip
PAGE_SIZE = 24
MAX_PAGE_SIZE = 60


# ---------------------------------------------------------------------------------------------
# Slugs
# ---------------------------------------------------------------------------------------------


def slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    if len(slug) < 3:
        slug = f"shop-{slug}".strip("-")
    return slug[:50].rstrip("-") or "shop"


def validate_slug(slug: str) -> str:
    candidate = slug.strip().lower()
    if not SLUG_PATTERN.fullmatch(candidate) or len(candidate) < 3:
        raise AppError(
            422,
            "SLUG_INVALID",
            "A storefront address is 3–50 lowercase letters, digits or hyphens",
        )
    if candidate in RESERVED_SLUGS:
        raise AppError(409, "SLUG_RESERVED", "This storefront address is reserved")
    return candidate


def _slug_taken(db: Session, slug: str, *, except_tenant: UUID | None = None) -> bool:
    query = select(Tenant.id).where(Tenant.slug == slug)
    if except_tenant is not None:
        query = query.where(Tenant.id != except_tenant)
    if db.scalar(query) is not None:
        return True
    return _redirect_owner(db, slug) not in (None, except_tenant)


def unique_slug(db: Session, name: str) -> str:
    base = slugify(name)
    if base in RESERVED_SLUGS:
        base = f"{base}-shop"
    candidate = base
    suffix = 2
    while _slug_taken(db, candidate):
        tail = f"-{suffix}"
        candidate = f"{base[: 50 - len(tail)]}{tail}"
        suffix += 1
    return candidate


def _redirect_owner(db: Session, slug: str) -> UUID | None:
    db.execute(text("SELECT set_config('app.public_slug', :slug, true)"), {"slug": slug})
    return db.scalar(select(TenantSlugRedirect.tenant_id).where(TenantSlugRedirect.slug == slug))


def resolve_slug(db: Session, slug: str) -> SlugResolution:
    """Current slug → the business; a previous slug → a redirect target (D-047)."""
    candidate = slug.strip().lower()
    tenant = db.scalar(select(Tenant).where(Tenant.slug == candidate))
    if tenant is None:
        owner = _redirect_owner(db, candidate)
        if owner is not None:
            tenant = db.get(Tenant, owner)
            if tenant is not None:
                return SlugResolution(
                    tenant_id=tenant.id, slug=tenant.slug, redirected_from=candidate
                )
        raise AppError(404, "STOREFRONT_NOT_FOUND", "No storefront at this address")
    return SlugResolution(tenant_id=tenant.id, slug=tenant.slug, redirected_from=None)


def storefront_settings(db: Session, tenant: Tenant) -> StorefrontSettings:
    set_tenant_scope(db, tenant.id)
    previous = list(
        db.scalars(
            select(TenantSlugRedirect.slug)
            .where(TenantSlugRedirect.tenant_id == tenant.id)
            .order_by(TenantSlugRedirect.created_at.desc())
        )
    )
    published = db.scalar(
        select(func.count())
        .select_from(TenantProduct)
        .where(TenantProduct.tenant_id == tenant.id, TenantProduct.is_published.is_(True))
    )
    return StorefrontSettings(
        slug=tenant.slug,
        previous_slugs=previous,
        published_products=int(published or 0),
        accepting_orders=tenant.status is TenantStatus.ACTIVE,
        customer_access_policy=tenant.customer_access_policy,
        available_policies=["LINK"],
    )


def rename_slug(db: Session, tenant: Tenant, actor_id: UUID, new_slug: str) -> StorefrontSettings:
    """Audited rename; the previous address keeps redirecting (D-047)."""
    candidate = validate_slug(new_slug)
    if candidate == tenant.slug:
        return storefront_settings(db, tenant)
    if _slug_taken(db, candidate, except_tenant=tenant.id):
        raise AppError(409, "SLUG_TAKEN", "This storefront address is already in use")
    set_tenant_scope(db, tenant.id)
    previous = tenant.slug
    # Returning to an earlier address: that redirect row becomes the live slug again.
    old_redirect = db.get(TenantSlugRedirect, candidate)
    if old_redirect is not None:
        db.delete(old_redirect)
        db.flush()
    tenant.slug = candidate
    db.add(TenantSlugRedirect(slug=previous, tenant_id=tenant.id, renamed_by_user_id=actor_id))
    db.add(
        AuditEvent(
            tenant_id=tenant.id,
            actor_user_id=actor_id,
            action="STOREFRONT_SLUG_RENAMED",
            entity_type="tenant",
            entity_id=tenant.id,
            details={"from": previous, "to": candidate},
        )
    )
    db.commit()
    set_tenant_scope(db, tenant.id)
    return storefront_settings(db, tenant)


# ---------------------------------------------------------------------------------------------
# Public catalog
# ---------------------------------------------------------------------------------------------


def _public_tenant(db: Session, slug: str) -> tuple[Tenant, SlugResolution]:
    resolution = resolve_slug(db, slug)
    tenant = db.get(Tenant, resolution.tenant_id)
    if tenant is None or tenant.status is TenantStatus.CLOSED:
        raise AppError(404, "STOREFRONT_NOT_FOUND", "No storefront at this address")
    set_tenant_scope(db, tenant.id)
    return tenant, resolution


def _image(image: TenantProductImage | MasterProductImage, slug: str, kind: str) -> PublicImage:
    return PublicImage(
        id=image.id,
        url=f"/api/v1/public/{slug}/catalog/images/{kind}/{image.id}",
        width=image.width,
        height=image.height,
        alt_text=image.alt_text,
    )


def _images(db: Session, product: TenantProduct, slug: str) -> list[PublicImage]:
    own = list(
        db.scalars(
            select(TenantProductImage)
            .where(
                TenantProductImage.tenant_id == product.tenant_id,
                TenantProductImage.tenant_product_id == product.id,
            )
            .order_by(TenantProductImage.display_order, TenantProductImage.created_at)
        )
    )
    images = [_image(image, slug, "tenant") for image in own]
    if not images and product.master_product_id is not None:
        master = list(
            db.scalars(
                select(MasterProductImage)
                .where(MasterProductImage.master_product_id == product.master_product_id)
                .order_by(MasterProductImage.display_order, MasterProductImage.created_at)
            )
        )
        images = [_image(image, slug, "master") for image in master]
    return images


def _money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.0001')):f}"


def _product(
    db: Session,
    product: TenantProduct,
    slug: str,
    barcode: str | None,
    context: CustomerContext | None = None,
) -> PublicProduct:
    if context is not None and context.tenant_id == product.tenant_id:
        # D-071: the customer's *current* rule (explicit grade price → grade discount → public),
        # resolved through the customer identity; the grade itself is never exposed.
        resolved = resolve_product_pricing(db, product.tenant_id, product, context.grade)
        basis, piece_price, box_price = (
            resolved.basis_price,
            resolved.piece_price,
            resolved.box_price,
        )
        pricing = "personalized"
    else:
        basis = product.unit_price
        piece_price, box_price = derive_counterpart_prices(
            product.unit_price, product.price_basis, product.pieces_per_box
        )
        pricing = "public"
    return PublicProduct(
        id=product.id,
        category_id=product.category_id,
        name=product.name,
        name_ar=product.name_ar,
        barcode=barcode,
        currency=product.currency,
        price=_money(basis),
        pricing=pricing,
        price_basis=product.price_basis.value,
        packaging=PublicPackaging(
            pieces_per_box=product.pieces_per_box,
            piece_price=_money(piece_price),
            box_price=_money(box_price) if box_price is not None else None,
        ),
        images=_images(db, product, slug),
    )


def _published(tenant_id: UUID) -> Any:
    return (
        select(TenantProduct)
        .join(
            Category,
            (Category.id == TenantProduct.category_id) & (Category.tenant_id == tenant_id),
        )
        .where(
            TenantProduct.tenant_id == tenant_id,
            TenantProduct.is_published.is_(True),
            Category.is_active.is_(True),
        )
    )


def _primary_barcodes(db: Session, tenant_id: UUID, product_ids: list[UUID]) -> dict[UUID, str]:
    if not product_ids:
        return {}
    rows = db.execute(
        select(TenantBarcode.tenant_product_id, TenantBarcode.barcode)
        .where(
            TenantBarcode.tenant_id == tenant_id,
            TenantBarcode.tenant_product_id.in_(product_ids),
        )
        .order_by(TenantBarcode.tenant_product_id, TenantBarcode.created_at)
    ).all()
    first: dict[UUID, str] = {}
    for product_id, barcode in rows:
        first.setdefault(product_id, barcode)
    return first


def public_storefront(db: Session, slug: str) -> PublicStorefront:
    tenant, resolution = _public_tenant(db, slug)
    counts: dict[UUID, int] = {
        category_id: int(count)
        for category_id, count in db.execute(
            select(TenantProduct.category_id, func.count())
            .where(TenantProduct.tenant_id == tenant.id, TenantProduct.is_published.is_(True))
            .group_by(TenantProduct.category_id)
        ).all()
    }
    categories = [
        PublicCategory(
            id=category.id,
            name_en=category.name_en,
            name_ar=category.name_ar,
            slug=category.slug,
            product_count=int(counts.get(category.id, 0)),
        )
        for category in db.scalars(
            select(Category)
            .where(Category.tenant_id == tenant.id, Category.is_active.is_(True))
            .order_by(Category.display_order, Category.name_en)
        )
        if counts.get(category.id)
    ]
    return PublicStorefront(
        slug=tenant.slug,
        redirected_from=resolution.redirected_from,
        name=tenant.name,
        accepting_orders=tenant.status is TenantStatus.ACTIVE,
        categories=categories,
        published_products=sum(counts.values()),
        generated_at=datetime.now(UTC),
        branding=public_branding(db, tenant),
    )


def public_products(
    db: Session,
    slug: str,
    *,
    query: str | None,
    category_id: UUID | None,
    page: int,
    page_size: int,
    context: CustomerContext | None = None,
) -> PublicProductPage:
    """Deterministic, bounded listing: exact barcode/name first, then prefix, then contains."""
    tenant, _resolution = _public_tenant(db, slug)
    size = max(1, min(page_size, MAX_PAGE_SIZE))
    base = _published(tenant.id)
    if category_id is not None:
        base = base.where(TenantProduct.category_id == category_id)
    needle = (query or "").strip()
    if needle:
        lowered = needle.lower()
        barcode_match = select(TenantBarcode.tenant_product_id).where(
            TenantBarcode.tenant_id == tenant.id, TenantBarcode.barcode == needle
        )
        base = base.where(
            or_(
                TenantProduct.id.in_(barcode_match),
                func.lower(TenantProduct.name).contains(lowered),
                func.lower(func.coalesce(TenantProduct.name_ar, "")).contains(lowered),
            )
        )
    total = int(db.scalar(select(func.count()).select_from(base.subquery())) or 0)
    rows = list(db.scalars(base.order_by(TenantProduct.name, TenantProduct.id)))
    if needle:
        lowered = needle.lower()
        barcodes = _primary_barcodes(db, tenant.id, [row.id for row in rows])

        def rank_of(row: TenantProduct) -> tuple[int, str, str]:
            names = [row.name.lower(), (row.name_ar or "").lower()]
            if barcodes.get(row.id) == needle or lowered in names:
                order = 0
            elif any(name.startswith(lowered) for name in names):
                order = 1
            else:
                order = 2
            return (order, row.name.lower(), str(row.id))

        rows.sort(key=rank_of)
    start = (max(page, 1) - 1) * size
    window = rows[start : start + size]
    barcodes = _primary_barcodes(db, tenant.id, [row.id for row in window])
    return PublicProductPage(
        items=[_product(db, row, tenant.slug, barcodes.get(row.id), context) for row in window],
        page=max(page, 1),
        page_size=size,
        total=total,
        has_more=start + size < total,
    )


def public_product(
    db: Session, slug: str, product_id: UUID, context: CustomerContext | None = None
) -> PublicProduct:
    tenant, _resolution = _public_tenant(db, slug)
    product = db.scalar(_published(tenant.id).where(TenantProduct.id == product_id))
    if product is None:
        raise AppError(404, "PRODUCT_NOT_FOUND", "Product was not found")
    barcodes = _primary_barcodes(db, tenant.id, [product.id])
    return _product(db, product, tenant.slug, barcodes.get(product.id), context)


def public_image(db: Session, slug: str, kind: str, image_id: UUID) -> tuple[str, str] | None:
    """Return (object_key, content_type) only for an image of a published product."""
    tenant, _resolution = _public_tenant(db, slug)
    if kind == "tenant":
        image = db.scalar(
            select(TenantProductImage)
            .join(TenantProduct, TenantProduct.id == TenantProductImage.tenant_product_id)
            .where(
                TenantProductImage.id == image_id,
                TenantProductImage.tenant_id == tenant.id,
                TenantProduct.is_published.is_(True),
            )
        )
        return (image.object_key, image.content_type) if image else None
    if kind == "master":
        master = db.scalar(
            select(MasterProductImage)
            .join(
                TenantProduct,
                TenantProduct.master_product_id == MasterProductImage.master_product_id,
            )
            .where(
                MasterProductImage.id == image_id,
                TenantProduct.tenant_id == tenant.id,
                TenantProduct.is_published.is_(True),
            )
        )
        return (master.object_key, master.content_type) if master else None
    return None


def public_products_by_ids(
    db: Session, slug: str, product_ids: list[UUID], context: CustomerContext | None = None
) -> list[PublicProduct]:
    """Published products in the given order (featured/recommended lists)."""
    tenant, _resolution = _public_tenant(db, slug)
    if not product_ids:
        return []
    rows = {
        row.id: row
        for row in db.scalars(_published(tenant.id).where(TenantProduct.id.in_(product_ids)))
    }
    barcodes = _primary_barcodes(db, tenant.id, [pid for pid in product_ids if pid in rows])
    return [
        _product(db, rows[pid], tenant.slug, barcodes.get(pid), context)
        for pid in product_ids
        if pid in rows
    ]


def public_tenant_id(db: Session, slug: str) -> UUID:
    tenant, _resolution = _public_tenant(db, slug)
    return tenant.id
