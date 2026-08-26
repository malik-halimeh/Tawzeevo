from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from tawzeevo_api.models import (
    CustomerGrade,
    PriceResolutionSource,
    ProductGradePrice,
    ProductPriceBasis,
    TenantGradeDiscount,
    TenantProduct,
)
from tawzeevo_api.repositories.tenancy import commit_and_restore_tenant_scope

MONEY_QUANTUM = Decimal("0.0001")
PERCENT_HUNDRED = Decimal("100")


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def derive_counterpart_prices(
    basis_price: Decimal,
    price_basis: ProductPriceBasis,
    pieces_per_box: int | None,
) -> tuple[Decimal, Decimal | None]:
    rounded_basis = quantize_money(basis_price)
    if price_basis is ProductPriceBasis.PIECE:
        box_price = (
            quantize_money(rounded_basis * pieces_per_box) if pieces_per_box is not None else None
        )
        return rounded_basis, box_price
    if pieces_per_box is None:
        raise RuntimeError("BOX product is missing pieces_per_box")
    return quantize_money(rounded_basis / pieces_per_box), rounded_basis


@dataclass(frozen=True)
class ResolvedPricing:
    customer_grade: CustomerGrade | None
    source: PriceResolutionSource
    discount_percent: Decimal | None
    basis_price: Decimal
    piece_price: Decimal
    box_price: Decimal | None


def list_grade_discounts(db: Session, tenant_id: UUID) -> list[TenantGradeDiscount]:
    return list(
        db.scalars(
            select(TenantGradeDiscount)
            .where(TenantGradeDiscount.tenant_id == tenant_id)
            .order_by(TenantGradeDiscount.grade.asc())
        )
    )


def set_grade_discount(
    db: Session,
    tenant_id: UUID,
    grade: CustomerGrade,
    discount_percent: Decimal,
) -> TenantGradeDiscount:
    discount = db.scalar(
        select(TenantGradeDiscount).where(
            TenantGradeDiscount.tenant_id == tenant_id,
            TenantGradeDiscount.grade == grade,
        )
    )
    if discount is None:
        discount = TenantGradeDiscount(
            tenant_id=tenant_id,
            grade=grade,
            discount_percent=quantize_money(discount_percent),
        )
        db.add(discount)
    else:
        discount.discount_percent = quantize_money(discount_percent)
    commit_and_restore_tenant_scope(db, tenant_id)
    db.refresh(discount)
    return discount


def clear_grade_discount(db: Session, tenant_id: UUID, grade: CustomerGrade) -> None:
    discount = db.scalar(
        select(TenantGradeDiscount).where(
            TenantGradeDiscount.tenant_id == tenant_id,
            TenantGradeDiscount.grade == grade,
        )
    )
    if discount is not None:
        db.delete(discount)
        commit_and_restore_tenant_scope(db, tenant_id)


def list_product_grade_prices(
    db: Session, tenant_id: UUID, product_id: UUID
) -> list[ProductGradePrice]:
    return list(
        db.scalars(
            select(ProductGradePrice)
            .where(
                ProductGradePrice.tenant_id == tenant_id,
                ProductGradePrice.tenant_product_id == product_id,
            )
            .order_by(ProductGradePrice.grade.asc())
        )
    )


def set_product_grade_price(
    db: Session,
    tenant_id: UUID,
    product_id: UUID,
    grade: CustomerGrade,
    unit_price: Decimal,
) -> ProductGradePrice:
    grade_price = db.scalar(
        select(ProductGradePrice).where(
            ProductGradePrice.tenant_id == tenant_id,
            ProductGradePrice.tenant_product_id == product_id,
            ProductGradePrice.grade == grade,
        )
    )
    if grade_price is None:
        grade_price = ProductGradePrice(
            tenant_id=tenant_id,
            tenant_product_id=product_id,
            grade=grade,
            unit_price=quantize_money(unit_price),
        )
        db.add(grade_price)
    else:
        grade_price.unit_price = quantize_money(unit_price)
    commit_and_restore_tenant_scope(db, tenant_id)
    db.refresh(grade_price)
    return grade_price


def clear_product_grade_price(
    db: Session, tenant_id: UUID, product_id: UUID, grade: CustomerGrade
) -> None:
    grade_price = db.scalar(
        select(ProductGradePrice).where(
            ProductGradePrice.tenant_id == tenant_id,
            ProductGradePrice.tenant_product_id == product_id,
            ProductGradePrice.grade == grade,
        )
    )
    if grade_price is not None:
        db.delete(grade_price)
        commit_and_restore_tenant_scope(db, tenant_id)


def resolve_product_pricing(
    db: Session,
    tenant_id: UUID,
    product: TenantProduct,
    customer_grade: CustomerGrade | None,
) -> ResolvedPricing:
    source = PriceResolutionSource.NORMAL
    discount_percent: Decimal | None = None
    resolved_basis = product.unit_price
    if customer_grade is not None:
        explicit = db.scalar(
            select(ProductGradePrice).where(
                ProductGradePrice.tenant_id == tenant_id,
                ProductGradePrice.tenant_product_id == product.id,
                ProductGradePrice.grade == customer_grade,
            )
        )
        if explicit is not None:
            source = PriceResolutionSource.EXPLICIT_GRADE_PRICE
            resolved_basis = explicit.unit_price
        else:
            discount = db.scalar(
                select(TenantGradeDiscount).where(
                    TenantGradeDiscount.tenant_id == tenant_id,
                    TenantGradeDiscount.grade == customer_grade,
                )
            )
            if discount is not None:
                source = PriceResolutionSource.GRADE_DISCOUNT
                discount_percent = discount.discount_percent
                resolved_basis = product.unit_price * (
                    Decimal("1") - discount.discount_percent / PERCENT_HUNDRED
                )
    basis_price = quantize_money(resolved_basis)
    piece_price, box_price = derive_counterpart_prices(
        basis_price, product.price_basis, product.pieces_per_box
    )
    return ResolvedPricing(
        customer_grade=customer_grade,
        source=source,
        discount_percent=discount_percent,
        basis_price=basis_price,
        piece_price=piece_price,
        box_price=box_price,
    )
