"""Deterministic owner-intelligence demo history for one dedicated, empty tenant (D-089).

Purpose: fill a demo business with about six months of synthetic, ledger-consistent trading so
every owner intelligence view shows meaningful output: daily priorities, inactivity risk,
anomalies, cash-flow position and ageing, and the copilot tools that read them. Every customer,
phone number, product and amount here is invented; no real person or business is represented.

How the history is written: every business record goes through the same service functions the
API routes call (customers, catalog, suppliers and costs, invoice draft + confirm + cancel,
receipts, receipt reversals, refunds, supplier purchases, supplier payments, delivery tasks and
the overdue-threshold setting). Nothing financial is hand-inserted. Because the financial tables
are immutable at the database (their timestamps can never be shifted afterwards), each record is
created *at* its historical moment instead: a simulated clock is active while its service call
runs, so every row that call writes carries the same instant - the services' own `now()` reads
(confirmation, cancellation, reversal) and the database-default timestamps (`created_at`,
`recorded_at`, `occurred_at`, `updated_at`), which are stamped explicitly on insert/update. The
clock patches module globals, so this command must run in its own process, never inside the API.

Guards (all mandatory): the tenant must exist and be owned by the given owner (the same tenant
context checks as the API); `--confirm-tenant-name` must equal the tenant's exact name; the tenant
must have no customer, invoice or payment yet; settings that indicate production are refused
unless `--allow-production` is passed. The whole seed is one database transaction: the service
commits become savepoints of an outer transaction that commits only when everything succeeded.

Reruns on a fresh tenant with the same `--as-of` date and `--seed` produce the same shape.

Example:
    python -m tawzeevo_api.cli.seed_intelligence_demo --owner-email owner@example.com \\
        --tenant-id <uuid> --confirm-tenant-name "Demo Wholesale"
"""

from __future__ import annotations

import argparse
import random
from collections import Counter
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from decimal import Decimal
from types import ModuleType
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import DateTime, Engine, event, func, inspect, select
from sqlalchemy.orm import Session, UOWTransaction

from tawzeevo_api.config import get_settings
from tawzeevo_api.dependencies import resolve_tenant_context
from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    AuditEvent,
    Customer,
    CustomerGrade,
    CustomerLedgerEntry,
    Invoice,
    Payment,
    ProductPriceBasis,
    TenantRole,
    User,
)
from tawzeevo_api.repositories.tenancy import set_tenant_scope
from tawzeevo_api.schemas.cash_van import (
    CategoryCreateRequest,
    CustomerCreateRequest,
    TenantProductCreateRequest,
)
from tawzeevo_api.schemas.delivery import TaskCreateRequest
from tawzeevo_api.schemas.invoice_editor import (
    InvoiceCancelRequest,
    InvoiceEditorDraftRequest,
    InvoiceEditorItemRequest,
    InvoiceEditorResponse,
)
from tawzeevo_api.schemas.payments import (
    CustomerReceiptRequest,
    CustomerRefundRequest,
    PaymentReversalRequest,
)
from tawzeevo_api.schemas.supplier_ledger import SupplierPaymentRequest
from tawzeevo_api.schemas.supplier_purchases import PurchaseCreateRequest, PurchaseLineRequest
from tawzeevo_api.schemas.suppliers import ProductCostEntryCreateRequest, SupplierCreateRequest
from tawzeevo_api.services import (
    cash_van,
    customer_ledger,
    delivery,
    invoice_editor,
    invoice_finance,
    payments,
    supplier_ledger,
    supplier_purchases,
    suppliers,
)
from tawzeevo_api.services.analytics import TENANT_TZ
from tawzeevo_api.services.invoice_editor import money

DEFAULT_RNG_SEED = 89
OVERDUE_THRESHOLD_DAYS = 30
FUZZY_THRESHOLD = Decimal("0.7000")
CENT = Decimal("0.01")

# Service modules whose own `datetime.now()` reads are served by the simulated clock.
_CLOCK_ATTRIBUTE = "datetime"
_CLOCK_MODULES: tuple[ModuleType, ...] = (
    cash_van,
    customer_ledger,
    delivery,
    invoice_editor,
    invoice_finance,
    payments,
    supplier_ledger,
    supplier_purchases,
    suppliers,
)

