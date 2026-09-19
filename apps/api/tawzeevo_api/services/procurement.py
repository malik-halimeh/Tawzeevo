"""Demand-driven procurement (PHASE_06.md A/E/F; D-058).

A procurement list is a purchasing to-do built from *confirmed* customer demand in a date
range: the current revision lines of CONFIRMED invoices confirmed inside the range, grouped by
product and unit. Every line keeps three distinct quantities — required (demand), target
(owner-adjusted) and purchased (written by supplier purchases in P6-M4) — and remaining is
derived. Nothing here is stock: no on-hand, reserved or availability value exists.

Lifecycle (D-058): OPEN → PARTIALLY_PURCHASED → COMPLETE / CANCELLED. Completion requires every
line to be fully purchased, waived with a reason, carried forward or removed with a reason, so
nothing is dropped silently. Carry-forward creates a new OPEN list holding the remaining
quantities and links both lines.

The assignee is any active membership of the business (owner or driver), so a sole owner can
self-assign. The runner projection carries supplier identity/location and quantities only.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, time
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    AuditEvent,
    Invoice,
    InvoiceRevisionItem,
    InvoiceStatus,
    ProcurementItem,
    ProcurementItemOrigin,
    ProcurementList,
    ProcurementStatus,
    ProductPriceBasis,
    TenantMembership,
    TenantProduct,
    TenantProductCostEntry,
    TenantSupplier,
    User,
)
from tawzeevo_api.repositories.tenancy import commit_and_restore_tenant_scope, set_tenant_scope
from tawzeevo_api.schemas.procurement import (
    AssigneeResponse,
    CarryForwardRequest,
    Estimate,
    GenerateListRequest,
    ItemUpdateRequest,
    ManualItemRequest,
    PickupItem,
    PickupList,
    PickupResponse,
    PickupSupplier,
    ProcurementItemResponse,
    ProcurementListResponse,
    ProcurementListSummary,
)
from tawzeevo_api.services.cash_van import get_product
from tawzeevo_api.services.invoice_editor import money
from tawzeevo_api.services.suppliers import STALE_AFTER_DAYS

TENANT_TZ = ZoneInfo("Asia/Beirut")
TERMINAL = {ProcurementStatus.COMPLETE.value, ProcurementStatus.CANCELLED.value}


def _audit(
    db: Session,
    tenant_id: UUID,
    actor: UUID | None,
    action: str,
    entity: str,
    entity_id: UUID,
    **details: object,
) -> None:
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor,
            action=action,
            entity_type=entity,
            entity_id=entity_id,
            details={key: str(value) for key, value in details.items()},
        )
    )


def _range_utc(day_from: date, day_to: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day_from, time.min, tzinfo=TENANT_TZ).astimezone(UTC)
    end = datetime.combine(day_to, time.max, tzinfo=TENANT_TZ).astimezone(UTC)
    return start, end


def get_list(db: Session, tenant_id: UUID, list_id: UUID) -> ProcurementList:
    set_tenant_scope(db, tenant_id)
    row = db.get(ProcurementList, list_id)
    if row is None or row.tenant_id != tenant_id:
        raise AppError(404, "PROCUREMENT_LIST_NOT_FOUND", "Procurement list was not found")
    return row


def _item(db: Session, tenant_id: UUID, list_id: UUID, item_id: UUID) -> ProcurementItem:
    row = db.get(ProcurementItem, item_id)
    if row is None or row.tenant_id != tenant_id or row.list_id != list_id:
        raise AppError(404, "PROCUREMENT_ITEM_NOT_FOUND", "Procurement line was not found")
    return row


def _items(db: Session, tenant_id: UUID, list_id: UUID) -> list[ProcurementItem]:
    return list(
        db.scalars(
            select(ProcurementItem)
            .where(ProcurementItem.tenant_id == tenant_id, ProcurementItem.list_id == list_id)
            .order_by(ProcurementItem.product_name.asc(), ProcurementItem.created_at.asc())
        )
    )


def _require_editable(row: ProcurementList) -> None:
    if row.status in TERMINAL:
        raise AppError(409, "PROCUREMENT_LIST_CLOSED", "A complete or cancelled list cannot change")


def _line_is_settled(item: ProcurementItem) -> bool:
    return (
        item.removed_at is not None
        or item.waived_at is not None
        or item.carried_to_item_id is not None
        or item.remaining_quantity == 0
    )


def refresh_status(db: Session, row: ProcurementList) -> None:
    """OPEN ↔ PARTIALLY_PURCHASED follow the purchased quantities; COMPLETE is an owner act
    (or automatic once every active line is fully purchased)."""
    if row.status in TERMINAL:
        return
    items = [i for i in _items(db, row.tenant_id, row.id) if i.removed_at is None]
    active = [i for i in items if i.waived_at is None and i.carried_to_item_id is None]
    purchased_any = any(i.purchased_quantity > 0 for i in items)
    if active and all(i.remaining_quantity == 0 for i in active) and purchased_any:
        row.status = ProcurementStatus.COMPLETE.value
        row.completed_at = datetime.now(UTC)
    elif purchased_any:
        row.status = ProcurementStatus.PARTIALLY_PURCHASED.value
    else:
        row.status = ProcurementStatus.OPEN.value


# ---------------------------------------------------------------------------------------------
# Demand aggregation and list creation
# ---------------------------------------------------------------------------------------------


def confirmed_demand(
    db: Session, tenant_id: UUID, day_from: date, day_to: date
) -> dict[tuple[UUID, ProductPriceBasis, int | None], tuple[Decimal, int, str]]:
    """Sum of current-revision quantities of CONFIRMED invoices confirmed in the range, grouped
    by product and unit/package. Cancelled invoices never count; drafts never count."""
    start, end = _range_utc(day_from, day_to)
    rows = db.execute(
        select(
            InvoiceRevisionItem.tenant_product_id,
            InvoiceRevisionItem.price_basis,
            InvoiceRevisionItem.pieces_per_box,
            InvoiceRevisionItem.quantity,
            InvoiceRevisionItem.product_name,
            Invoice.id,
        )
        .join(Invoice, Invoice.current_revision_id == InvoiceRevisionItem.invoice_revision_id)
        .where(
            Invoice.tenant_id == tenant_id,
            InvoiceRevisionItem.tenant_id == tenant_id,
            Invoice.status == InvoiceStatus.CONFIRMED,
            Invoice.confirmed_at >= start,
            Invoice.confirmed_at <= end,
            InvoiceRevisionItem.tenant_product_id.is_not(None),
        )
    ).all()
    totals: dict[tuple[UUID, ProductPriceBasis, int | None], Decimal] = defaultdict(Decimal)
    invoices: dict[tuple[UUID, ProductPriceBasis, int | None], set[UUID]] = defaultdict(set)
    names: dict[tuple[UUID, ProductPriceBasis, int | None], str] = {}
    for product_id, basis, pieces, quantity, name, invoice_id in rows:
        key = (product_id, basis, pieces if basis is ProductPriceBasis.BOX else None)
        totals[key] += Decimal(quantity)
        invoices[key].add(invoice_id)
        names[key] = name
    return {key: (totals[key], len(invoices[key]), names[key]) for key in totals}


def generate_list(
    db: Session, tenant_id: UUID, actor: UUID, request: GenerateListRequest
) -> ProcurementList:
    if request.demand_from > request.demand_to:
        raise AppError(422, "DEMAND_RANGE_INVALID", "demand_from must not be after demand_to")
    demand = confirmed_demand(db, tenant_id, request.demand_from, request.demand_to)
    if not demand and not request.include_empty:
        raise AppError(409, "NO_CONFIRMED_DEMAND", "No confirmed demand in that range")
    title = (
        request.title
        or f"Procurement {request.demand_from.isoformat()} → {request.demand_to.isoformat()}"
    )
    row = ProcurementList(
        tenant_id=tenant_id,
        title=title,
        demand_from=request.demand_from,
        demand_to=request.demand_to,
        notes=request.notes,
        created_by_user_id=actor,
    )
    db.add(row)
    db.flush()
    products = {
        p.id: p
        for p in db.scalars(
            select(TenantProduct).where(
                TenantProduct.tenant_id == tenant_id,
                TenantProduct.id.in_([key[0] for key in demand]),
            )
        )
    }
    for (product_id, basis, pieces), (quantity, invoice_count, name) in sorted(
        demand.items(), key=lambda kv: (kv[1][2], str(kv[0][0]), kv[0][1].value)
    ):
        product = products.get(product_id)
        db.add(
            ProcurementItem(
                tenant_id=tenant_id,
                list_id=row.id,
                tenant_product_id=product_id,
                product_name=product.name if product else name,
                supplier_id=product.preferred_supplier_id if product else None,
                price_basis=basis,
                pieces_per_box=pieces,
                origin=ProcurementItemOrigin.DEMAND.value,
                required_quantity=quantity,
                target_quantity=quantity,
                demand_invoice_count=invoice_count,
            )
        )
    _audit(
        db,
        tenant_id,
        actor,
        "procurement_list_generated",
        "procurement_list",
        row.id,
        demand_from=request.demand_from,
        demand_to=request.demand_to,
        lines=len(demand),
    )
    commit_and_restore_tenant_scope(db, tenant_id)
    return get_list(db, tenant_id, row.id)


def list_lists(db: Session, tenant_id: UUID, status: str | None = None) -> list[ProcurementList]:
    set_tenant_scope(db, tenant_id)
    query = select(ProcurementList).where(ProcurementList.tenant_id == tenant_id)
    if status:
        query = query.where(ProcurementList.status == status)
    return list(db.scalars(query.order_by(ProcurementList.created_at.desc()).limit(200)))


# ---------------------------------------------------------------------------------------------
# Owner edits
# ---------------------------------------------------------------------------------------------


def add_manual_item(
    db: Session, tenant_id: UUID, actor: UUID, list_id: UUID, request: ManualItemRequest
) -> ProcurementList:
    row = get_list(db, tenant_id, list_id)
    _require_editable(row)
    product = get_product(db, tenant_id, request.product_id)
    if request.supplier_id is not None:
        _supplier(db, tenant_id, request.supplier_id)
    basis = request.price_basis or product.price_basis
    item = ProcurementItem(
        tenant_id=tenant_id,
        list_id=row.id,
        tenant_product_id=product.id,
        product_name=product.name,
        supplier_id=request.supplier_id or product.preferred_supplier_id,
        price_basis=basis,
        pieces_per_box=product.pieces_per_box if basis is ProductPriceBasis.BOX else None,
        origin=ProcurementItemOrigin.MANUAL.value,
        required_quantity=Decimal("0"),
        target_quantity=request.target_quantity,
        notes=request.notes,
    )
    db.add(item)
    db.flush()
    _audit(
        db,
        tenant_id,
        actor,
        "procurement_item_added",
        "procurement_item",
        item.id,
        product_id=product.id,
        target=request.target_quantity,
    )
    refresh_status(db, row)
    commit_and_restore_tenant_scope(db, tenant_id)
    return get_list(db, tenant_id, list_id)


def _supplier(db: Session, tenant_id: UUID, supplier_id: UUID) -> TenantSupplier:
    supplier = db.get(TenantSupplier, supplier_id)
    if supplier is None or supplier.tenant_id != tenant_id:
        raise AppError(404, "SUPPLIER_NOT_FOUND", "Supplier was not found")
    return supplier


def update_item(
    db: Session,
    tenant_id: UUID,
    actor: UUID,
    list_id: UUID,
    item_id: UUID,
    request: ItemUpdateRequest,
) -> ProcurementList:
    row = get_list(db, tenant_id, list_id)
    _require_editable(row)
    item = _item(db, tenant_id, list_id, item_id)
    if item.removed_at is not None or item.carried_to_item_id is not None:
        raise AppError(409, "PROCUREMENT_ITEM_CLOSED", "This line can no longer be edited")
    if item.version != request.expected_version:
        raise AppError(
            409, "PROCUREMENT_ITEM_VERSION_CONFLICT", "Line was changed elsewhere; reload"
        )
    changed = apply_item_update(db, tenant_id, item, request)
    if changed:
        _audit(
            db, tenant_id, actor, "procurement_item_updated", "procurement_item", item.id, **changed
        )
    refresh_status(db, row)
    commit_and_restore_tenant_scope(db, tenant_id)
    return get_list(db, tenant_id, list_id)


def apply_item_update(
    db: Session, tenant_id: UUID, item: ProcurementItem, request: ItemUpdateRequest
) -> dict[str, object]:
    """Field-level edit shared by the API and the sync push applier; no commit here."""
    changed: dict[str, object] = {}
    if request.target_quantity is not None and request.target_quantity != item.target_quantity:
        if request.target_quantity < item.purchased_quantity:
            raise AppError(
                422, "TARGET_BELOW_PURCHASED", "Target cannot be below the purchased quantity"
            )
        changed["target_quantity"] = f"{item.target_quantity:f}→{request.target_quantity:f}"
        item.target_quantity = money(request.target_quantity)  # required stays as demand history
    if request.clear_supplier:
        changed["supplier_id"] = ""
        item.supplier_id = None
    elif request.supplier_id is not None and request.supplier_id != item.supplier_id:
        _supplier(db, tenant_id, request.supplier_id)
        changed["supplier_id"] = request.supplier_id
        item.supplier_id = request.supplier_id
    if request.notes is not None and request.notes != item.notes:
        changed["notes"] = request.notes
        item.notes = request.notes
    if changed:
        item.version += 1
    return changed


def remove_item(
    db: Session, tenant_id: UUID, actor: UUID, list_id: UUID, item_id: UUID, reason: str
) -> ProcurementList:
    """Soft removal: the line and its demand history stay readable with the reason."""
    row = get_list(db, tenant_id, list_id)
    _require_editable(row)
    item = _item(db, tenant_id, list_id, item_id)
    if item.purchased_quantity > 0:
        raise AppError(
            409,
            "PROCUREMENT_ITEM_HAS_PURCHASES",
            "A line with purchases cannot be removed; waive the rest instead",
        )
    if item.removed_at is None:
        item.removed_at = datetime.now(UTC)
        item.remove_reason = reason
        item.version += 1
        _audit(
            db,
            tenant_id,
            actor,
            "procurement_item_removed",
            "procurement_item",
            item.id,
            reason=reason,
        )
    refresh_status(db, row)
    commit_and_restore_tenant_scope(db, tenant_id)
    return get_list(db, tenant_id, list_id)


def waive_item(
    db: Session, tenant_id: UUID, actor: UUID, list_id: UUID, item_id: UUID, reason: str
) -> ProcurementList:
    """D-058: the owner may waive the remaining quantity with a reason; nothing is dropped
    silently."""
    row = get_list(db, tenant_id, list_id)
    _require_editable(row)
    item = _item(db, tenant_id, list_id, item_id)
    if item.removed_at is not None or item.carried_to_item_id is not None:
        raise AppError(409, "PROCUREMENT_ITEM_CLOSED", "This line can no longer be waived")
    if item.waived_at is None:
        item.waived_at = datetime.now(UTC)
        item.waive_reason = reason
        item.version += 1
        _audit(
            db,
            tenant_id,
            actor,
            "procurement_item_waived",
            "procurement_item",
            item.id,
            reason=reason,
            remaining=item.remaining_quantity,
        )
    refresh_status(db, row)
    commit_and_restore_tenant_scope(db, tenant_id)
    return get_list(db, tenant_id, list_id)


def set_assignee(
    db: Session, tenant_id: UUID, actor: UUID, list_id: UUID, membership_id: UUID | None
) -> ProcurementList:
    """Neutral assignee semantics (PHASE_06.md F): any active owner or driver membership."""
    row = get_list(db, tenant_id, list_id)
    _require_editable(row)
    if membership_id is not None:
        membership = db.get(TenantMembership, membership_id)
        if membership is None or membership.tenant_id != tenant_id or not membership.is_active:
            raise AppError(
                404, "ASSIGNEE_NOT_FOUND", "Assignee must be an active member of this business"
            )
    if row.assignee_membership_id != membership_id:
        row.assignee_membership_id = membership_id
        row.version += 1
        _audit(
            db,
            tenant_id,
            actor,
            "procurement_list_assigned",
            "procurement_list",
            row.id,
            membership_id=membership_id or "",
        )
    commit_and_restore_tenant_scope(db, tenant_id)
    return get_list(db, tenant_id, list_id)


def complete_list(db: Session, tenant_id: UUID, actor: UUID, list_id: UUID) -> ProcurementList:
    row = get_list(db, tenant_id, list_id)
    _require_editable(row)
    unsettled = [i for i in _items(db, tenant_id, list_id) if not _line_is_settled(i)]
    if unsettled:
        raise AppError(
            409,
            "PROCUREMENT_LINES_OPEN",
            f"{len(unsettled)} line(s) still have remaining quantity: purchase, waive with a "
            "reason or carry them forward",
        )
    row.status = ProcurementStatus.COMPLETE.value
    row.completed_at = datetime.now(UTC)
    row.version += 1
    _audit(db, tenant_id, actor, "procurement_list_completed", "procurement_list", row.id)
    commit_and_restore_tenant_scope(db, tenant_id)
    return get_list(db, tenant_id, list_id)


def cancel_list(
    db: Session, tenant_id: UUID, actor: UUID, list_id: UUID, reason: str
) -> ProcurementList:
    row = get_list(db, tenant_id, list_id)
    _require_editable(row)
    if any(i.purchased_quantity > 0 for i in _items(db, tenant_id, list_id)):
        raise AppError(
            409,
            "PROCUREMENT_LIST_HAS_PURCHASES",
            "A list with recorded purchases cannot be cancelled; complete it instead",
        )
    row.status = ProcurementStatus.CANCELLED.value
    row.cancelled_at = datetime.now(UTC)
    row.cancel_reason = reason
    row.version += 1
    _audit(
        db,
        tenant_id,
        actor,
        "procurement_list_cancelled",
        "procurement_list",
        row.id,
        reason=reason,
    )
    commit_and_restore_tenant_scope(db, tenant_id)
    return get_list(db, tenant_id, list_id)


def carry_forward(
    db: Session, tenant_id: UUID, actor: UUID, list_id: UUID, request: CarryForwardRequest
) -> ProcurementList:
    """Move every open remaining quantity into a new OPEN list; both lines stay linked (D-058)."""
    source = get_list(db, tenant_id, list_id)
    _require_editable(source)
    open_items = [i for i in _items(db, tenant_id, list_id) if not _line_is_settled(i)]
    if not open_items:
        raise AppError(409, "NOTHING_TO_CARRY", "Every line is already settled")
    target = ProcurementList(
        tenant_id=tenant_id,
        title=request.title or f"{source.title} (carried forward)",
        demand_from=source.demand_from,
        demand_to=source.demand_to,
        carried_from_list_id=source.id,
        assignee_membership_id=source.assignee_membership_id,
        created_by_user_id=actor,
    )
    db.add(target)
    db.flush()
    for item in open_items:
        carried = ProcurementItem(
            tenant_id=tenant_id,
            list_id=target.id,
            tenant_product_id=item.tenant_product_id,
            product_name=item.product_name,
            supplier_id=item.supplier_id,
            price_basis=item.price_basis,
            pieces_per_box=item.pieces_per_box,
            origin=ProcurementItemOrigin.CARRY_FORWARD.value,
            required_quantity=item.remaining_quantity,
            target_quantity=item.remaining_quantity,
            carried_from_item_id=item.id,
            notes=item.notes,
        )
        db.add(carried)
        db.flush()
        item.carried_to_item_id = carried.id
        item.version += 1
    _audit(
        db,
        tenant_id,
        actor,
        "procurement_list_carried_forward",
        "procurement_list",
        source.id,
        target_list_id=target.id,
        lines=len(open_items),
    )
    if request.complete_source:
        source.status = ProcurementStatus.COMPLETE.value
        source.completed_at = datetime.now(UTC)
        source.version += 1
    commit_and_restore_tenant_scope(db, tenant_id)
    return get_list(db, tenant_id, target.id)


# ---------------------------------------------------------------------------------------------
# Projections
# ---------------------------------------------------------------------------------------------


def _assignee(
    db: Session, tenant_id: UUID, membership_id: UUID | None, viewer_membership_id: UUID | None
) -> AssigneeResponse | None:
    if membership_id is None:
        return None
    membership = db.get(TenantMembership, membership_id)
    if membership is None:
        return None
    user = db.get(User, membership.user_id)
    return AssigneeResponse(
        membership_id=membership.id,
        role=membership.role.value,
        display_name=f"{user.first_name} {user.last_name}".strip() if user else "?",
        is_self=membership.id == viewer_membership_id,
    )


def list_assignees(
    db: Session, tenant_id: UUID, viewer_membership_id: UUID
) -> list[AssigneeResponse]:
    set_tenant_scope(db, tenant_id)
    rows = db.scalars(
        select(TenantMembership).where(
            TenantMembership.tenant_id == tenant_id, TenantMembership.is_active.is_(True)
        )
    )
    out = [_assignee(db, tenant_id, row.id, viewer_membership_id) for row in rows]
    return sorted(
        [row for row in out if row], key=lambda r: (not r.is_self, r.role, r.display_name)
    )


def _latest_comparable(
    db: Session,
    tenant_id: UUID,
    product_id: UUID,
    supplier_id: UUID,
    basis: ProductPriceBasis,
    pieces: int | None,
    currency: str,
    now: datetime,
) -> TenantProductCostEntry | None:
    query = (
        select(TenantProductCostEntry)
        .where(
            TenantProductCostEntry.tenant_id == tenant_id,
            TenantProductCostEntry.tenant_product_id == product_id,
            TenantProductCostEntry.supplier_id == supplier_id,
            TenantProductCostEntry.currency == currency,
            TenantProductCostEntry.cost_basis == basis,
            TenantProductCostEntry.effective_at <= now,
        )
        .order_by(
            TenantProductCostEntry.effective_at.desc(), TenantProductCostEntry.created_at.desc()
        )
        .limit(1)
    )
    if basis is ProductPriceBasis.BOX:
        query = query.where(TenantProductCostEntry.pieces_per_box == pieces)
    return db.scalar(query)


def _estimate(
    db: Session,
    tenant_id: UUID,
    item: ProcurementItem,
    product: TenantProduct | None,
    names: dict[UUID, str],
    now: datetime,
) -> Estimate | None:
    """Estimate = latest comparable price of the chosen supplier (or, if none chosen, the
    cheapest comparable supplier) × remaining quantity. Labelled, never booked anywhere."""
    if product is None or item.remaining_quantity == 0:
        return None
    candidates = [item.supplier_id] if item.supplier_id else list(names)
    best: tuple[TenantProductCostEntry, bool] | None = None
    for supplier_id in candidates:
        entry = _latest_comparable(
            db,
            tenant_id,
            product.id,
            supplier_id,
            item.price_basis,
            item.pieces_per_box,
            product.currency,
            now,
        )
        if entry is None:
            continue
        stale = (now - entry.effective_at).days >= STALE_AFTER_DAYS
        if best is None or (stale, money(entry.unit_cost)) < (
            (now - best[0].effective_at).days >= STALE_AFTER_DAYS,
            money(best[0].unit_cost),
        ):
            best = (entry, item.supplier_id is None)
    if best is None:
        return None
    entry, recommended = best
    return Estimate(
        supplier_id=entry.supplier_id,
        supplier_name=names.get(entry.supplier_id, "?"),
        unit_cost=money(entry.unit_cost),
        currency=entry.currency,
        effective_at=entry.effective_at,
        age_days=max(0, (now - entry.effective_at).days),
        is_stale=(now - entry.effective_at).days >= STALE_AFTER_DAYS,
        source_type=entry.source_type,
        remaining_cost=money(money(entry.unit_cost) * item.remaining_quantity),
        supplier_is_recommended=recommended,
    )


def list_response(
    db: Session,
    tenant_id: UUID,
    row: ProcurementList,
    viewer_membership_id: UUID | None,
    now: datetime | None = None,
) -> ProcurementListResponse:
    as_of = now or datetime.now(UTC)
    items = _items(db, tenant_id, row.id)
    names = {
        s.id: s.name
        for s in db.scalars(select(TenantSupplier).where(TenantSupplier.tenant_id == tenant_id))
    }
    products = (
        {
            p.id: p
            for p in db.scalars(
                select(TenantProduct).where(
                    TenantProduct.tenant_id == tenant_id,
                    TenantProduct.id.in_([i.tenant_product_id for i in items]),
                )
            )
        }
        if items
        else {}
    )
    totals: dict[str, Decimal] = defaultdict(Decimal)
    responses: list[ProcurementItemResponse] = []
    for item in items:
        estimate = (
            _estimate(db, tenant_id, item, products.get(item.tenant_product_id), names, as_of)
            if _line_is_settled(item) is False
            else None
        )
        if estimate:
            totals[estimate.currency] += estimate.remaining_cost
        responses.append(
            ProcurementItemResponse(
                id=item.id,
                list_id=item.list_id,
                product_id=item.tenant_product_id,
                product_name=item.product_name,
                supplier_id=item.supplier_id,
                supplier_name=names.get(item.supplier_id) if item.supplier_id else None,
                price_basis=item.price_basis,
                pieces_per_box=item.pieces_per_box,
                origin=item.origin,
                required_quantity=item.required_quantity,
                target_quantity=item.target_quantity,
                purchased_quantity=item.purchased_quantity,
                remaining_quantity=item.remaining_quantity,
                demand_invoice_count=item.demand_invoice_count,
                removed_at=item.removed_at,
                remove_reason=item.remove_reason,
                waived_at=item.waived_at,
                waive_reason=item.waive_reason,
                carried_from_item_id=item.carried_from_item_id,
                carried_to_item_id=item.carried_to_item_id,
                notes=item.notes,
                version=item.version,
                estimate=estimate,
            )
        )
    return ProcurementListResponse(
        id=row.id,
        status=row.status,
        title=row.title,
        demand_from=row.demand_from,
        demand_to=row.demand_to,
        notes=row.notes,
        assignee=_assignee(db, tenant_id, row.assignee_membership_id, viewer_membership_id),
        carried_from_list_id=row.carried_from_list_id,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
        completed_at=row.completed_at,
        cancelled_at=row.cancelled_at,
        cancel_reason=row.cancel_reason,
        items=responses,
        estimated_totals={currency: money(total) for currency, total in sorted(totals.items())},
        open_line_count=sum(1 for i in items if not _line_is_settled(i)),
    )


def summaries(
    db: Session, tenant_id: UUID, rows: list[ProcurementList], viewer_membership_id: UUID | None
) -> list[ProcurementListSummary]:
    out = []
    for row in rows:
        items = _items(db, tenant_id, row.id)
        out.append(
            ProcurementListSummary(
                id=row.id,
                status=row.status,
                title=row.title,
                demand_from=row.demand_from,
                demand_to=row.demand_to,
                assignee=_assignee(db, tenant_id, row.assignee_membership_id, viewer_membership_id),
                created_at=row.created_at,
                line_count=sum(1 for i in items if i.removed_at is None),
                open_line_count=sum(1 for i in items if not _line_is_settled(i)),
            )
        )
    return out


def export_csv(
    db: Session, tenant_id: UUID, row: ProcurementList, viewer_membership_id: UUID | None
) -> str:
    """Printable export for the owner. Demand and progress columns only, plus the labelled
    estimate; no stock or availability column exists to export."""
    response = list_response(db, tenant_id, row, viewer_membership_id)
    lines = [
        "product,supplier,unit,required,target,purchased,remaining,state,estimate_unit_cost,estimate_currency"
    ]
    for item in response.items:
        state = (
            "removed"
            if item.removed_at
            else "waived"
            if item.waived_at
            else "carried_forward"
            if item.carried_to_item_id
            else "open"
        )
        unit = item.price_basis.value + (f" x{item.pieces_per_box}" if item.pieces_per_box else "")
        cells = [
            item.product_name.replace(",", " "),
            (item.supplier_name or "").replace(",", " "),
            unit,
            f"{item.required_quantity:f}",
            f"{item.target_quantity:f}",
            f"{item.purchased_quantity:f}",
            f"{item.remaining_quantity:f}",
            state,
            f"{item.estimate.unit_cost:f}" if item.estimate else "",
            item.estimate.currency if item.estimate else "",
        ]
        lines.append(",".join(cells))
    return "\n".join(lines) + "\n"


def my_pickups(db: Session, tenant_id: UUID, membership_id: UUID) -> PickupResponse:
    """Runner projection (PHASE_06.md F): the lists assigned to the caller, grouped by supplier
    with identity and location, remaining quantities only. No price, cost, estimate or margin."""
    set_tenant_scope(db, tenant_id)
    rows = db.scalars(
        select(ProcurementList)
        .where(
            ProcurementList.tenant_id == tenant_id,
            ProcurementList.assignee_membership_id == membership_id,
            ProcurementList.status.in_(
                [ProcurementStatus.OPEN.value, ProcurementStatus.PARTIALLY_PURCHASED.value]
            ),
        )
        .order_by(ProcurementList.created_at.desc())
    )
    suppliers = {
        s.id: s
        for s in db.scalars(select(TenantSupplier).where(TenantSupplier.tenant_id == tenant_id))
    }
    lists: list[PickupList] = []
    for row in rows:
        grouped: dict[UUID | None, list[PickupItem]] = defaultdict(list)
        for item in _items(db, tenant_id, row.id):
            if _line_is_settled(item):
                continue
            grouped[item.supplier_id].append(
                PickupItem(
                    item_id=item.id,
                    product_name=item.product_name,
                    price_basis=item.price_basis,
                    pieces_per_box=item.pieces_per_box,
                    remaining_quantity=item.remaining_quantity,
                    notes=item.notes,
                )
            )
        pickup_suppliers = []
        for supplier_id, items in grouped.items():
            supplier = suppliers.get(supplier_id) if supplier_id else None
            pickup_suppliers.append(
                PickupSupplier(
                    supplier_id=supplier_id,
                    supplier_name=supplier.name if supplier else None,
                    contact_name=supplier.contact_name if supplier else None,
                    contact_phone=supplier.contact_phone if supplier else None,
                    address=supplier.address if supplier else None,
                    latitude=supplier.latitude if supplier else None,
                    longitude=supplier.longitude if supplier else None,
                    items=items,
                )
            )
        pickup_suppliers.sort(key=lambda s: (s.supplier_name is None, s.supplier_name or ""))
        lists.append(
            PickupList(
                list_id=row.id,
                title=row.title,
                status=row.status,
                notes=row.notes,
                suppliers=pickup_suppliers,
            )
        )
    return PickupResponse(lists=lists)
