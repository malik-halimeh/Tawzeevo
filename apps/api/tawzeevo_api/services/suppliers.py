"""Owner-facing supplier and product-cost setup (D-041 on the D-034 cost foundation).

Suppliers, cost entries and preferred-supplier choices are tenant-private. Cost entries are
append-only and effective-dated; nothing here edits or deletes a historical entry. Phase 6 may
append entries automatically later without changing these rules.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    AuditEvent,
    ProductPriceBasis,
    TenantProduct,
    TenantProductCostEntry,
    TenantSupplier,
)
from tawzeevo_api.repositories.tenancy import commit_and_restore_tenant_scope
from tawzeevo_api.schemas.suppliers import (
    PreferredSupplierRequest,
    ProductCostEntryCreateRequest,
    ProductCostEntryResponse,
    ProductCostSetupResponse,
    SupplierCreateRequest,
    SupplierListResponse,
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
    name = request.name.strip()
    if not name:
        raise AppError(422, "SUPPLIER_NAME_REQUIRED", "Supplier name is required")
    _reject_duplicate_name(db, tenant_id, name, exclude_id=supplier.id)
    previous = supplier.name
    supplier.name = name
    _audit(
        db,
        tenant_id,
        actor,
        "supplier_renamed",
        "tenant_supplier",
        supplier.id,
        previous_name=previous,
        name=name,
    )
    commit_and_restore_tenant_scope(db, tenant_id)
    db.refresh(supplier)
    return SupplierResponse.model_validate(supplier)


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


def append_product_cost(
    db: Session,
    tenant_id: UUID,
    actor: UUID,
    product_id: UUID,
    request: ProductCostEntryCreateRequest,
) -> ProductCostSetupResponse:
    product = get_product(db, tenant_id, product_id)
    _supplier(db, tenant_id, request.supplier_id)
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
        source_type="MANUAL",
        notes=request.notes.strip() if request.notes else None,
        created_by_user_id=actor,
    )
    db.add(entry)
    db.flush()
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
    )
    if product.preferred_supplier_id is None:
        # First cost for a product makes its supplier the default so invoice entry preloads it.
        product.preferred_supplier_id = request.supplier_id
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
    )
    commit_and_restore_tenant_scope(db, tenant_id)
    return _cost_setup(db, tenant_id, get_product(db, tenant_id, product_id))