# key, name, Arabic name, unit price, supplier cost (all per piece)
USD_PRODUCTS: tuple[tuple[str, str, str, str, str], ...] = (
    ("water", "Cedar Spring Water 6x1.5L", "مياه الأرز ٦×١.٥ ل", "3.2500", "2.1000"),
    ("olive_oil", "Mount Hermon Olive Oil 1L", "زيت زيتون حرمون ١ ل", "9.5000", "7.9000"),
    ("lentils", "Bekaa Red Lentils 1kg", "عدس أحمر بقاعي ١ كغ", "2.7500", "1.8500"),
    ("labneh", "Chtaura Labneh 500g", "لبنة شتورة ٥٠٠ غ", "4.2500", "3.1000"),
    ("coffee", "Cardamom Coffee 250g", "قهوة بالهال ٢٥٠ غ", "6.5000", "4.4000"),
    ("zaatar", "Za'atar Mix 500g", "زعتر ٥٠٠ غ", "5.0000", "3.3000"),
    ("tahini", "Tahini 800g", "طحينة ٨٠٠ غ", "5.7500", "4.0000"),
    ("sunflower", "Sunflower Oil 1.8L", "زيت دوار الشمس ١.٨ ل", "6.2500", "4.9000"),
)
LBP_PRODUCTS: tuple[tuple[str, str, str, str, str], ...] = (
    ("pita", "Fresh Pita Bread Bag", "خبز عربي طازج", "90000.0000", "60000.0000"),
    ("manakish", "Manakish Dough Tray", "صينية عجينة مناقيش", "450000.0000", "300000.0000"),
)

# key, name, synthetic phone, grade, address
CUSTOMERS: tuple[tuple[str, str, str, CustomerGrade | None, str], ...] = (
    ("mount_lebanon", "Mount Lebanon Market", "+96171000101", CustomerGrade.A, "Baabda"),
    ("byblos", "Byblos Grocery", "+96171000102", CustomerGrade.B, "Jbeil"),
    ("tyre", "Tyre Fresh Foods", "+96171000103", CustomerGrade.B, "Tyre"),
    ("zahle", "Zahle Wholesale", "+96171000104", CustomerGrade.A, "Zahle"),
    ("batroun", "Batroun Bakery", "+96171000105", CustomerGrade.B_PLUS, "Batroun"),
    ("jounieh", "Jounieh Minimart", "+96171000106", CustomerGrade.B, "Jounieh"),
    ("saida", "Saida Corner Shop", "+96171000107", None, "Saida"),
    ("hamra", "Hamra Café", "+96171000108", CustomerGrade.B, "Hamra, Beirut"),
    ("tripoli", "Tripoli Traders", "+96171000109", None, "Tripoli"),
    ("arz", "دكان الأرز", "+96171000110", CustomerGrade.B, "Aley"),
)

EXPECTED_OUTCOMES: tuple[str, ...] = (
    "Priorities USD: Tyre Fresh Foods HIGH, COLLECT_OVERDUE (OLD_OVERDUE_BALANCE, ~76 days)",
    "Priorities USD: Byblos Grocery HIGH, REACTIVATE_CUSTOMER (LAPSED)",
    "Priorities USD: Zahle Wholesale MEDIUM, COLLECT_OVERDUE (OVERDUE_BALANCE)",
    "Priorities USD: Batroun Bakery MEDIUM, CHECK_ACTIVITY_DECLINE (ACTIVITY_DOWN_VS_90D)",
    "Priorities USD: Jounieh Minimart LOW, REVIEW_RECENT_FRICTION (cancellations, reversal)",
    "Priorities LBP: Hamra Café LOW, FOLLOW_UP_BALANCE (outstanding LBP balance)",
    "Inactivity: Byblos LAPSED; Tyre and Batroun WATCH; Saida INSUFFICIENT_HISTORY; "
    "Mount Lebanon Market NORMAL",
    "Anomalies USD: SALES_PERIOD_HIGH, REFUND_SPIKE, CUSTOMER_INVOICE_VALUE_HIGH (Tripoli), "
    "BACKDATED_RECEIPT_LARGE (Batroun), OVERDUE_THRESHOLD_CROSSED (Zahle), "
    "SUPPLIER_PAYABLE_JUMP, LINE_PRICE_BELOW_SNAPSHOT_COST (Jounieh)",
    "Cash flow USD: overdue receivables (Tyre, Zahle), ageing 0-30 / 31-60 / 61-90, "
    "4 planned delivery collections; LBP reported separately with 1 planned collection",
)


