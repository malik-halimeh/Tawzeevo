"""Actual supplier purchases (PHASE_06.md G/H; D-034, D-038, D-039, D-059).

Finalization is one transaction: purchase header + lines, one ACTUAL_PURCHASE cost entry per
line (the price history never gets a purchase it cannot point to), one PURCHASE_CHARGE entry on
the supplier ledger (payable up), the linked procurement lines' `purchased_quantity` up and the
list status refreshed, an audit row, commit. A failure anywhere rolls the whole thing back.
Replaying the same idempotency key returns the stored purchase. A reversal is a compensating
PURCHASE_REVERSAL ledger entry and the procurement progress taken back; the purchase row, its
lines and the appended cost entries stay as history. Supplier payments stay aggregate per
currency (never allocated to a purchase). No inventory is touched because none exists.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    AuditEvent,
    CostSourceType,
    CustomerLedgerEntry,
    ProcurementItem,
    ProcurementList,
    ProductPriceBasis,
    SupplierLedgerEntry,
    SupplierLedgerEntryType,
    SupplierPurchase,
    SupplierPurchaseItem,
    TenantProduct,
    TenantProductCostEntry,
    TenantSupplier,
)
from tawzeevo_api.repositories.tenancy import commit_and_restore_tenant_scope, set_tenant_scope
from tawzeevo_api.schemas.supplier_purchases import (
    CurrencyTotal,
    OutstandingTotalsResponse,
    PurchaseCreateRequest,
    PurchaseLineResponse,
    PurchaseResponse,
)
from tawzeevo_api.services.invoice_editor import money
from tawzeevo_api.services.payments import _lock_idempotency_key
from tawzeevo_api.services.procurement import refresh_status


def _supplier(db: Session, tenant_id: UUID, supplier_id: UUID) -> TenantSupplier:
    supplier = db.scalar(
        select(TenantSupplier)
        .where(TenantSupplier.tenant_id == tenant_id, TenantSupplier.id == supplier_id)
        .with_for_update()
    )
    if supplier is None:
        raise AppError(404, "SUPPLIER_NOT_FOUND", "Supplier was not found")
    return supplier


def get_purchase(db: Session, tenant_id: UUID, purchase_id: UUID) -> SupplierPurchase:
    set_tenant_scope(db, tenant_id)
    row = db.get(SupplierPurchase, purchase_id)
    if row is None or row.tenant_id != tenant_id:
        raise AppError(404, "PURCHASE_NOT_FOUND", "Supplier purchase was not found")
    return row


def _existing(db: Session, tenant_id: UUID, key: UUID) -> SupplierPurchase | None:
    return db.scalar(
        select(SupplierPurchase).where(
            SupplierPurchase.tenant_id == tenant_id, SupplierPurchase.idempotency_key == key
        )
    )


def _fingerprint(request: PurchaseCreateRequest) -> dict[str, object]:
    return {
        "supplier_id": str(request.supplier_id),
        "currency": request.currency,
        "items": [
            (str(i.product_id), f"{money(i.quantity):f}", f"{money(i.unit_cost):f}")
            for i in request.items
        ],
    }


def record_purchase(
    db: Session, tenant_id: UUID, actor: UUID, request: PurchaseCreateRequest
) -> tuple[SupplierPurchase, bool]:
    """PHASE_06.md G finalization transaction. Returns (purchase, replayed)."""
    set_tenant_scope(db, tenant_id)
    _lock_idempotency_key(db, request.idempotency_key)
    existing = _existing(db, tenant_id, request.idempotency_key)
    if existing is not None:
        stored = {
            "supplier_id": str(existing.supplier_id),
            "currency": existing.currency,
            "items": [
                (str(i.tenant_product_id), f"{money(i.quantity):f}", f"{money(i.unit_cost):f}")
                for i in _lines(db, tenant_id, existing.id)
            ],
        }
        if stored != _fingerprint(request):
            raise AppError(
                409, "IDEMPOTENCY_CONFLICT", "Key was already used for a different purchase"
            )
        return existing, True

    supplier = _supplier(db, tenant_id, request.supplier_id)
    procurement_list: ProcurementList | None = None
    if request.procurement_list_id is not None:
        procurement_list = db.get(ProcurementList, request.procurement_list_id)
        if procurement_list is None or procurement_list.tenant_id != tenant_id:
            raise AppError(404, "PROCUREMENT_LIST_NOT_FOUND", "Procurement list was not found")
        if procurement_list.status in ("COMPLETE", "CANCELLED"):
            raise AppError(409, "PROCUREMENT_LIST_CLOSED", "That list is complete or cancelled")

    purchased_at = request.purchased_at or datetime.now(UTC)
    purchase = SupplierPurchase(
        tenant_id=tenant_id,
        supplier_id=supplier.id,
        procurement_list_id=procurement_list.id if procurement_list else None,
        idempotency_key=request.idempotency_key,
        purchased_at=purchased_at,
        currency=request.currency,
        total_amount=Decimal("0"),
        supplier_reference=request.supplier_reference,
        notes=request.notes,
        created_by_user_id=actor,
    )
    db.add(purchase)
    db.flush()

    total = Decimal("0")
    touched_lists: dict[UUID, ProcurementList] = {}
    for number, line in enumerate(request.items, start=1):
        product = db.get(TenantProduct, line.product_id)
        if product is None or product.tenant_id != tenant_id:
            raise AppError(404, "PRODUCT_NOT_FOUND", f"Line {number}: product was not found")
        if product.currency != request.currency:
            # D-034: a cost is recorded in the product's currency; no silent conversion.
            raise AppError(
                400,
                "CURRENCY_MISMATCH",
                f"Line {number}: purchase currency must match the product currency",
            )
        basis = line.price_basis or product.price_basis
        pieces = (
            (line.pieces_per_box or product.pieces_per_box)
            if basis is ProductPriceBasis.BOX
            else None
        )
        if basis is ProductPriceBasis.BOX and pieces is None:
            raise AppError(
                400, "COST_PIECES_PER_BOX_REQUIRED", f"Line {number}: box cost needs pieces per box"
            )
        procurement_item: ProcurementItem | None = None
        if line.procurement_item_id is not None:
            procurement_item = db.scalar(
                select(ProcurementItem)
                .where(
                    ProcurementItem.tenant_id == tenant_id,
                    ProcurementItem.id == line.procurement_item_id,
                )
                .with_for_update()
            )
            if procurement_item is None or procurement_item.tenant_product_id != product.id:
                raise AppError(
                    404,
                    "PROCUREMENT_ITEM_NOT_FOUND",
                    f"Line {number}: procurement line was not found for this product",
                )
            if procurement_list is not None and procurement_item.list_id != procurement_list.id:
                raise AppError(
                    409,
                    "PROCUREMENT_ITEM_WRONG_LIST",
                    f"Line {number}: procurement line belongs to another list",
                )
            if procurement_item.removed_at is not None or procurement_item.carried_to_item_id:
                raise AppError(
                    409, "PROCUREMENT_ITEM_CLOSED", f"Line {number}: procurement line is closed"
                )
        line_total = money(line.unit_cost * line.quantity)
        total += line_total
        cost_entry = TenantProductCostEntry(
            tenant_id=tenant_id,
            tenant_product_id=product.id,
            supplier_id=supplier.id,
            unit_cost=money(line.unit_cost),
            currency=request.currency,
            cost_basis=basis,
            pieces_per_box=pieces,
            effective_at=purchased_at,
            source_type=CostSourceType.ACTUAL_PURCHASE.value,
            source_reference_id=purchase.id,
            quantity_context=line.quantity,
            notes=line.notes,
            created_by_user_id=actor,
        )
        db.add(cost_entry)
        db.flush()
        db.add(
            SupplierPurchaseItem(
                tenant_id=tenant_id,
                purchase_id=purchase.id,
                line_number=number,
                tenant_product_id=product.id,
                product_name=product.name,
                procurement_item_id=procurement_item.id if procurement_item else None,
                quantity=line.quantity,
                price_basis=basis,
                pieces_per_box=pieces,
                unit_cost=money(line.unit_cost),
                line_total=line_total,
                cost_entry_id=cost_entry.id,
                notes=line.notes,
            )
        )
        if procurement_item is not None:
            procurement_item.purchased_quantity = (
                Decimal(procurement_item.purchased_quantity) + line.quantity
            )
            procurement_item.version += 1
            owner_list = db.get(ProcurementList, procurement_item.list_id)
            if owner_list is not None:
                touched_lists[owner_list.id] = owner_list
    purchase.total_amount = money(total)
    db.add(
        SupplierLedgerEntry(
            tenant_id=tenant_id,
            supplier_id=supplier.id,
            currency=request.currency,
            signed_amount=money(total),
            entry_type=SupplierLedgerEntryType.PURCHASE_CHARGE,
            source_type="SUPPLIER_PURCHASE",
            source_id=purchase.id,
            source_effect_key=f"supplier-purchase:{purchase.id}",
            effective_at=purchased_at,
            actor_user_id=actor,
            idempotency_key=request.idempotency_key,
            metadata_json={"lines": len(request.items)},
        )
    )
    db.flush()
    for owner_list in touched_lists.values():
        refresh_status(db, owner_list)
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor,
            action="supplier_purchase_recorded",
            entity_type="supplier_purchase",
            entity_id=purchase.id,
            details={
                "supplier_id": str(supplier.id),
                "currency": request.currency,
                "total": f"{money(total):f}",
                "lines": str(len(request.items)),
            },
        )
    )
    commit_and_restore_tenant_scope(db, tenant_id)
    return get_purchase(db, tenant_id, purchase.id), False


def reverse_purchase(
    db: Session, tenant_id: UUID, actor: UUID, purchase_id: UUID, key: UUID, reason: str
) -> SupplierPurchase:
    """Compensating reversal (PHASE_06.md H `supplier_purchase_reversal`); history stays."""
    set_tenant_scope(db, tenant_id)
    _lock_idempotency_key(db, key)
    purchase = get_purchase(db, tenant_id, purchase_id)
    if purchase.reversed_at is not None:
        if purchase.reversal_idempotency_key == key:
            return purchase
        raise AppError(409, "PURCHASE_ALREADY_REVERSED", "This purchase was already reversed")
    _supplier(db, tenant_id, purchase.supplier_id)
    original = db.scalar(
        select(SupplierLedgerEntry).where(
            SupplierLedgerEntry.tenant_id == tenant_id,
            SupplierLedgerEntry.source_effect_key == f"supplier-purchase:{purchase.id}",
        )
    )
    if original is None:
        raise AppError(409, "PURCHASE_LEDGER_EFFECT_MISSING", "Purchase ledger effect is missing")
    now = datetime.now(UTC)
    db.add(
        SupplierLedgerEntry(
            tenant_id=tenant_id,
            supplier_id=purchase.supplier_id,
            currency=purchase.currency,
            signed_amount=-Decimal(purchase.total_amount),
            entry_type=SupplierLedgerEntryType.PURCHASE_REVERSAL,
            source_type="SUPPLIER_PURCHASE",
            source_id=purchase.id,
            source_effect_key=f"supplier-purchase-reversal:{purchase.id}",
            effective_at=now,
            actor_user_id=actor,
            reverses_entry_id=original.id,
            idempotency_key=key,
            metadata_json={"reason": reason},
        )
    )
    touched: dict[UUID, ProcurementList] = {}
    for line in _lines(db, tenant_id, purchase.id):
        if line.procurement_item_id is None:
            continue
        item = db.get(ProcurementItem, line.procurement_item_id)
        if item is None:
            continue
        item.purchased_quantity = max(
            Decimal("0"), Decimal(item.purchased_quantity) - Decimal(line.quantity)
        )
        item.version += 1
        owner_list = db.get(ProcurementList, item.list_id)
        if owner_list is not None and owner_list.status != "CANCELLED":
            touched[owner_list.id] = owner_list
    purchase.reversed_at = now
    purchase.reversal_reason = reason
    purchase.reversal_idempotency_key = key
    db.flush()
    for owner_list in touched.values():
        if owner_list.status == "COMPLETE":
            # Progress went backwards: the list is open again until the owner settles it.
            owner_list.status = "OPEN"
            owner_list.completed_at = None
        refresh_status(db, owner_list)
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor,
            action="supplier_purchase_reversed",
            entity_type="supplier_purchase",
            entity_id=purchase.id,
            details={"reason": reason, "total": f"{Decimal(purchase.total_amount):f}"},
        )
    )
    commit_and_restore_tenant_scope(db, tenant_id)
    return get_purchase(db, tenant_id, purchase.id)


def _lines(db: Session, tenant_id: UUID, purchase_id: UUID) -> list[SupplierPurchaseItem]:
    return list(
        db.scalars(
            select(SupplierPurchaseItem)
            .where(
                SupplierPurchaseItem.tenant_id == tenant_id,
                SupplierPurchaseItem.purchase_id == purchase_id,
            )
            .order_by(SupplierPurchaseItem.line_number)
        )
    )


def list_purchases(
    db: Session, tenant_id: UUID, supplier_id: UUID | None = None, limit: int = 100
) -> list[SupplierPurchase]:
    set_tenant_scope(db, tenant_id)
    query = select(SupplierPurchase).where(SupplierPurchase.tenant_id == tenant_id)
    if supplier_id is not None:
        query = query.where(SupplierPurchase.supplier_id == supplier_id)
    return list(db.scalars(query.order_by(SupplierPurchase.purchased_at.desc()).limit(limit)))


def purchase_response(
    db: Session, tenant_id: UUID, purchase: SupplierPurchase, replayed: bool = False
) -> PurchaseResponse:
    supplier = db.get(TenantSupplier, purchase.supplier_id)
    return PurchaseResponse(
        id=purchase.id,
        supplier_id=purchase.supplier_id,
        supplier_name=supplier.name if supplier else "?",
        procurement_list_id=purchase.procurement_list_id,
        purchased_at=purchase.purchased_at,
        currency=purchase.currency,
        total_amount=purchase.total_amount,
        supplier_reference=purchase.supplier_reference,
        notes=purchase.notes,
        created_at=purchase.created_at,
        reversed_at=purchase.reversed_at,
        reversal_reason=purchase.reversal_reason,
        replayed=replayed,
        items=[
            PurchaseLineResponse(
                id=line.id,
                line_number=line.line_number,
                product_id=line.tenant_product_id,
                product_name=line.product_name,
                procurement_item_id=line.procurement_item_id,
                quantity=line.quantity,
                price_basis=line.price_basis,
                pieces_per_box=line.pieces_per_box,
                unit_cost=line.unit_cost,
                line_total=line.line_total,
                cost_entry_id=line.cost_entry_id,
                notes=line.notes,
            )
            for line in _lines(db, tenant_id, purchase.id)
        ],
    )


# ---------------------------------------------------------------------------------------------
# Totals by currency (PHASE_06.md H dashboard; D-066)
# ---------------------------------------------------------------------------------------------


def _totals(rows: list[tuple[str, Decimal]]) -> list[CurrencyTotal]:
    outstanding: dict[str, Decimal] = defaultdict(Decimal)
    credit: dict[str, Decimal] = defaultdict(Decimal)
    parties: dict[str, int] = defaultdict(int)
    for currency, balance in rows:
        amount = Decimal(balance or 0)
        if amount > 0:
            outstanding[currency] += amount
            parties[currency] += 1
        elif amount < 0:
            credit[currency] += -amount
    currencies = sorted(set(outstanding) | set(credit))
    return [
        CurrencyTotal(
            currency=currency,
            outstanding=money(outstanding[currency]),
            credit=money(credit[currency]),
            parties=parties[currency],
        )
        for currency in currencies
    ]


def outstanding_totals(db: Session, tenant_id: UUID) -> OutstandingTotalsResponse:
    """Positive balances summed per currency; credits listed separately; no netting and no
    cross-currency sum (D-066)."""
    set_tenant_scope(db, tenant_id)
    customer_rows = db.execute(
        select(CustomerLedgerEntry.currency, func.sum(CustomerLedgerEntry.signed_amount))
        .where(CustomerLedgerEntry.tenant_id == tenant_id)
        .group_by(CustomerLedgerEntry.customer_id, CustomerLedgerEntry.currency)
    ).all()
    supplier_rows = db.execute(
        select(SupplierLedgerEntry.currency, func.sum(SupplierLedgerEntry.signed_amount))
        .where(SupplierLedgerEntry.tenant_id == tenant_id)
        .group_by(SupplierLedgerEntry.supplier_id, SupplierLedgerEntry.currency)
    ).all()
    return OutstandingTotalsResponse(
        customers=_totals([(c, Decimal(b)) for c, b in customer_rows]),
        suppliers=_totals([(c, Decimal(b)) for c, b in supplier_rows]),
    )
