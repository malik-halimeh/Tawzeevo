"""Owner-facing supplier and product-cost setup (D-041 on the D-034 cost foundation).

Suppliers, cost entries and preferred-supplier choices are tenant-private. Cost entries are
append-only and effective-dated; nothing here edits or deletes a historical entry. Phase 6 may
append entries automatically later without changing these rules.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    AuditEvent,
    CostSourceType,
    ProductPriceBasis,
    TenantProduct,
    TenantProductCostEntry,
    TenantSupplier,
)
from tawzeevo_api.phone import normalize_phone
from tawzeevo_api.repositories.tenancy import commit_and_restore_tenant_scope
from tawzeevo_api.schemas.suppliers import (
    ExcludedSupplier,
    PreferredSupplierRequest,
    ProductCostEntryCreateRequest,
    ProductCostEntryResponse,
    ProductCostSetupResponse,
    ProductPriceInsightsResponse,
    RankedSupplier,
    SupplierCreateRequest,
    SupplierListResponse,
    SupplierPriceInsight,
    SupplierRecommendationResponse,
    SupplierResponse,
    SupplierUpdateRequest,
)
from tawzeevo_api.services.cash_van import get_product
from tawzeevo_api.services.invoice_editor import money


def _supplier(db: Session, tenant_id: UUID, supplier_id: UUID) -> TenantSupplier:
    supplier = db.scalar(
        select(TenantSupplier).where(
            TenantSupplier.tenant_id == tenant_id, TenantSupplier.id == supplier_id
        )
    )
    if supplier is None:
        raise AppError(404, "SUPPLIER_NOT_FOUND", "Supplier was not found")
    return supplier


def _reject_duplicate_name(
    db: Session, tenant_id: UUID, name: str, *, exclude_id: UUID | None = None
) -> None:
    query = select(TenantSupplier.id).where(
        TenantSupplier.tenant_id == tenant_id,
        func.lower(TenantSupplier.name) == name.casefold(),
    )
    if exclude_id is not None:
        query = query.where(TenantSupplier.id != exclude_id)
    if db.scalar(query) is not None:
        raise AppError(409, "SUPPLIER_NAME_EXISTS", "A supplier with this name already exists")


def _audit(
    db: Session,
    tenant_id: UUID,
    actor: UUID,
    action: str,
    entity_type: str,
    entity_id: UUID,
    **details: object,
) -> None:
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details={key: str(value) for key, value in details.items()},
        )
    )


def list_suppliers(db: Session, tenant_id: UUID) -> SupplierListResponse:
    return SupplierListResponse(
        suppliers=[
            SupplierResponse.model_validate(row)
            for row in db.scalars(
                select(TenantSupplier)
                .where(TenantSupplier.tenant_id == tenant_id)
                .order_by(TenantSupplier.name.asc(), TenantSupplier.id.asc())
            )
        ]
    )


def create_supplier(
    db: Session, tenant_id: UUID, actor: UUID, request: SupplierCreateRequest
) -> SupplierResponse:
    name = request.name.strip()
    if not name:
        raise AppError(422, "SUPPLIER_NAME_REQUIRED", "Supplier name is required")
    _reject_duplicate_name(db, tenant_id, name)
    supplier = TenantSupplier(tenant_id=tenant_id, name=name)
    _apply_profile(supplier, request.model_dump(exclude={"name"}, exclude_unset=True))
    db.add(supplier)
    db.flush()
    _audit(db, tenant_id, actor, "supplier_created", "tenant_supplier", supplier.id, name=name)
    commit_and_restore_tenant_scope(db, tenant_id)
    db.refresh(supplier)
    return SupplierResponse.model_validate(supplier)


def update_supplier(
    db: Session, tenant_id: UUID, actor: UUID, supplier_id: UUID, request: SupplierUpdateRequest
) -> SupplierResponse:
    supplier = _supplier(db, tenant_id, supplier_id)
    if request.expected_version is not None and supplier.version != request.expected_version:
        raise AppError(
            409, "SUPPLIER_VERSION_CONFLICT", "Supplier was changed elsewhere; reload it"
        )
    values = request.model_dump(exclude={"expected_version"}, exclude_unset=True)
    changed: dict[str, object] = {}
    if "name" in values:
        name = (values.pop("name") or "").strip()
        if not name:
            raise AppError(422, "SUPPLIER_NAME_REQUIRED", "Supplier name is required")
        _reject_duplicate_name(db, tenant_id, name, exclude_id=supplier.id)
        if name != supplier.name:
            changed["previous_name"] = supplier.name
            changed["name"] = name
            supplier.name = name
    changed.update(_apply_profile(supplier, values))
    if changed:
        # A pure rename keeps the Phase 3 audit action; anything else is a profile update.
        action = (
            "supplier_renamed" if set(changed) <= {"previous_name", "name"} else "supplier_updated"
        )
        _audit(db, tenant_id, actor, action, "tenant_supplier", supplier.id, **changed)
    commit_and_restore_tenant_scope(db, tenant_id)
    db.refresh(supplier)
    return SupplierResponse.model_validate(supplier)


def _apply_profile(supplier: TenantSupplier, values: dict[str, object]) -> dict[str, object]:
    """Apply contact/address/location/notes fields; returns what actually changed for the audit."""
    changed: dict[str, object] = {}
    if "contact_phone" in values:
        raw = values.pop("contact_phone")
        normalized = normalize_phone(str(raw)) if raw else None
        if normalized != supplier.contact_phone:
            changed["contact_phone"] = normalized or ""
        supplier.contact_phone = normalized
        supplier.contact_phone_raw = str(raw) if raw else None
    for field_name, value in values.items():
        if getattr(supplier, field_name) != value:
            changed[field_name] = "" if value is None else value
            setattr(supplier, field_name, value)
    if (supplier.latitude is None) != (supplier.longitude is None):
        raise AppError(422, "COORDINATES_PAIRED", "Latitude and longitude must be given together")
    return changed


def _cost_setup(db: Session, tenant_id: UUID, product: TenantProduct) -> ProductCostSetupResponse:
    entries = db.scalars(
        select(TenantProductCostEntry)
        .where(
            TenantProductCostEntry.tenant_id == tenant_id,
            TenantProductCostEntry.tenant_product_id == product.id,
        )
        .order_by(
            TenantProductCostEntry.effective_at.desc(),
            TenantProductCostEntry.created_at.desc(),
            TenantProductCostEntry.id.desc(),
        )
    )
    return ProductCostSetupResponse(
        product_id=product.id,
        product_name=product.name,
        currency=product.currency,
        preferred_supplier_id=product.preferred_supplier_id,
        entries=[
            ProductCostEntryResponse.model_validate(entry).model_copy(
                update={"unit_cost": money(entry.unit_cost)}
            )
            for entry in entries
        ],
    )


def product_cost_setup(db: Session, tenant_id: UUID, product_id: UUID) -> ProductCostSetupResponse:
    return _cost_setup(db, tenant_id, get_product(db, tenant_id, product_id))


def append_cost_row(
    db: Session,
    tenant_id: UUID,
    actor: UUID,
    product_id: UUID,
    request: ProductCostEntryCreateRequest,
    entry_id: UUID | None = None,
) -> TenantProductCostEntry:
    """Validate and append one cost entry without committing (shared by the API and the sync
    push applier). `entry_id` lets an offline command name its own row so a replay is a no-op."""
    product = get_product(db, tenant_id, product_id)
    _supplier(db, tenant_id, request.supplier_id)
    if entry_id is not None and db.get(TenantProductCostEntry, entry_id) is not None:
        raise AppError(409, "ENTITY_ID_IN_USE", "Entity id already exists")
    if request.currency != product.currency:
        # D-034: no silent currency conversion; a cost must be in the product's currency.
        raise AppError(400, "CURRENCY_MISMATCH", "Cost currency must match the product currency")
    pieces_per_box = request.pieces_per_box or product.pieces_per_box
    if request.cost_basis is ProductPriceBasis.BOX and pieces_per_box is None:
        raise AppError(400, "COST_PIECES_PER_BOX_REQUIRED", "Box cost requires pieces per box")
    entry = TenantProductCostEntry(
        tenant_id=tenant_id,
        tenant_product_id=product.id,
        supplier_id=request.supplier_id,
        unit_cost=money(request.unit_cost),
        currency=request.currency,
        cost_basis=request.cost_basis,
        pieces_per_box=pieces_per_box
        if request.cost_basis is ProductPriceBasis.BOX
        else request.pieces_per_box,
        effective_at=request.effective_at or datetime.now(UTC),
        source_type=request.source_type.value,
        quantity_context=request.quantity_context,
        notes=request.notes.strip() if request.notes else None,
        created_by_user_id=actor,
    )
    if entry_id is not None:
        entry.id = entry_id
    db.add(entry)
    db.flush()
    if product.preferred_supplier_id is None:
        # First cost for a product makes its supplier the default so invoice entry preloads it.
        product.preferred_supplier_id = request.supplier_id
    return entry


def append_product_cost(
    db: Session,
    tenant_id: UUID,
    actor: UUID,
    product_id: UUID,
    request: ProductCostEntryCreateRequest,
) -> ProductCostSetupResponse:
    product = get_product(db, tenant_id, product_id)
    had_preferred = product.preferred_supplier_id is not None
    entry = append_cost_row(db, tenant_id, actor, product_id, request)
    _audit(
        db,
        tenant_id,
        actor,
        "product_cost_appended",
        "tenant_product_cost_entry",
        entry.id,
        product_id=product.id,
        supplier_id=request.supplier_id,
        unit_cost=money(request.unit_cost),
        currency=request.currency,
        cost_basis=request.cost_basis.value,
        source_type=request.source_type.value,
    )
    if not had_preferred and product.preferred_supplier_id == request.supplier_id:
        _audit(
            db,
            tenant_id,
            actor,
            "preferred_supplier_set",
            "tenant_product",
            product.id,
            supplier_id=request.supplier_id,
            reason="first_cost_entry",
        )
    commit_and_restore_tenant_scope(db, tenant_id)
    return _cost_setup(db, tenant_id, get_product(db, tenant_id, product_id))


def set_preferred_supplier(
    db: Session,
    tenant_id: UUID,
    actor: UUID,
    product_id: UUID,
    request: PreferredSupplierRequest,
) -> ProductCostSetupResponse:
    product = get_product(db, tenant_id, product_id)
    if request.supplier_id is not None:
        _supplier(db, tenant_id, request.supplier_id)
    product.preferred_supplier_id = request.supplier_id
    _audit(
        db,
        tenant_id,
        actor,
        "preferred_supplier_set",
        "tenant_product",
        product.id,
        supplier_id=request.supplier_id,
        reason=request.reason or "",
    )
    commit_and_restore_tenant_scope(db, tenant_id)
    return _cost_setup(db, tenant_id, get_product(db, tenant_id, product_id))


# ---------------------------------------------------------------------------------------------
# Derived price insights (PHASE_06.md C) — computed, never stored
# ---------------------------------------------------------------------------------------------

STALE_AFTER_DAYS = 90
RECENT_PRICES = 5
_PERCENT = Decimal("0.01")


def _variation_percent(values: list[Decimal]) -> Decimal | None:
    """Spread of the recent comparable prices as a percentage of their mean (0 = perfectly
    stable). Population standard deviation over at most RECENT_PRICES entries; None below two."""
    if len(values) < 2:
        return None
    mean = sum(values) / Decimal(len(values))
    if mean == 0:
        return Decimal("0.00")
    variance = sum((value - mean) ** 2 for value in values) / Decimal(len(values))
    deviation = variance.sqrt()
    return (deviation / mean * Decimal(100)).quantize(_PERCENT, rounding=ROUND_HALF_UP)


def _stability(variation: Decimal | None) -> str:
    if variation is None:
        return "INSUFFICIENT_DATA"
    if variation <= Decimal("2"):
        return "STABLE"
    if variation <= Decimal("10"):
        return "MODERATE"
    return "VOLATILE"


def product_price_insights(
    db: Session, tenant_id: UUID, product_id: UUID, now: datetime | None = None
) -> ProductPriceInsightsResponse:
    """Per supplier and comparable group: latest/lowest/highest, last actual purchase, recent
    trend, stability and price age. Groups with different currency, basis or pieces per box are
    never merged (no FX, no unit conversion); stale groups are reported, not hidden."""
    product = get_product(db, tenant_id, product_id)
    as_of = now or datetime.now(UTC)
    rows = list(
        db.scalars(
            select(TenantProductCostEntry)
            .where(
                TenantProductCostEntry.tenant_id == tenant_id,
                TenantProductCostEntry.tenant_product_id == product.id,
                TenantProductCostEntry.effective_at <= as_of,
            )
            .order_by(
                TenantProductCostEntry.effective_at.desc(),
                TenantProductCostEntry.created_at.desc(),
                TenantProductCostEntry.id.desc(),
            )
        )
    )
    names = {
        row.id: row.name
        for row in db.scalars(select(TenantSupplier).where(TenantSupplier.tenant_id == tenant_id))
    }
    groups: dict[tuple[UUID, str, ProductPriceBasis, int | None], list[TenantProductCostEntry]] = (
        defaultdict(list)
    )
    for row in rows:  # newest first within each group
        groups[(row.supplier_id, row.currency, row.cost_basis, row.pieces_per_box)].append(row)
    insights: list[SupplierPriceInsight] = []
    for (supplier_id, currency, basis, pieces), entries in groups.items():
        latest = entries[0]
        recent = [money(entry.unit_cost) for entry in entries[:RECENT_PRICES]]
        purchases = [e for e in entries if e.source_type == CostSourceType.ACTUAL_PURCHASE.value]
        variation = _variation_percent(recent)
        insights.append(
            SupplierPriceInsight(
                supplier_id=supplier_id,
                supplier_name=names.get(supplier_id, "?"),
                currency=currency,
                cost_basis=basis,
                pieces_per_box=pieces,
                latest_unit_cost=money(latest.unit_cost),
                latest_effective_at=latest.effective_at,
                latest_source_type=latest.source_type,
                latest_entry_id=latest.id,
                age_days=max(0, (as_of - latest.effective_at).days),
                lowest_unit_cost=min(money(e.unit_cost) for e in entries),
                highest_unit_cost=max(money(e.unit_cost) for e in entries),
                last_purchase_at=purchases[0].effective_at if purchases else None,
                last_purchase_unit_cost=money(purchases[0].unit_cost) if purchases else None,
                recent_unit_costs=recent,
                entry_count=len(entries),
                variation_percent=variation,
                stability=_stability(variation),
                is_preferred=product.preferred_supplier_id == supplier_id,
            )
        )
    insights.sort(
        key=lambda row: (
            row.currency,
            row.cost_basis.value,
            row.pieces_per_box or 0,
            row.latest_unit_cost,
            row.supplier_name,
            str(row.supplier_id),
        )
    )
    return ProductPriceInsightsResponse(
        product_id=product.id,
        product_name=product.name,
        currency=product.currency,
        preferred_supplier_id=product.preferred_supplier_id,
        as_of=as_of,
        stale_after_days=STALE_AFTER_DAYS,
        insights=insights,
    )


# ---------------------------------------------------------------------------------------------
# Deterministic comparable-supplier recommendation (PHASE_06.md D) — no AI, no FX
# ---------------------------------------------------------------------------------------------


def recommend_supplier(
    db: Session,
    tenant_id: UUID,
    product_id: UUID,
    cost_basis: ProductPriceBasis | None = None,
    pieces_per_box: int | None = None,
    now: datetime | None = None,
) -> SupplierRecommendationResponse:
    """Rank suppliers for one product inside one comparable group (the product's currency and
    the requested unit/package): the latest price per supplier, fresh prices before stale ones,
    lowest first, ties broken by newer price then supplier name then id, so two owners looking at
    the same history see the same order. Suppliers whose only prices are in another unit, another
    package size or another currency are listed as excluded with the reason, never ranked. The
    owner's preferred supplier overrides the recommendation and both are returned."""
    product = get_product(db, tenant_id, product_id)
    as_of = now or datetime.now(UTC)
    basis = cost_basis or product.price_basis
    pieces = pieces_per_box if pieces_per_box is not None else product.pieces_per_box
    if basis is ProductPriceBasis.PIECE:
        pieces = None
    rows = list(
        db.scalars(
            select(TenantProductCostEntry)
            .where(
                TenantProductCostEntry.tenant_id == tenant_id,
                TenantProductCostEntry.tenant_product_id == product.id,
                TenantProductCostEntry.effective_at <= as_of,
            )
            .order_by(
                TenantProductCostEntry.effective_at.desc(),
                TenantProductCostEntry.created_at.desc(),
                TenantProductCostEntry.id.desc(),
            )
        )
    )
    names = {
        row.id: row.name
        for row in db.scalars(select(TenantSupplier).where(TenantSupplier.tenant_id == tenant_id))
    }
    latest: dict[UUID, TenantProductCostEntry] = {}
    excluded: dict[UUID, ExcludedSupplier] = {}
    for row in rows:  # newest first: the first comparable row per supplier is its latest price
        if row.supplier_id in latest:
            continue
        if row.currency != product.currency:
            reason, detail = "DIFFERENT_CURRENCY", f"{row.currency} vs {product.currency}"
        elif row.cost_basis is not basis or (
            basis is ProductPriceBasis.BOX and row.pieces_per_box != pieces
        ):
            package = f" x{row.pieces_per_box}" if row.pieces_per_box else ""
            reason, detail = "INCOMPATIBLE_UNIT", f"{row.cost_basis.value}{package}"
        else:
            latest[row.supplier_id] = row
            excluded.pop(row.supplier_id, None)
            continue
        excluded.setdefault(
            row.supplier_id,
            ExcludedSupplier(
                supplier_id=row.supplier_id,
                supplier_name=names.get(row.supplier_id, "?"),
                reason=reason,
                detail=detail,
            ),
        )
    for supplier_id, name in names.items():
        if supplier_id not in latest and supplier_id not in excluded:
            excluded[supplier_id] = ExcludedSupplier(
                supplier_id=supplier_id, supplier_name=name, reason="NO_PRICE", detail=""
            )
    ordered = sorted(
        latest.values(),
        key=lambda row: (
            (as_of - row.effective_at).days >= STALE_AFTER_DAYS,
            money(row.unit_cost),
            -row.effective_at.timestamp(),
            names.get(row.supplier_id, ""),
            str(row.supplier_id),
        ),
    )
    best = money(ordered[0].unit_cost) if ordered else Decimal("0")
    ranked: list[RankedSupplier] = []
    for index, row in enumerate(ordered, start=1):
        age = max(0, (as_of - row.effective_at).days)
        stale = age >= STALE_AFTER_DAYS
        if index == 1:
            explanation = "LOWEST_COMPARABLE" if not stale else "LOWEST_BUT_STALE"
        elif stale:
            explanation = "STALE_RANKED_LAST"
        elif money(row.unit_cost) == best:
            explanation = "SAME_PRICE_OLDER"
        else:
            explanation = "HIGHER_PRICE"
        ranked.append(
            RankedSupplier(
                rank=index,
                supplier_id=row.supplier_id,
                supplier_name=names.get(row.supplier_id, "?"),
                unit_cost=money(row.unit_cost),
                effective_at=row.effective_at,
                age_days=age,
                is_stale=stale,
                source_type=row.source_type,
                entry_id=row.id,
                quantity_context=row.quantity_context,
                delta_vs_best=money(row.unit_cost) - best,
                explanation=explanation,
            )
        )
    recommended = ranked[0].supplier_id if ranked else None
    preferred = product.preferred_supplier_id
    if preferred is not None:
        effective, reason = preferred, "OWNER_OVERRIDE"
        if preferred == recommended:
            reason = "OWNER_CHOICE_MATCHES_RECOMMENDATION"
    elif recommended is not None:
        effective, reason = recommended, "LOWEST_COMPARABLE"
    else:
        effective, reason = None, "NO_COMPARABLE_PRICE"
    return SupplierRecommendationResponse(
        product_id=product.id,
        product_name=product.name,
        currency=product.currency,
        cost_basis=basis,
        pieces_per_box=pieces,
        as_of=as_of,
        stale_after_days=STALE_AFTER_DAYS,
        recommended_supplier_id=recommended,
        preferred_supplier_id=preferred,
        effective_supplier_id=effective,
        effective_reason=reason,
        ranked=ranked,
        excluded=sorted(
            excluded.values(), key=lambda row: (row.supplier_name, str(row.supplier_id))
        ),
    )
