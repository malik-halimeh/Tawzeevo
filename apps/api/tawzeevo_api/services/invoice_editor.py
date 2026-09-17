from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, DivisionByZero, InvalidOperation, Overflow, localcontext
from difflib import SequenceMatcher
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    AuditEvent,
    Customer,
    CustomerGrade,
    CustomerLedgerEntry,
    Invoice,
    InvoiceRevision,
    InvoiceRevisionItem,
    InvoiceStatus,
    PriceResolutionSource,
    ProductPriceBasis,
    TenantProduct,
    TenantProductCostEntry,
    TenantSupplier,
)
from tawzeevo_api.repositories.tenancy import commit_and_restore_tenant_scope
from tawzeevo_api.schemas.invoice_editor import (
    CatalogMatchResponse,
    CatalogSearchResponse,
    InvoiceEditorDraftRequest,
    InvoiceEditorItemRequest,
    InvoiceEditorItemResponse,
    InvoiceEditorResponse,
    ItemParserResponse,
    ParsedItemResponse,
    ProductCostOptionResponse,
    ProductCostOptionsResponse,
)
from tawzeevo_api.services.cash_van import get_customer, get_product, product_response
from tawzeevo_api.services.pricing import derive_counterpart_prices, resolve_product_pricing

MONEY_SCALE = Decimal("0.0001")
ZERO = Decimal("0.0000")
_TOKEN = re.compile(r"\s*(?:(\d+(?:\.\d+)?)|(.))")
_QUANTITY_PREFIX = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(?:x|×|\*)?\s+(.+)$", re.I)
_QUANTITY_SUFFIX = re.compile(r"^(.+?)\s+(?:x|×|\*)\s*(\d+(?:\.\d+)?)\s*$", re.I)
_ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
_DIGIT_TRANSLATION = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_ARABIC_NORMALIZATION = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ؤ": "و", "ئ": "ي"})


# Largest magnitude representable by the authoritative NUMERIC(20,4) money columns.
MONEY_LIMIT = Decimal("10000000000000000")  # 10^16, i.e. 16 integer digits


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_SCALE, rounding=ROUND_HALF_UP)


def stored_money(value: Decimal) -> Decimal:
    """Quantize an authoritative monetary stage and reject values NUMERIC(20,4) cannot store.

    A calculator or line/invoice stage that overflows is a validation error for the owner, not an
    internal failure. Rounding stays Q4 ROUND_HALF_UP; only representability is enforced.
    """
    try:
        with localcontext() as context:
            context.prec = 60
            quantized = money(value)
    except (InvalidOperation, Overflow) as exc:
        raise AppError(400, "AMOUNT_OUT_OF_RANGE", "Amount is too large to be stored") from exc
    if abs(quantized) >= MONEY_LIMIT:
        raise AppError(400, "AMOUNT_OUT_OF_RANGE", "Amount is too large to be stored")
    return quantized


class _Calculator:
    def __init__(self, expression: str) -> None:
        normalized = expression.translate(_DIGIT_TRANSLATION)
        self.tokens: list[str] = []
        position = 0
        while position < len(normalized):
            match = _TOKEN.match(normalized, position)
            if match is None:
                raise AppError(400, "INVALID_CALCULATOR_EXPRESSION", "Expression is invalid")
            number, operator = match.groups()
            if number is not None:
                self.tokens.append(number)
            elif operator in {"+", "-", "*", "/", "(", ")"}:
                self.tokens.append(operator)
            elif operator and not operator.isspace():
                raise AppError(
                    400,
                    "INVALID_CALCULATOR_EXPRESSION",
                    "Only numbers and + - * / ( ) are allowed",
                )
            position = match.end()
        self.index = 0

    def parse(self) -> Decimal:
        if not self.tokens:
            raise AppError(400, "INVALID_CALCULATOR_EXPRESSION", "Expression is empty")
        try:
            with localcontext() as context:
                context.prec = 38
                result = self._expression()
        except (DivisionByZero, InvalidOperation, Overflow, ZeroDivisionError) as exc:
            raise AppError(
                400, "INVALID_CALCULATOR_EXPRESSION", "Expression cannot be calculated"
            ) from exc
        if self.index != len(self.tokens):
            raise AppError(400, "INVALID_CALCULATOR_EXPRESSION", "Expression is invalid")
        return stored_money(result)

    def _expression(self) -> Decimal:
        value = self._term()
        while self._peek() in {"+", "-"}:
            operator = self._take()
            right = self._term()
            value = value + right if operator == "+" else value - right
        return value

    def _term(self) -> Decimal:
        value = self._factor()
        while self._peek() in {"*", "/"}:
            operator = self._take()
            right = self._factor()
            value = value * right if operator == "*" else value / right
        return value

    def _factor(self) -> Decimal:
        token = self._peek()
        if token in {"+", "-"}:
            operator = self._take()
            value = self._factor()
            return value if operator == "+" else -value
        if token == "(":
            self._take()
            value = self._expression()
            if self._take() != ")":
                raise AppError(400, "INVALID_CALCULATOR_EXPRESSION", "Parentheses do not match")
            return value
        if token is None or token in {"*", "/", ")"}:
            raise AppError(400, "INVALID_CALCULATOR_EXPRESSION", "Expression is invalid")
        self._take()
        try:
            return Decimal(token)
        except InvalidOperation as exc:
            raise AppError(400, "INVALID_CALCULATOR_EXPRESSION", "Expression is invalid") from exc

    def _peek(self) -> str | None:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def _take(self) -> str:
        token = self._peek()
        if token is None:
            raise AppError(400, "INVALID_CALCULATOR_EXPRESSION", "Expression is incomplete")
        self.index += 1
        return token