@dataclass(frozen=True)
class IntelligenceDemoSeedResult:
    tenant_id: UUID
    tenant_name: str
    as_of: datetime
    rng_seed: int
    counts: dict[str, int]
    expected_outcomes: tuple[str, ...] = EXPECTED_OUTCOMES


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description=(
            "Fill one dedicated, empty demo tenant with ~6 months of synthetic, ledger-consistent "
            "history for the owner intelligence views (D-089)."
        )
    )
    command.add_argument("--owner-email", required=True)
    command.add_argument("--tenant-id", required=True, type=UUID)
    command.add_argument(
        "--confirm-tenant-name",
        required=True,
        help="The tenant's exact name, as a safety confirmation.",
    )
    command.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=None,
        help="History ends the day before this Asia/Beirut date (default: today).",
    )
    command.add_argument("--seed", type=int, default=DEFAULT_RNG_SEED)
    command.add_argument(
        "--allow-production",
        action="store_true",
        help="Required when settings indicate production.",
    )
    return command


# ---------------------------------------------------------------------------------------------
# Simulated clock
# ---------------------------------------------------------------------------------------------


def _frozen_datetime(moment: datetime) -> type[datetime]:
    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> _FrozenDatetime:
            value = moment.astimezone(tz) if tz is not None else moment.replace(tzinfo=None)
            return cls.combine(value.date(), value.timetz())

    return _FrozenDatetime


def _stamp_timestamps(moment: datetime) -> Callable[[Session, UOWTransaction, Any], None]:
    """Give inserted rows' database-default timestamps, and updated rows' on-update timestamps,
    the simulated instant instead of the database clock."""

    def stamp(session: Session, _context: UOWTransaction, _instances: Any) -> None:
        for obj in session.new:
            for column in inspect(obj).mapper.columns:
                if (
                    column.server_default is not None
                    and isinstance(column.type, DateTime)
                    and column.key is not None
                    and getattr(obj, column.key, None) is None
                ):
                    setattr(obj, column.key, moment)
        for obj in session.dirty:
            if not session.is_modified(obj):
                continue
            for column in inspect(obj).mapper.columns:
                if column.onupdate is not None and isinstance(column.type, DateTime):
                    setattr(obj, str(column.key), moment)

    return stamp


@contextmanager
def _simulated_clock(db: Session, moment: datetime) -> Iterator[None]:
    frozen = _frozen_datetime(moment)
    patched: list[ModuleType] = []
    listener = _stamp_timestamps(moment)
    try:
        for module in _CLOCK_MODULES:
            if getattr(module, _CLOCK_ATTRIBUTE, None) is not datetime:
                raise RuntimeError(f"{module.__name__} does not read the clock as expected")
            setattr(module, _CLOCK_ATTRIBUTE, frozen)
            patched.append(module)
        event.listen(db, "before_flush", listener)
        yield
    finally:
        if event.contains(db, "before_flush", listener):
            event.remove(db, "before_flush", listener)
        for module in patched:
            setattr(module, _CLOCK_ATTRIBUTE, datetime)


# ---------------------------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------------------------


def _local_midnight(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=TENANT_TZ).astimezone(UTC)


def _resolve_as_of(as_of_date: date | None) -> datetime:
    today = datetime.now(UTC).astimezone(TENANT_TZ).date()
    day = as_of_date or today
    if day > today:
        raise AppError(422, "AS_OF_IN_FUTURE", "The as-of date cannot be later than today")
    return _local_midnight(day)


def _guard(
    db: Session,
    *,
    owner_email: str,
    tenant_id: UUID,
    confirm_tenant_name: str,
    app_env: str,
    allow_production: bool,
) -> tuple[UUID, UUID, str]:
    if app_env.strip().lower() == "production" and not allow_production:
        raise AppError(
            409,
            "PRODUCTION_REFUSED",
            "Settings indicate production; pass --allow-production to seed a dedicated demo "
            "tenant there",
        )
    owner = db.scalar(
        select(User).where(
            User.email == owner_email.strip().lower(),
            User.is_deleted.is_(False),
        )
    )
    if owner is None:
        raise AppError(404, "OWNER_NOT_FOUND", "An active owner account was not found")
    context = resolve_tenant_context(db, owner, tenant_id)
    if context.membership.role is not TenantRole.OWNER:
        raise AppError(403, "TENANT_OWNER_REQUIRED", "Tenant owner access is required")
    if context.tenant.name != confirm_tenant_name:
        raise AppError(
            409,
            "TENANT_NAME_MISMATCH",
            "--confirm-tenant-name does not match the tenant's exact name",
        )
    set_tenant_scope(db, tenant_id)
    existing = {
        "customers": db.scalar(
            select(func.count()).select_from(Customer).where(Customer.tenant_id == tenant_id)
        ),
        "invoices": db.scalar(
            select(func.count()).select_from(Invoice).where(Invoice.tenant_id == tenant_id)
        ),
        "payments": db.scalar(
            select(func.count()).select_from(Payment).where(Payment.tenant_id == tenant_id)
        ),
    }
    if any(existing.values()):
        found = ", ".join(f"{count} {name}" for name, count in existing.items() if count)
        raise AppError(
            409,
            "TENANT_NOT_EMPTY",
            f"The tenant already has business data ({found}); use a dedicated empty tenant",
        )
    return owner.id, context.membership.id, context.tenant.name


# ---------------------------------------------------------------------------------------------
# The history
# ---------------------------------------------------------------------------------------------

Line = tuple[str, int, str]  # product key, quantity, line discount expression


@dataclass
class _Seeder:
    db: Session
    tenant_id: UUID
    actor_id: UUID
    membership_id: UUID
    today: date
    rng: random.Random
    products: dict[str, UUID] = field(default_factory=dict)
    customers: dict[str, UUID] = field(default_factory=dict)
    suppliers: dict[str, UUID] = field(default_factory=dict)
    invoices: dict[str, InvoiceEditorResponse] = field(default_factory=dict)
    receipts: dict[str, UUID] = field(default_factory=dict)
    purchases: dict[str, Decimal] = field(default_factory=dict)
    counts: Counter[str] = field(default_factory=Counter)
    _events: list[tuple[datetime, int, Callable[[], None]]] = field(default_factory=list)
    _keys: int = 0

    # ---- time and identity
    def moment(self, days_ago: int, hour: int, minute: int | None = None) -> datetime:
        minute = self.rng.randrange(0, 50) if minute is None else minute
        local = datetime.combine(
            self.today - timedelta(days=days_ago), time(hour, minute), tzinfo=TENANT_TZ
        )
        return local.astimezone(UTC)

    def key(self) -> UUID:
        self._keys += 1
        return uuid5(NAMESPACE_URL, f"tawzeevo:intelligence-demo:{self.tenant_id}:{self._keys}")

    def at(self, when: datetime, action: Callable[[], None]) -> None:
        self._events.append((when, len(self._events), action))

    def run(self) -> None:
        for when, _order, action in sorted(self._events, key=lambda item: item[:2]):
            with _simulated_clock(self.db, when):
                action()
        self._events.clear()

    def balance(self, customer: str, currency: str) -> Decimal:
        total = self.db.scalar(
            select(func.coalesce(func.sum(CustomerLedgerEntry.signed_amount), 0)).where(
                CustomerLedgerEntry.tenant_id == self.tenant_id,
                CustomerLedgerEntry.customer_id == self.customers[customer],
                CustomerLedgerEntry.currency == currency,
            )
        )
        return money(Decimal(total or 0))

    def net(self, label: str) -> Decimal:
        return money(self.invoices[label].net_sales)

    # ---- setup
    def setup(self, when: datetime) -> None:
        with _simulated_clock(self.db, when):
            customer_ledger.set_overdue_threshold(
                self.db, self.tenant_id, self.actor_id, OVERDUE_THRESHOLD_DAYS
            )
            for supplier_key, name in (
                ("usd", "Bekaa Distribution Co."),
                ("lbp", "Beirut Bakery Supplies"),
            ):
                self.suppliers[supplier_key] = suppliers.create_supplier(
                    self.db, self.tenant_id, self.actor_id, SupplierCreateRequest(name=name)
                ).id
                self.counts["suppliers"] += 1
            for slug, name_en, name_ar, currency, catalog in (
                ("intelligence-demo-pantry", "Pantry", "مؤونة", "USD", USD_PRODUCTS),
                ("intelligence-demo-bakery", "Bakery", "مخبوزات", "LBP", LBP_PRODUCTS),
            ):
                category = cash_van.create_category(
                    self.db,
                    self.tenant_id,
                    CategoryCreateRequest(name_en=name_en, name_ar=name_ar, slug=slug),
                )
                for product_key, name, name_ar_product, price, cost in catalog:
                    product = cash_van.create_product(
                        self.db,
                        self.tenant_id,
                        TenantProductCreateRequest(
                            category_id=category.id,
                            name=name,
                            name_ar=name_ar_product,
                            barcode=f"TZW-INTEL-{len(self.products) + 1:03d}",
                            unit_price=Decimal(price),
                            currency=currency,
                            price_basis=ProductPriceBasis.PIECE,
                            pieces_per_box=12,
                        ),
                    )
                    self.products[product_key] = product.id
                    self.counts["products"] += 1
                    suppliers.append_product_cost(
                        self.db,
                        self.tenant_id,
                        self.actor_id,
                        product.id,
                        ProductCostEntryCreateRequest(
                            supplier_id=self.suppliers[currency.lower()],
                            unit_cost=Decimal(cost),
                            currency=currency,
                            cost_basis=ProductPriceBasis.PIECE,
                            effective_at=when,
                            notes="Synthetic demo cost",
                        ),
                    )
                    self.counts["product_costs"] += 1
            for customer_key, name, phone, grade, address in CUSTOMERS:
                self.customers[customer_key] = cash_van.create_customer(
                    self.db,
                    self.tenant_id,
                    CustomerCreateRequest(
                        name=name, phone=phone, grade=grade, address=f"{address} (synthetic)"
                    ),
                ).id
                self.counts["customers"] += 1

    # ---- scheduled business events
    def basket(self, choices: Sequence[str], count: int, low: int, high: int) -> list[Line]:
        picked = self.rng.sample(list(choices), count)
        return [(product, self.rng.randint(low, high), "0") for product in picked]

    def invoice(
        self, label: str, customer: str, days_ago: int, lines: list[Line], currency: str = "USD"
    ) -> None:
        def action() -> None:
            draft = invoice_editor.create_editor_draft(
                self.db,
                self.tenant_id,
                self.actor_id,
                InvoiceEditorDraftRequest(
                    client_command_id=self.key(),
                    customer_id=self.customers[customer],
                    currency=currency,
                    items=[
                        InvoiceEditorItemRequest(
                            product_id=self.products[product],
                            quantity_expression=str(quantity),
                            price_basis=ProductPriceBasis.PIECE,
                            line_discount_expression=discount,
                        )
                        for product, quantity, discount in lines
                    ],
                ),
                fuzzy_threshold=FUZZY_THRESHOLD,
            )
            self.invoices[label] = invoice_finance.confirm_invoice(
                self.db, self.tenant_id, self.actor_id, draft.id, draft.current_revision_id
            )
            self.counts["invoices_confirmed"] += 1

        self.at(self.moment(days_ago, 10), action)

    def cancel(self, label: str, days_ago: int, reason: str) -> None:
        def action() -> None:
            invoice_finance.cancel_invoice(
                self.db,
                self.tenant_id,
                self.actor_id,
                self.invoices[label].id,
                InvoiceCancelRequest(idempotency_key=self.key(), reason=reason),
            )
            self.counts["invoices_cancelled"] += 1

        self.at(self.moment(days_ago, 11), action)

    def receipt(
        self,
        customer: str,
        days_ago: int,
        amount: Callable[[], Decimal],
        *,
        currency: str = "USD",
        paid_days_ago: int | None = None,
        label: str | None = None,
        method: str = "CASH",
    ) -> None:
        recorded = self.moment(days_ago, 16)
        paid = recorded if paid_days_ago is None else self.moment(paid_days_ago, 16)

        def action() -> None:
            value = amount().quantize(CENT)
            if value <= 0:
                return
            response = payments.record_customer_receipt(
                self.db,
                self.tenant_id,
                self.actor_id,
                CustomerReceiptRequest(
                    idempotency_key=self.key(),
                    customer_id=self.customers[customer],
                    amount=value,
                    currency=currency,
                    method=method,
                    paid_at=paid,
                ),
            )
            if label is not None:
                self.receipts[label] = response.id
            self.counts["customer_receipts"] += 1

        self.at(recorded, action)

    def reverse(self, label: str, days_ago: int, reason: str) -> None:
        def action() -> None:
            payments.reverse_customer_receipt(
                self.db,
                self.tenant_id,
                self.actor_id,
                self.receipts[label],
                PaymentReversalRequest(idempotency_key=self.key(), reason=reason),
            )
            self.counts["receipt_reversals"] += 1

        self.at(self.moment(days_ago, 15), action)

    def refund(self, customer: str, days_ago: int, amount: str) -> None:
        when = self.moment(days_ago, 17)

        def action() -> None:
            payments.record_customer_refund(
                self.db,
                self.tenant_id,
                self.actor_id,
                CustomerRefundRequest(
                    idempotency_key=self.key(),
                    customer_id=self.customers[customer],
                    amount=Decimal(amount),
                    currency="USD",
                    method="CASH",
                    paid_at=when,
                    notes="Returned overpayment",
                ),
            )
            self.counts["customer_refunds"] += 1

        self.at(when, action)

    def purchase(self, label: str, days_ago: int, lines: list[tuple[str, int]]) -> None:
        when = self.moment(days_ago, 8)
        costs = {key: Decimal(cost) for key, _n, _a, _p, cost in USD_PRODUCTS}
        items = [
            PurchaseLineRequest(
                product_id=self.products[product],
                quantity=Decimal(quantity),
                unit_cost=(costs[product] * Decimal(self.rng.randint(97, 103)) / 100).quantize(
                    CENT
                ),
            )
            for product, quantity in lines
        ]

        def action() -> None:
            purchase, _replayed = supplier_purchases.record_purchase(
                self.db,
                self.tenant_id,
                self.actor_id,
                PurchaseCreateRequest(
                    idempotency_key=self.key(),
                    supplier_id=self.suppliers["usd"],
                    currency="USD",
                    purchased_at=when,
                    items=items,
                ),
            )
            self.purchases[label] = money(purchase.total_amount)
            self.counts["supplier_purchases"] += 1

        self.at(when, action)

    def supplier_payment(self, label: str, days_ago: int) -> None:
        when = self.moment(days_ago, 12)

        def action() -> None:
            supplier_ledger.record_supplier_payment(
                self.db,
                self.tenant_id,
                self.actor_id,
                SupplierPaymentRequest(
                    idempotency_key=self.key(),
                    supplier_id=self.suppliers["usd"],
                    currency="USD",
                    amount=self.purchases[label],
                    paid_at=when,
                    method="BANK_TRANSFER",
                ),
            )
            self.counts["supplier_payments"] += 1

        self.at(when, action)

    def delivery_task(self, label: str, days_ahead: int) -> None:
        def action() -> None:
            delivery.create_task(
                self.db,
                self.tenant_id,
                self.actor_id,
                TaskCreateRequest(
                    invoice_id=self.invoices[label].id,
                    assigned_membership_id=self.membership_id,
                    delivery_date=self.today + timedelta(days=days_ahead),
                    notes="Collect on delivery (synthetic demo)",
                ),
            )
            self.counts["delivery_tasks"] += 1

        self.at(self.moment(1, 18), action)

    # ---- the ten customers, the supplier and the planned deliveries
    def plan(self) -> None:
        def pay_invoice(customer: str, label: str, days_ago: int, **extra: Any) -> None:
            self.receipt(customer, days_ago, lambda: self.net(label), **extra)

        # 1. Mount Lebanon Market: weekly for six months, pays within four days. Two overpayments
        # are handed back (one refund in the baseline, two refunds this week: REFUND_SPIKE).
        for days in range(177, 1, -7):
            label = f"mount_lebanon:{days}"
            self.invoice(
                label,
                "mount_lebanon",
                days,
                self.basket(("water", "lentils", "labneh", "coffee"), 3, 7, 12),
            )
            if days == 44:
                self.receipt(
                    "mount_lebanon",
                    40,
                    lambda: self.balance("mount_lebanon", "USD") + Decimal("25"),
                )
                self.refund("mount_lebanon", 39, "25.0000")
            elif days == 9:
                self.receipt(
                    "mount_lebanon",
                    6,
                    lambda: self.balance("mount_lebanon", "USD") + Decimal("140"),
                )
                self.refund("mount_lebanon", 5, "80.0000")
                self.refund("mount_lebanon", 4, "60.0000")
            elif days > 2:
                pay_invoice("mount_lebanon", label, days - 4)

        # 2. Byblos Grocery: every ten days until fifty days ago, always paid, then silence.
        for days in range(170, 49, -10):
            label = f"byblos:{days}"
            self.invoice(
                label, "byblos", days, self.basket(("water", "tahini", "zaatar"), 3, 8, 14)
            )
            pay_invoice("byblos", label, days - 4)

        # 3. Tyre Fresh Foods: every eight days; stopped paying 76 days ago (two token payments,
        # one of them a returned cheque), last purchase 12 days ago.
        for days in range(180, 11, -8):
            label = f"tyre:{days}"
            self.invoice(
                label, "tyre", days, self.basket(("labneh", "olive_oil", "sunflower"), 3, 6, 10)
            )
            if days >= 84:
                pay_invoice("tyre", label, days - 5)
        self.receipt("tyre", 40, lambda: Decimal("60"))
        self.receipt("tyre", 20, lambda: Decimal("50"), label="tyre:cheque", method="CHEQUE")
        self.reverse("tyre:cheque", 15, "Cheque returned unpaid")

        # 4. Zahle Wholesale: every nine days; paid through the invoice of 43 days ago, so the
        # oldest unpaid invoice (34 days) crossed the 30-day threshold this week.
        for days in range(169, 6, -9):
            label = f"zahle:{days}"
            self.invoice(
                label,
                "zahle",
                days,
                self.basket(("sunflower", "lentils", "olive_oil", "water"), 3, 8, 12),
            )
            if days >= 43:
                pay_invoice("zahle", label, days - 4)

        # 5. Batroun Bakery: large orders every six days until a month ago, then one small order.
        # The last month of invoices was settled by a cheque dated 22 days ago but recorded two
        # days ago (BACKDATED_RECEIPT_LARGE).
        for days in range(163, 30, -6):
            label = f"batroun:{days}"
            self.invoice(
                label,
                "batroun",
                days,
                self.basket(("zaatar", "sunflower", "tahini"), 3, 12, 16),
            )
            if days >= 55:
                pay_invoice("batroun", label, days - 3)
        self.invoice("batroun:8", "batroun", 8, [("zaatar", 4, "0")])
        pay_invoice("batroun", "batroun:8", 6)
        self.receipt(
            "batroun",
            2,
            lambda: self.balance("batroun", "USD"),
            paid_days_ago=22,
            method="CHEQUE",
        )

        # 6. Jounieh Minimart: weekly and fully paid, with two recent cancelled orders and a
        # returned cheque; its latest invoice has a promotional line sold below cost.
        for days in range(171, 3, -7):
            label = f"jounieh:{days}"
            self.invoice(
                label, "jounieh", days, self.basket(("water", "coffee", "labneh"), 3, 5, 9)
            )
            if days == 10:
                self.receipt(
                    "jounieh",
                    8,
                    lambda: self.net("jounieh:10"),
                    label="jounieh:cheque",
                    method="CHEQUE",
                )
                self.reverse("jounieh:cheque", 6, "Cheque returned unpaid")
                pay_invoice("jounieh", label, 5)
            else:
                pay_invoice("jounieh", label, days - 4)
        self.invoice("jounieh:3", "jounieh", 3, [("olive_oil", 12, "24"), ("water", 6, "0")])
        pay_invoice("jounieh", "jounieh:3", 1)
        for days in (19, 12):
            label = f"jounieh:cancelled:{days}"
            self.invoice(label, "jounieh", days, self.basket(("water", "labneh"), 2, 4, 8))
            self.cancel(label, days - 1, "Customer changed the order")

        # 7. Saida Corner Shop: only two invoices, the latest still open.
        self.invoice("saida:40", "saida", 40, self.basket(("water", "lentils"), 2, 5, 8))
        pay_invoice("saida", "saida:40", 36)
        self.invoice("saida:15", "saida", 15, self.basket(("water", "lentils"), 2, 5, 8))

        # 8. Hamra Café (LBP): weekly bakery orders; the last four are unpaid.
        for days in range(170, 1, -7):
            label = f"hamra:{days}"
            self.invoice(
                label,
                "hamra",
                days,
                [
                    ("pita", self.rng.randint(20, 36), "0"),
                    ("manakish", self.rng.randint(3, 5), "0"),
                ],
                currency="LBP",
            )
            if days >= 30:
                pay_invoice("hamra", label, days - 3, currency="LBP")

        # 9. Tripoli Traders: small orders every twelve days, then one very large order.
        for days in range(146, 13, -12):
            label = f"tripoli:{days}"
            self.invoice(label, "tripoli", days, [("water", self.rng.randint(5, 9), "0")])
            pay_invoice("tripoli", label, days - 3)
        self.invoice("tripoli:2", "tripoli", 2, [("olive_oil", 150, "0"), ("sunflower", 120, "0")])

        # 10. دكان الأرز: every eight days; paid in full until a month ago, then part-paid.
        for days in range(172, 3, -8):
            label = f"arz:{days}"
            self.invoice(
                label,
                "arz",
                days,
                self.basket(("lentils", "zaatar", "tahini", "coffee"), 3, 6, 11),
            )
            if days >= 28:
                pay_invoice("arz", label, days - 3)
            elif days == 20:
                self.receipt("arz", 17, lambda: self.net("arz:20") * Decimal("0.6"))

        # Supplier: steady weekly purchases, each paid five days later; one large order this week.
        for days in range(170, 8, -7):
            label = f"purchase:{days}"
            self.purchase(
                label,
                days,
                [
                    (product, self.rng.randint(40, 70))
                    for product in self.rng.sample(
                        ("water", "lentils", "labneh", "coffee", "zaatar", "tahini"), 3
                    )
                ],
            )
            self.supplier_payment(label, days - 5)
        self.purchase("purchase:2", 2, [("olive_oil", 300), ("sunflower", 250), ("water", 200)])

        # Planned collections: open delivery tasks for unpaid invoices in the next days.
        for label, days_ahead in (
            ("tripoli:2", 1),
            ("zahle:7", 2),
            ("arz:4", 3),
            ("tyre:12", 4),
            ("hamra:2", 1),
        ):
            self.delivery_task(label, days_ahead)