def calculate_expression(expression: str) -> Decimal:
    return _Calculator(expression).parse()


def normalize_item_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).translate(_DIGIT_TRANSLATION)
    value = _ARABIC_DIACRITICS.sub("", value).translate(_ARABIC_NORMALIZATION)
    value = value.casefold()
    value = re.sub(r"[^\w\s-]", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def _extract_quantity(line: str) -> tuple[Decimal, str]:
    normalized_digits = line.translate(_DIGIT_TRANSLATION)
    suffix = _QUANTITY_SUFFIX.match(normalized_digits)
    prefix = _QUANTITY_PREFIX.match(normalized_digits)
    match = prefix or suffix
    if match is None:
        return Decimal("1.0000"), normalized_digits.strip()
    if prefix is not None:
        raw_quantity, query = match.group(1), match.group(2)
    else:
        query, raw_quantity = match.group(1), match.group(2)
    quantity = money(Decimal(raw_quantity))
    if quantity <= 0:
        raise AppError(400, "INVALID_ITEM_QUANTITY", "Item quantity must be greater than zero")
    return quantity, query.strip()


def _primary_match(
    db: Session,
    product: TenantProduct,
    match_type: Literal["EXACT", "PREFIX", "FUZZY"],
    score: Decimal,
    *,
    preferred_barcode: str | None = None,
) -> CatalogMatchResponse:
    response = product_response(db, product, preferred_barcode=preferred_barcode)
    primary_barcode = next(
        (item for item in response.barcodes if item.barcode == response.barcode),
        response.barcodes[0],
    )
    return CatalogMatchResponse(
        product_id=product.id,
        name=product.name,
        barcode=response.barcode,
        package_level=ProductPriceBasis(primary_barcode.package_level.value),
        currency=product.currency,
        price_basis=product.price_basis,
        unit_price=money(product.unit_price),
        image_url=response.images[0].url if response.images else None,
        match_type=match_type,
        score=money(score),
    )


def _tenant_products(db: Session, tenant_id: UUID) -> list[TenantProduct]:
    return list(
        db.scalars(
            select(TenantProduct)
            .where(TenantProduct.tenant_id == tenant_id)
            .order_by(TenantProduct.name.asc(), TenantProduct.id.asc())
        )
    )


def search_catalog(
    db: Session, tenant_id: UUID, query: str, *, limit: int = 12
) -> CatalogSearchResponse:
    normalized = normalize_item_text(query)
    if not normalized:
        return CatalogSearchResponse(matches=[])
    exact: list[tuple[TenantProduct, str | None]] = []
    prefix: list[tuple[TenantProduct, str | None]] = []
    for product in _tenant_products(db, tenant_id):
        name = normalize_item_text(product.name)
        response = product_response(db, product)
        barcodes = {normalize_item_text(item.barcode): item.barcode for item in response.barcodes}
        if normalized == name or normalized in barcodes:
            exact.append((product, barcodes.get(normalized)))
        elif name.startswith(normalized) or any(code.startswith(normalized) for code in barcodes):
            matching_barcode = next(
                (raw for code, raw in barcodes.items() if code.startswith(normalized)), None
            )
            prefix.append((product, matching_barcode))
    selected = exact if exact else prefix
    match_type: Literal["EXACT", "PREFIX"] = "EXACT" if exact else "PREFIX"
    return CatalogSearchResponse(
        matches=[
            _primary_match(
                db,
                product,
                match_type,
                Decimal("1"),
                preferred_barcode=preferred_barcode,
            )
            for product, preferred_barcode in selected[:limit]
        ]
    )


def product_cost_options(
    db: Session,
    tenant_id: UUID,
    product_id: UUID,
    currency: str,
    basis: ProductPriceBasis,
) -> ProductCostOptionsResponse:
    product = get_product(db, tenant_id, product_id)
    if product.currency != currency:
        raise AppError(400, "CURRENCY_MISMATCH", "Cost currency must match product currency")
    suppliers = list(
        db.scalars(
            select(TenantSupplier)
            .where(TenantSupplier.tenant_id == tenant_id)
            .order_by(TenantSupplier.name.asc(), TenantSupplier.id.asc())
        )
    )
    options: list[ProductCostOptionResponse] = []
    for supplier in suppliers:
        entry = db.scalar(
            select(TenantProductCostEntry)
            .where(
                TenantProductCostEntry.tenant_id == tenant_id,
                TenantProductCostEntry.tenant_product_id == product.id,
                TenantProductCostEntry.supplier_id == supplier.id,
                TenantProductCostEntry.currency == currency,
                TenantProductCostEntry.cost_basis == basis,
                TenantProductCostEntry.effective_at <= datetime.now(UTC),
            )
            .order_by(
                TenantProductCostEntry.effective_at.desc(),
                TenantProductCostEntry.created_at.desc(),
                TenantProductCostEntry.id.desc(),
            )
            .limit(1)
        )
        options.append(
            ProductCostOptionResponse(
                supplier_id=supplier.id,
                supplier_name=supplier.name,
                is_preferred=supplier.id == product.preferred_supplier_id,
                product_cost_entry_id=entry.id if entry else None,
                unit_cost=money(entry.unit_cost) if entry else None,
                currency=currency,
                cost_basis=basis,
                pieces_per_box=entry.pieces_per_box if entry else None,
                effective_at=entry.effective_at if entry else None,
            )
        )
    options.sort(key=lambda option: (not option.is_preferred, option.supplier_name.casefold()))
    return ProductCostOptionsResponse(options=options)


def parse_item_text(
    db: Session,
    tenant_id: UUID,
    text: str,
    *,
    threshold: Decimal,
) -> ItemParserResponse:
    products = _tenant_products(db, tenant_id)
    parsed: list[ParsedItemResponse] = []
    for source_line in (line.strip() for line in text.splitlines() if line.strip()):
        quantity, query = _extract_quantity(source_line)
        normalized = normalize_item_text(query)
        exact_products: list[tuple[TenantProduct, str | None]] = []
        for product in products:
            response = product_response(db, product)
            barcode_aliases = {
                normalize_item_text(item.barcode): item.barcode for item in response.barcodes
            }
            if normalized == normalize_item_text(product.name) or normalized in barcode_aliases:
                exact_products.append((product, barcode_aliases.get(normalized)))
        if len(exact_products) == 1:
            exact_product, exact_barcode = exact_products[0]
            selected = _primary_match(
                db,
                exact_product,
                "EXACT",
                Decimal("1"),
                preferred_barcode=exact_barcode,
            )
            parsed.append(
                ParsedItemResponse(
                    source_text=source_line,
                    normalized_query=normalized,
                    quantity=quantity,
                    resolution="EXACT",
                    selected=selected,
                    suggestions=[],
                )
            )
            continue
        if len(exact_products) > 1:
            parsed.append(
                ParsedItemResponse(
                    source_text=source_line,
                    normalized_query=normalized,
                    quantity=quantity,
                    resolution="AMBIGUOUS",
                    selected=None,
                    suggestions=[
                        _primary_match(
                            db,
                            product,
                            "EXACT",
                            Decimal("1"),
                            preferred_barcode=preferred_barcode,
                        )
                        for product, preferred_barcode in exact_products[:5]
                    ],
                )
            )
            continue
        scored = sorted(
            (
                (
                    Decimal(
                        str(
                            SequenceMatcher(
                                None, normalized, normalize_item_text(product.name)
                            ).ratio()
                        )
                    ),
                    product,
                )
                for product in products
            ),
            key=lambda pair: (-pair[0], normalize_item_text(pair[1].name), str(pair[1].id)),
        )
        suggestions = [
            _primary_match(db, product, "FUZZY", score)
            for score, product in scored
            if score >= threshold
        ][:5]
        parsed.append(
            ParsedItemResponse(
                source_text=source_line,
                normalized_query=normalized,
                quantity=quantity,
                resolution="AMBIGUOUS" if suggestions else "UNRESOLVED",
                selected=None,
                suggestions=suggestions,
            )
        )
    if not parsed:
        raise AppError(400, "ITEM_LIST_EMPTY", "Enter at least one non-empty item line")
    return ItemParserResponse(threshold=money(threshold), items=parsed)


@dataclass(frozen=True)
class _PreparedCost:
    supplier_id: UUID | None
    entry_id: UUID | None
    unit_cost: Decimal | None
    currency: str | None
    basis: ProductPriceBasis | None
    pieces_per_box: int | None
    source_type: str | None
    is_override: bool
    override_reason: str | None


@dataclass(frozen=True)
class _PreparedItem:
    request: InvoiceEditorItemRequest
    product: TenantProduct | None
    name: str
    barcode: str | None
    media: dict[str, object]
    quantity: Decimal
    basis: ProductPriceBasis
    pieces_per_box: int | None
    normal_price: Decimal
    effective_price: Decimal
    customer_grade: CustomerGrade | None
    price_source: PriceResolutionSource
    grade_discount: Decimal | None
    grade_snapshot: dict[str, object]
    line_discount: Decimal
    line_markup: Decimal
    base_total: Decimal
    line_total: Decimal
    cost: _PreparedCost


def _validate_supplier(db: Session, tenant_id: UUID, supplier_id: UUID) -> None:
    if (
        db.scalar(
            select(TenantSupplier.id).where(
                TenantSupplier.id == supplier_id, TenantSupplier.tenant_id == tenant_id
            )
        )
        is None
    ):
        raise AppError(404, "SUPPLIER_NOT_FOUND", "Supplier was not found")


def _prepare_cost(
    db: Session,
    tenant_id: UUID,
    product: TenantProduct | None,
    request: InvoiceEditorItemRequest,
    currency: str,
    basis: ProductPriceBasis,
) -> _PreparedCost:
    supplier_id = request.supplier_id or (product.preferred_supplier_id if product else None)
    if supplier_id is not None:
        _validate_supplier(db, tenant_id, supplier_id)
    cost_basis = request.cost_basis or basis
    cost_pieces = request.cost_pieces_per_box or request.pieces_per_box
    if cost_basis is ProductPriceBasis.BOX and cost_pieces is None:
        cost_pieces = product.pieces_per_box if product else None
        if cost_pieces is None:
            raise AppError(400, "COST_PIECES_PER_BOX_REQUIRED", "Box cost requires pieces per box")
    if request.cost_override is not None:
        if supplier_id is None:
            raise AppError(400, "COST_SUPPLIER_REQUIRED", "Select a supplier for a cost override")
        return _PreparedCost(
            supplier_id=supplier_id,
            entry_id=None,
            unit_cost=money(request.cost_override),
            currency=currency,
            basis=cost_basis,
            pieces_per_box=cost_pieces,
            source_type="OWNER_OVERRIDE",
            is_override=True,
            override_reason=request.cost_override_reason.strip()
            if request.cost_override_reason
            else None,
        )
    if product is None or supplier_id is None:
        return _PreparedCost(None, None, None, None, None, None, None, False, None)
    entry = db.scalar(
        select(TenantProductCostEntry)
        .where(
            TenantProductCostEntry.tenant_id == tenant_id,
            TenantProductCostEntry.tenant_product_id == product.id,
            TenantProductCostEntry.supplier_id == supplier_id,
            TenantProductCostEntry.currency == currency,
            TenantProductCostEntry.cost_basis == cost_basis,
            TenantProductCostEntry.effective_at <= datetime.now(UTC),
        )
        .order_by(
            TenantProductCostEntry.effective_at.desc(),
            TenantProductCostEntry.created_at.desc(),
            TenantProductCostEntry.id.desc(),
        )
        .limit(1)
    )
    if entry is None:
        return _PreparedCost(supplier_id, None, None, None, None, None, None, False, None)
    return _PreparedCost(
        supplier_id=supplier_id,
        entry_id=entry.id,
        unit_cost=money(entry.unit_cost),
        currency=entry.currency,
        basis=entry.cost_basis,
        pieces_per_box=entry.pieces_per_box,
        source_type=entry.source_type,
        is_override=False,
        override_reason=None,
    )


def _selected_prices(
    db: Session,
    tenant_id: UUID,
    product: TenantProduct,
    customer: Customer,
    basis: ProductPriceBasis,
) -> tuple[Decimal, Decimal, PriceResolutionSource, Decimal | None, dict[str, object]]:
    pricing = resolve_product_pricing(db, tenant_id, product, customer.grade)
    normal_piece, normal_box = derive_counterpart_prices(
        product.unit_price, product.price_basis, product.pieces_per_box
    )
    if basis is ProductPriceBasis.PIECE:
        normal = normal_piece
        effective = pricing.piece_price
    else:
        if normal_box is None or pricing.box_price is None:
            raise AppError(400, "BOX_PRICE_UNAVAILABLE", "Product has no box packaging price")
        normal = normal_box
        effective = pricing.box_price
    snapshot: dict[str, object] = {
        "customer_grade": str(customer.grade) if customer.grade is not None else None,
        "price_source": str(pricing.source),
        "discount_percent": (
            str(pricing.discount_percent) if pricing.discount_percent is not None else None
        ),
        "catalog_price_basis": str(product.price_basis),
        "selected_price_basis": str(basis),
    }
    return money(normal), money(effective), pricing.source, pricing.discount_percent, snapshot


def _validate_barcode_basis(
    db: Session,
    product: TenantProduct,
    barcode: str | None,
    basis: ProductPriceBasis,
) -> str:
    response = product_response(db, product, preferred_barcode=barcode)
    selected = next((item for item in response.barcodes if item.barcode == barcode), None)
    if barcode is not None and selected is None:
        raise AppError(400, "BARCODE_PRODUCT_MISMATCH", "Barcode does not belong to product")
    selected = selected or next(
        (item for item in response.barcodes if item.package_level.value == basis.value),
        None,
    )
    if selected is None:
        raise AppError(400, "BARCODE_PACKAGE_MISMATCH", "Product has no barcode for this package")
    if selected.package_level.value != basis.value:
        raise AppError(
            400,
            "BARCODE_PACKAGE_MISMATCH",
            "Selected barcode package must match the invoice item price basis",
        )
    return selected.barcode


def _prepare_items(
    db: Session,
    tenant_id: UUID,
    customer: Customer,
    currency: str,
    requests: list[InvoiceEditorItemRequest],
    threshold: Decimal,
) -> list[_PreparedItem]:
    prepared: list[_PreparedItem] = []
    for requested in requests:
        barcode: str | None
        media: dict[str, object]
        quantity = calculate_expression(requested.quantity_expression)
        line_discount = calculate_expression(requested.line_discount_expression)
        line_markup = calculate_expression(requested.line_markup_expression)
        if quantity <= 0:
            raise AppError(400, "INVALID_ITEM_QUANTITY", "Item quantity must be greater than zero")
        if line_discount < 0 or line_markup < 0:
            raise AppError(400, "INVALID_LINE_ADJUSTMENT", "Line adjustments cannot be negative")
        if requested.product_id is not None:
            product = get_product(db, tenant_id, requested.product_id)
            if product.currency != currency:
                raise AppError(
                    400,
                    "CURRENCY_MISMATCH",
                    "Every catalog item must use the invoice currency",
                )
            barcode = _validate_barcode_basis(db, product, requested.barcode, requested.price_basis)
            normal_price, effective_price, price_source, grade_discount, grade_snapshot = (
                _selected_prices(db, tenant_id, product, customer, requested.price_basis)
            )
            response = product_response(db, product, preferred_barcode=barcode)
            media = {"images": [image.model_dump(mode="json") for image in response.images]}
            pieces = product.pieces_per_box
            if requested.accepted_fuzzy_match is not None:
                server_score = Decimal(
                    str(
                        SequenceMatcher(
                            None,
                            normalize_item_text(requested.accepted_fuzzy_match.query),
                            normalize_item_text(product.name),
                        ).ratio()
                    )
                )
                if server_score < threshold:
                    raise AppError(
                        400,
                        "FUZZY_MATCH_BELOW_THRESHOLD",
                        "Accepted fuzzy match no longer meets the configured threshold",
                    )
        else:
            product = None
            barcode = requested.barcode.strip() if requested.barcode else None
            normal_price = money(requested.manual_unit_price or ZERO)
            effective_price = normal_price
            price_source = PriceResolutionSource.NORMAL
            grade_discount = None
            grade_snapshot = {
                "customer_grade": str(customer.grade) if customer.grade is not None else None,
                "price_source": str(PriceResolutionSource.NORMAL),
                "manual_item": True,
            }
            media = {"images": []}
            pieces = requested.pieces_per_box
        base_total = stored_money(effective_price * quantity)
        line_total = stored_money(base_total - line_discount + line_markup)
        if line_total < 0:
            raise AppError(400, "NEGATIVE_LINE_TOTAL", "Line discount exceeds the line value")
        cost = _prepare_cost(db, tenant_id, product, requested, currency, requested.price_basis)
        prepared.append(
            _PreparedItem(
                request=requested,
                product=product,
                name=product.name if product else (requested.manual_name or ""),
                barcode=barcode,
                media=media,
                quantity=quantity,
                basis=requested.price_basis,
                pieces_per_box=pieces,
                normal_price=normal_price,
                effective_price=effective_price,
                customer_grade=customer.grade,
                price_source=price_source,
                grade_discount=grade_discount,
                grade_snapshot=grade_snapshot,
                line_discount=line_discount,
                line_markup=line_markup,
                base_total=base_total,
                line_total=line_total,
                cost=cost,
            )
        )
    return prepared


def _prior_balance(db: Session, tenant_id: UUID, customer_id: UUID, currency: str) -> Decimal:
    value = db.scalar(
        select(func.coalesce(func.sum(CustomerLedgerEntry.signed_amount), 0)).where(
            CustomerLedgerEntry.tenant_id == tenant_id,
            CustomerLedgerEntry.customer_id == customer_id,
            CustomerLedgerEntry.currency == currency,
        )
    )
    return money(Decimal(value or 0))


def _customer_snapshot(customer: Customer) -> dict[str, object]:
    return {
        "id": str(customer.id),
        "name": customer.name,
        "phone": customer.phone,
        "address": customer.address,
        "latitude": str(customer.latitude) if customer.latitude is not None else None,
        "longitude": str(customer.longitude) if customer.longitude is not None else None,
        "grade": str(customer.grade) if customer.grade is not None else None,
    }


def _write_revision_items(
    db: Session, tenant_id: UUID, revision_id: UUID, items: list[_PreparedItem]
) -> None:
    for line_number, item in enumerate(items, start=1):
        db.add(
            InvoiceRevisionItem(
                tenant_id=tenant_id,
                invoice_revision_id=revision_id,
                line_number=line_number,
                tenant_product_id=item.product.id if item.product else None,
                product_name=item.name,
                barcode=item.barcode,
                media_snapshot=item.media,
                quantity=item.quantity,
                price_basis=item.basis,
                pieces_per_box=item.pieces_per_box,
                normal_unit_price=item.normal_price,
                grade_rule_snapshot=item.grade_snapshot,
                effective_unit_price=item.effective_price,
                line_discount=item.line_discount,
                line_markup=item.line_markup,
                line_total=item.line_total,
                customer_grade=item.customer_grade,
                price_source=item.price_source,
                grade_discount_percent=item.grade_discount,
                supplier_id=item.cost.supplier_id,
                product_cost_entry_id=item.cost.entry_id,
                unit_cost=item.cost.unit_cost,
                cost_currency=item.cost.currency,
                cost_basis=item.cost.basis,
                cost_pieces_per_box=item.cost.pieces_per_box,
                cost_source_type=item.cost.source_type,
                is_cost_override=item.cost.is_override,
                cost_override_reason=item.cost.override_reason,
            )
        )


def _audit_fuzzy_acceptances(
    db: Session,
    tenant_id: UUID,
    actor_user_id: UUID,
    invoice_id: UUID,
    items: list[_PreparedItem],
) -> None:
    for item in items:
        accepted = item.request.accepted_fuzzy_match
        if accepted is None or item.product is None:
            continue
        server_score = money(
            Decimal(
                str(
                    SequenceMatcher(
                        None,
                        normalize_item_text(accepted.query),
                        normalize_item_text(item.product.name),
                    ).ratio()
                )
            )
        )
        db.add(
            AuditEvent(
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                action="invoice_item_fuzzy_match_accepted",
                entity_type="invoice",
                entity_id=invoice_id,
                details={
                    "query": accepted.query,
                    "selected_product_id": str(item.product.id),
                    "server_score": str(server_score),
                },
            )
        )


def _editor_response(db: Session, tenant_id: UUID, invoice: Invoice) -> InvoiceEditorResponse:
    revision = db.scalar(
        select(InvoiceRevision).where(
            InvoiceRevision.id == invoice.current_revision_id,
            InvoiceRevision.invoice_id == invoice.id,
            InvoiceRevision.tenant_id == tenant_id,
        )
    )
    if revision is None or revision.customer_id is None:
        raise AppError(409, "INVOICE_REVISION_MISSING", "Invoice revision was not found")
    items = list(
        db.scalars(
            select(InvoiceRevisionItem)
            .where(
                InvoiceRevisionItem.invoice_revision_id == revision.id,
                InvoiceRevisionItem.tenant_id == tenant_id,
            )
            .order_by(InvoiceRevisionItem.line_number.asc())
        )
    )
    return InvoiceEditorResponse(
        id=invoice.id,
        tenant_id=tenant_id,
        status=invoice.status,
        official_invoice_number=invoice.official_invoice_number,
        confirmed_at=invoice.confirmed_at,
        customer_id=revision.customer_id,
        customer_snapshot=revision.customer_snapshot,
        current_revision_id=revision.id,
        server_revision_number=revision.server_revision_number,
        pricing_version="pricing-v1",
        currency=revision.currency,
        prior_balance=money(revision.prior_balance_snapshot),
        subtotal=money(revision.subtotal),
        discount_total=money(revision.discount_total),
        markup_total=money(revision.markup_total),
        net_sales=money(revision.net_sales),
        total_due=money(revision.amount_due_display),
        items=[
            InvoiceEditorItemResponse(
                id=item.id,
                line_number=item.line_number,
                product_id=item.tenant_product_id,
                product_name=item.product_name,
                barcode=item.barcode,
                media_snapshot=item.media_snapshot,
                quantity=money(item.quantity),
                price_basis=item.price_basis,
                pieces_per_box=item.pieces_per_box,
                normal_unit_price=money(item.normal_unit_price),
                effective_unit_price=money(item.effective_unit_price),
                customer_grade=item.customer_grade,
                price_source=item.price_source,
                grade_discount_percent=(
                    money(item.grade_discount_percent)
                    if item.grade_discount_percent is not None
                    else None
                ),
                line_discount=money(item.line_discount),
                line_markup=money(item.line_markup),
                line_total=money(item.line_total),
                supplier_id=item.supplier_id,
                product_cost_entry_id=item.product_cost_entry_id,
                unit_cost=money(item.unit_cost) if item.unit_cost is not None else None,
                cost_currency=item.cost_currency,
                cost_basis=item.cost_basis,
                cost_pieces_per_box=item.cost_pieces_per_box,
                cost_source_type=item.cost_source_type,
                is_cost_override=item.is_cost_override,
                cost_override_reason=item.cost_override_reason,
            )
            for item in items
        ],
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
    )


def _totals(
    items: list[_PreparedItem], discount_expression: str, markup_expression: str
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    subtotal = stored_money(sum((item.base_total for item in items), ZERO))
    invoice_discount = calculate_expression(discount_expression)
    invoice_markup = calculate_expression(markup_expression)
    if invoice_discount < 0 or invoice_markup < 0:
        raise AppError(400, "INVALID_INVOICE_ADJUSTMENT", "Adjustments cannot be negative")
    line_discounts = sum((item.line_discount for item in items), ZERO)
    line_markups = sum((item.line_markup for item in items), ZERO)
    discount_total = stored_money(line_discounts + invoice_discount)
    markup_total = stored_money(line_markups + invoice_markup)
    net_sales = stored_money(subtotal - discount_total + markup_total)
    if net_sales < 0:
        raise AppError(400, "NEGATIVE_INVOICE_TOTAL", "Invoice discount exceeds invoice value")
    return (
        subtotal,
        discount_total,
        markup_total,
        net_sales,
    )


def create_editor_draft(
    db: Session,
    tenant_id: UUID,
    actor_user_id: UUID,
    request: InvoiceEditorDraftRequest,
    *,
    fuzzy_threshold: Decimal,
) -> InvoiceEditorResponse:
    if request.expected_predecessor_revision_id is not None:
        raise AppError(400, "PREDECESSOR_NOT_ALLOWED", "A new invoice has no predecessor")
    customer = get_customer(db, tenant_id, request.customer_id)
    items = _prepare_items(
        db, tenant_id, customer, request.currency, request.items, fuzzy_threshold
    )
    subtotal, discount_total, markup_total, net_sales = _totals(
        items, request.invoice_discount_expression, request.invoice_markup_expression
    )
    prior_balance = _prior_balance(db, tenant_id, customer.id, request.currency)
    invoice_id = uuid4()
    revision_id = uuid4()
    invoice = Invoice(
        id=invoice_id,
        tenant_id=tenant_id,
        customer_id=customer.id,
        current_revision_id=revision_id,
        status=InvoiceStatus.DRAFT,
        created_by_user_id=actor_user_id,
        updated_by_user_id=actor_user_id,
    )
    revision = InvoiceRevision(
        id=revision_id,
        tenant_id=tenant_id,
        invoice_id=invoice_id,
        client_command_id=request.client_command_id,
        predecessor_revision_id=None,
        server_revision_number=1,
        pricing_version="pricing-v1",
        currency=request.currency,
        customer_id=customer.id,
        customer_snapshot=_customer_snapshot(customer),
        prior_balance_snapshot=prior_balance,
        subtotal=subtotal,
        discount_total=discount_total,
        markup_total=markup_total,
        net_sales=net_sales,
        amount_due_display=stored_money(prior_balance + net_sales),
        created_by_user_id=actor_user_id,
        reason=request.reason,
    )
    db.add(invoice)
    db.flush()
    db.add(revision)
    _write_revision_items(db, tenant_id, revision_id, items)
    _audit_fuzzy_acceptances(db, tenant_id, actor_user_id, invoice_id, items)
    commit_and_restore_tenant_scope(db, tenant_id)
    db.refresh(invoice)
    return _editor_response(db, tenant_id, invoice)


def update_editor_draft(
    db: Session,
    tenant_id: UUID,
    actor_user_id: UUID,
    invoice_id: UUID,
    request: InvoiceEditorDraftRequest,
    *,
    fuzzy_threshold: Decimal,
) -> InvoiceEditorResponse:
    invoice = db.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
        .with_for_update()
    )
    if invoice is None:
        raise AppError(404, "INVOICE_NOT_FOUND", "Invoice was not found")
    if invoice.status is not InvoiceStatus.DRAFT:
        raise AppError(409, "INVOICE_NOT_DRAFT", "Only a draft invoice can be edited here")
    replay = db.scalar(
        select(InvoiceRevision).where(
            InvoiceRevision.tenant_id == tenant_id,
            InvoiceRevision.invoice_id == invoice_id,
            InvoiceRevision.client_command_id == request.client_command_id,
        )
    )
    if replay is not None:
        if invoice.current_revision_id != replay.id:
            raise AppError(409, "STALE_INVOICE_REVISION", "Invoice has a newer revision")
        return _editor_response(db, tenant_id, invoice)
    if request.expected_predecessor_revision_id != invoice.current_revision_id:
        raise AppError(409, "STALE_INVOICE_REVISION", "Invoice has a newer revision")
    predecessor = db.scalar(
        select(InvoiceRevision).where(
            InvoiceRevision.id == invoice.current_revision_id,
            InvoiceRevision.invoice_id == invoice.id,
            InvoiceRevision.tenant_id == tenant_id,
        )
    )
    if predecessor is None:
        raise AppError(409, "INVOICE_REVISION_MISSING", "Invoice revision was not found")
    customer = get_customer(db, tenant_id, request.customer_id)
    items = _prepare_items(
        db, tenant_id, customer, request.currency, request.items, fuzzy_threshold
    )
    subtotal, discount_total, markup_total, net_sales = _totals(
        items, request.invoice_discount_expression, request.invoice_markup_expression
    )
    prior_balance = _prior_balance(db, tenant_id, customer.id, request.currency)
    revision_id = uuid4()
    revision = InvoiceRevision(
        id=revision_id,
        tenant_id=tenant_id,
        invoice_id=invoice_id,
        client_command_id=request.client_command_id,
        predecessor_revision_id=predecessor.id,
        server_revision_number=predecessor.server_revision_number + 1,
        pricing_version="pricing-v1",
        currency=request.currency,
        customer_id=customer.id,
        customer_snapshot=_customer_snapshot(customer),
        prior_balance_snapshot=prior_balance,
        subtotal=subtotal,
        discount_total=discount_total,
        markup_total=markup_total,
        net_sales=net_sales,
        amount_due_display=stored_money(prior_balance + net_sales),
        created_by_user_id=actor_user_id,
        reason=request.reason,
    )
    db.add(revision)
    _write_revision_items(db, tenant_id, revision_id, items)
    _audit_fuzzy_acceptances(db, tenant_id, actor_user_id, invoice_id, items)
    invoice.customer_id = customer.id
    invoice.current_revision_id = revision_id
    invoice.updated_by_user_id = actor_user_id
    try:
        commit_and_restore_tenant_scope(db, tenant_id)
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "STALE_INVOICE_REVISION", "Invoice has a newer revision") from exc
    db.refresh(invoice)
    return _editor_response(db, tenant_id, invoice)


def get_editor_draft(db: Session, tenant_id: UUID, invoice_id: UUID) -> InvoiceEditorResponse:
    invoice = db.scalar(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
    )
    if invoice is None:
        raise AppError(404, "INVOICE_NOT_FOUND", "Invoice was not found")
    return _editor_response(db, tenant_id, invoice)