def seed_intelligence_demo(
    db: Session,
    *,
    owner_email: str,
    tenant_id: UUID,
    confirm_tenant_name: str,
    as_of_date: date | None = None,
    rng_seed: int = DEFAULT_RNG_SEED,
    allow_production: bool = False,
    app_env: str | None = None,
) -> IntelligenceDemoSeedResult:
    """Write the demo history through the service layer. The service calls commit; run this via
    `seed_atomically` (or inside any outer transaction) to keep it all-or-nothing."""
    actor_id, membership_id, tenant_name = _guard(
        db,
        owner_email=owner_email,
        tenant_id=tenant_id,
        confirm_tenant_name=confirm_tenant_name,
        app_env=get_settings().app_env if app_env is None else app_env,
        allow_production=allow_production,
    )
    as_of = _resolve_as_of(as_of_date)
    seeder = _Seeder(
        db=db,
        tenant_id=tenant_id,
        actor_id=actor_id,
        membership_id=membership_id,
        today=as_of.astimezone(TENANT_TZ).date(),
        rng=random.Random(rng_seed),
    )
    seeder.setup(seeder.moment(186, 9, 0))
    seeder.plan()
    seeder.run()
    set_tenant_scope(db, tenant_id)
    counts = dict(sorted(seeder.counts.items()))
    # Provenance at the real clock: the audit trail says this history is synthetic.
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor_id,
            action="intelligence_demo_history_seeded",
            entity_type="tenant",
            entity_id=tenant_id,
            details={
                "synthetic": True,
                "as_of": as_of.isoformat(),
                "rng_seed": rng_seed,
                "counts": counts,
            },
        )
    )
    db.commit()
    return IntelligenceDemoSeedResult(
        tenant_id=tenant_id,
        tenant_name=tenant_name,
        as_of=as_of,
        rng_seed=rng_seed,
        counts=counts,
    )


def seed_atomically(engine: Engine, **kwargs: Any) -> IntelligenceDemoSeedResult:
    """One outer transaction: every service commit becomes a savepoint, and nothing is kept
    unless the whole seed succeeds."""
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            with Session(
                bind=connection,
                join_transaction_mode="create_savepoint",
                autoflush=False,
                expire_on_commit=False,
            ) as db:
                result = seed_intelligence_demo(db, **kwargs)
            transaction.commit()
        except BaseException:
            transaction.rollback()
            raise
    return result


def _summary(result: IntelligenceDemoSeedResult) -> str:
    lines = [
        f"Seeded synthetic intelligence demo history for tenant {result.tenant_id} "
        f"({result.tenant_name}); history ends before "
        f"{result.as_of.astimezone(TENANT_TZ).date().isoformat()} Asia/Beirut, "
        f"seed {result.rng_seed}.",
        "Records: " + ", ".join(f"{name} {count}" for name, count in result.counts.items()),
        "Expected on the owner intelligence views (viewed on the as-of date):",
        *(f"- {outcome}" for outcome in result.expected_outcomes),
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None, engine: Engine | None = None) -> int:
    arguments = parser().parse_args(argv)
    if engine is None:
        from tawzeevo_api.database import engine as default_engine

        engine = default_engine
    try:
        result = seed_atomically(
            engine,
            owner_email=arguments.owner_email,
            tenant_id=arguments.tenant_id,
            confirm_tenant_name=arguments.confirm_tenant_name,
            as_of_date=arguments.as_of,
            rng_seed=arguments.seed,
            allow_production=arguments.allow_production,
        )
    except AppError as exc:
        print(f"Demo history was not created: {exc.code} - {exc.message}")
        return 1
    print(_summary(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
