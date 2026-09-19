from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import Engine, create_engine, inspect, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from tawzeevo_api.models import (
    Category,
    Customer,
    Invoice,
    InvoiceRevision,
    InvoiceRevisionItem,
    InvoiceStatus,
    ProductPriceBasis,
    SystemUserType,
    Tenant,
    TenantProduct,
    TenantProductCostEntry,
    TenantSupplier,
    User,
)
from tawzeevo_api.security import hash_password


def _financial_context(db: Session, *, suffix: str = "a") -> dict[str, object]:
    owner = User(
        first_name="Financial",
        last_name="Owner",
        email=f"finance-{suffix}@example.com",
        phone=f"+96170123{100 + len(suffix):03d}",
        city="Beirut",
        age=35,
        type=SystemUserType.CLIENT,
        password_hash=hash_password("correct horse battery staple"),
    )
    tenant = Tenant(name=f"Financial tenant {suffix}")
    db.add_all([owner, tenant])
    db.flush()
    category = Category(
        tenant_id=tenant.id,
        name_en="Financial products",
        name_ar="منتجات مالية",
        slug=f"financial-products-{suffix}",
    )
    customer = Customer(
        tenant_id=tenant.id,
        name=f"Customer {suffix}",
        phone=f"+96171123{100 + len(suffix):03d}",
    )
    supplier = TenantSupplier(tenant_id=tenant.id, name="Supplier H")
    db.add_all([category, customer, supplier])
    db.flush()
    product = TenantProduct(
        tenant_id=tenant.id,
        category_id=category.id,
        preferred_supplier_id=supplier.id,
        name="Product X",
        unit_price=Decimal("3.0000"),
        currency="USD",
        price_basis=ProductPriceBasis.PIECE,
        pieces_per_box=12,
    )
    db.add(product)
    db.flush()
    cost = TenantProductCostEntry(
        tenant_id=tenant.id,
        tenant_product_id=product.id,
        supplier_id=supplier.id,
        unit_cost=Decimal("2.0000") if suffix == "a" else Decimal("2.2000"),
        currency="USD",
        cost_basis=ProductPriceBasis.PIECE,
        pieces_per_box=12,
        effective_at=datetime(2026, 8, 26, tzinfo=UTC),
        source_type="MANUAL",
        created_by_user_id=owner.id,
    )
    db.add(cost)
    db.flush()
    return {
        "owner": owner,
        "tenant": tenant,
        "category": category,
        "customer": customer,
        "supplier": supplier,
        "product": product,
        "cost": cost,
    }


@pytest.mark.integration
def test_financial_schema_is_canonical_numeric_and_database_immutable(
    test_engine: Engine,
) -> None:
    inspector = inspect(test_engine)
    invoice_columns = {column["name"]: column for column in inspector.get_columns("invoices")}
    assert "currency" not in invoice_columns
    assert "subtotal" not in invoice_columns
    assert invoice_columns["current_revision_id"]["nullable"] is False

    revision_columns = {
        column["name"]: column for column in inspector.get_columns("invoice_revisions")
    }
    for column_name in (
        "prior_balance_snapshot",
        "subtotal",
        "discount_total",
        "markup_total",
        "net_sales",
        "amount_due_display",
    ):
        assert revision_columns[column_name]["type"].precision == 20
        assert revision_columns[column_name]["type"].scale == 4

    expected_immutable = {
        "tenant_product_cost_entries",
        "invoice_revisions",
        "invoice_revision_items",
        "customer_ledger_entries",
        "payments",
        "payment_allocations",
        "supplier_ledger_entries",
    }
    with test_engine.connect() as connection:
        immutable_tables = set(
            connection.execute(
                text(
                    "SELECT c.relname FROM pg_trigger t "
                    "JOIN pg_class c ON c.oid = t.tgrelid "
                    "WHERE t.tgname = c.relname || '_immutable' AND NOT t.tgisinternal"
                )
            ).scalars()
        )
    assert immutable_tables == expected_immutable


@pytest.mark.integration
def test_supplier_costs_are_tenant_private_append_only_and_independently_priced(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        first = _financial_context(db, suffix="a")
        second = _financial_context(db, suffix="bb")
        db.commit()
        first_cost = first["cost"]
        second_cost = second["cost"]
        assert isinstance(first_cost, TenantProductCostEntry)
        assert isinstance(second_cost, TenantProductCostEntry)
        assert first_cost.unit_cost == Decimal("2.0000")
        assert second_cost.unit_cost == Decimal("2.2000")
        assert first_cost.tenant_id != second_cost.tenant_id

        first_product = first["product"]
        second_supplier = second["supplier"]
        first_owner = first["owner"]
        assert isinstance(first_product, TenantProduct)
        assert isinstance(second_supplier, TenantSupplier)
        assert isinstance(first_owner, User)
        with pytest.raises(IntegrityError), db.begin_nested():
            db.add(
                TenantProductCostEntry(
                    tenant_id=first_cost.tenant_id,
                    tenant_product_id=first_product.id,
                    supplier_id=second_supplier.id,
                    unit_cost=Decimal("1.0000"),
                    currency="USD",
                    cost_basis=ProductPriceBasis.PIECE,
                    effective_at=datetime.now(UTC),
                    source_type="MANUAL",
                    created_by_user_id=first_owner.id,
                )
            )
            db.flush()

        with pytest.raises(DBAPIError), db.begin_nested():
            first_cost.unit_cost = Decimal("9.0000")
            db.flush()
        db.expire(first_cost)
        assert first_cost.unit_cost == Decimal("2.0000")


@pytest.mark.integration
def test_financial_rls_filters_costs_and_blocks_cross_tenant_writes(
    test_engine: Engine,
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        first = _financial_context(db, suffix="a")
        second = _financial_context(db, suffix="bb")
        db.commit()
        first_tenant = first["tenant"]
        second_tenant = second["tenant"]
        first_supplier = first["supplier"]
        first_cost = first["cost"]
        assert isinstance(first_tenant, Tenant)
        assert isinstance(second_tenant, Tenant)
        assert isinstance(first_supplier, TenantSupplier)
        assert isinstance(first_cost, TenantProductCostEntry)

    role_name = f"tawzeevo_financial_rls_{uuid4().hex}"
    with test_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as admin:
        admin.exec_driver_sql(f'CREATE ROLE "{role_name}" NOLOGIN NOSUPERUSER NOBYPASSRLS')
        admin.exec_driver_sql(f'GRANT USAGE ON SCHEMA public TO "{role_name}"')
        admin.exec_driver_sql(
            "GRANT SELECT, INSERT ON tenant_suppliers, tenant_product_cost_entries "
            f'TO "{role_name}"'
        )

    connection = test_engine.connect()
    try:
        with connection.begin():
            connection.exec_driver_sql(f'SET ROLE "{role_name}"')
            connection.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(first_tenant.id)},
            )
            assert set(connection.execute(select(TenantSupplier.id)).scalars()) == {
                first_supplier.id
            }
            assert set(connection.execute(select(TenantProductCostEntry.id)).scalars()) == {
                first_cost.id
            }
            with pytest.raises(DBAPIError), connection.begin_nested():
                connection.execute(
                    text(
                        "INSERT INTO tenant_suppliers (id, tenant_id, name) "
                        "VALUES (:id, :tenant_id, 'Blocked supplier')"
                    ),
                    {"id": uuid4(), "tenant_id": second_tenant.id},
                )
        connection.exec_driver_sql("RESET ROLE")
        connection.commit()
    finally:
        if connection.in_transaction():
            connection.rollback()
        connection.close()
        with test_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as admin:
            admin.exec_driver_sql(f'DROP OWNED BY "{role_name}"')
            admin.exec_driver_sql(f'DROP ROLE "{role_name}"')


@pytest.mark.integration
def test_invoice_order_cardinality_and_cost_snapshot_survive_later_cost_change(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        context = _financial_context(db)
        tenant = context["tenant"]
        customer = context["customer"]
        product = context["product"]
        supplier = context["supplier"]
        owner = context["owner"]
        cost = context["cost"]
        assert isinstance(tenant, Tenant)
        assert isinstance(customer, Customer)
        assert isinstance(product, TenantProduct)
        assert isinstance(supplier, TenantSupplier)
        assert isinstance(owner, User)
        assert isinstance(cost, TenantProductCostEntry)

        order_id = uuid4()
        invoice_id = uuid4()
        revision_id = uuid4()
        invoice = Invoice(
            id=invoice_id,
            tenant_id=tenant.id,
            order_id=order_id,
            customer_id=customer.id,
            status=InvoiceStatus.DRAFT,
            current_revision_id=revision_id,
            created_by_user_id=owner.id,
        )
        revision = InvoiceRevision(
            id=revision_id,
            tenant_id=tenant.id,
            invoice_id=invoice_id,
            client_command_id=uuid4(),
            server_revision_number=1,
            pricing_version="pricing-v1",
            currency="USD",
            customer_id=customer.id,
            customer_snapshot={"id": str(customer.id), "name": customer.name},
            prior_balance_snapshot=Decimal("0.0000"),
            subtotal=Decimal("3.0000"),
            discount_total=Decimal("0.0000"),
            markup_total=Decimal("0.0000"),
            net_sales=Decimal("3.0000"),
            amount_due_display=Decimal("3.0000"),
            created_by_user_id=owner.id,
        )
        item = InvoiceRevisionItem(
            tenant_id=tenant.id,
            invoice_revision_id=revision_id,
            line_number=1,
            tenant_product_id=product.id,
            product_name=product.name,
            barcode="PRODUCT-X",
            media_snapshot={},
            quantity=Decimal("1.0000"),
            price_basis=ProductPriceBasis.PIECE,
            pieces_per_box=12,
            normal_unit_price=Decimal("3.0000"),
            grade_rule_snapshot={},
            effective_unit_price=Decimal("3.0000"),
            line_discount=Decimal("0.0000"),
            line_markup=Decimal("0.0000"),
            line_total=Decimal("3.0000"),
            supplier_id=supplier.id,
            product_cost_entry_id=cost.id,
            unit_cost=cost.unit_cost,
            cost_currency=cost.currency,
            cost_basis=cost.cost_basis,
            cost_pieces_per_box=cost.pieces_per_box,
            cost_source_type=cost.source_type,
        )
        db.add_all([invoice, revision, item])
        db.commit()

        with pytest.raises(IntegrityError), db.begin_nested():
            duplicate_revision_id = uuid4()
            db.add(
                Invoice(
                    tenant_id=tenant.id,
                    order_id=order_id,
                    customer_id=customer.id,
                    status=InvoiceStatus.DRAFT,
                    current_revision_id=duplicate_revision_id,
                )
            )
            db.flush()

        newer_cost = TenantProductCostEntry(
            tenant_id=tenant.id,
            tenant_product_id=product.id,
            supplier_id=supplier.id,
            unit_cost=Decimal("2.2000"),
            currency="USD",
            cost_basis=ProductPriceBasis.PIECE,
            pieces_per_box=12,
            effective_at=datetime(2026, 9, 2, tzinfo=UTC),
            source_type="MANUAL",
            created_by_user_id=owner.id,
        )
        db.add(newer_cost)
        db.commit()
        db.refresh(item)
        assert item.unit_cost == Decimal("2.0000")
        assert newer_cost.unit_cost == Decimal("2.2000")

        with pytest.raises(DBAPIError), db.begin_nested():
            revision.net_sales = Decimal("99.0000")
            db.flush()

        with pytest.raises(IntegrityError), db.begin_nested():
            invalid_item = InvoiceRevisionItem(
                tenant_id=tenant.id,
                invoice_revision_id=revision.id,
                line_number=2,
                product_name="Manual item",
                media_snapshot={},
                quantity=Decimal("1.0000"),
                price_basis=ProductPriceBasis.PIECE,
                normal_unit_price=Decimal("1.0000"),
                grade_rule_snapshot={},
                effective_unit_price=Decimal("1.0000"),
                line_discount=Decimal("0.0000"),
                line_markup=Decimal("0.0000"),
                line_total=Decimal("1.0000"),
                unit_cost=Decimal("0.5000"),
                cost_currency="USD",
                cost_basis=ProductPriceBasis.PIECE,
                cost_source_type="OWNER_OVERRIDE",
                is_cost_override=True,
            )
            db.add(invalid_item)
            db.flush()


@pytest.mark.integration
def test_phase2_draft_rows_upgrade_to_revisions_and_round_trip(
    test_engine: Engine,
) -> None:
    database_name = f"tawzeevo_p3_upgrade_{uuid4().hex[:12]}"
    admin_engine = create_engine(test_engine.url, isolation_level="AUTOCOMMIT")
    target_url = test_engine.url.set(database=database_name)
    target_engine = create_engine(target_url)
    config_path = str(Path(__file__).resolve().parent.parent / "alembic.ini")
    config = Config(config_path)
    config.set_main_option(
        "sqlalchemy.url", target_url.render_as_string(hide_password=False).replace("%", "%%")
    )
    ids = {key: uuid4() for key in ("tenant", "customer", "category", "product", "invoice", "item")}
    try:
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
        command.upgrade(config, "20260826_0007")
        with target_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO tenants (id, name, status) VALUES (:id, 'Legacy tenant', 'ACTIVE')"
                ),
                {"id": ids["tenant"]},
            )
            connection.execute(
                text(
                    "INSERT INTO customers (id, tenant_id, name, phone) "
                    "VALUES (:id, :tenant, 'Legacy customer', '+96170111222')"
                ),
                {"id": ids["customer"], "tenant": ids["tenant"]},
            )
            connection.execute(
                text(
                    "INSERT INTO categories "
                    "(id, tenant_id, name_en, name_ar, slug, display_order, is_active) "
                    "VALUES (:id, :tenant, 'Legacy', 'قديم', 'legacy', 0, true)"
                ),
                {"id": ids["category"], "tenant": ids["tenant"]},
            )
            connection.execute(
                text(
                    "INSERT INTO tenant_products "
                    "(id, tenant_id, category_id, name, is_published, unit_price, currency, "
                    "price_basis) VALUES (:id, :tenant, :category, 'Legacy product', false, "
                    "3.0000, 'USD', 'PIECE')"
                ),
                {
                    "id": ids["product"],
                    "tenant": ids["tenant"],
                    "category": ids["category"],
                },
            )
            connection.execute(
                text(
                    "INSERT INTO invoices (id, tenant_id, customer_id, status, currency, subtotal) "
                    "VALUES (:id, :tenant, :customer, 'DRAFT', 'USD', 6.0000)"
                ),
                {"id": ids["invoice"], "tenant": ids["tenant"], "customer": ids["customer"]},
            )
            connection.execute(
                text(
                    "INSERT INTO invoice_items "
                    "(id, tenant_id, invoice_id, product_id, product_name, barcode, quantity, "
                    "price_basis, unit_price, line_total, price_source) VALUES "
                    "(:id, :tenant, :invoice, :product, 'Legacy product', 'LEGACY-X', 2.0000, "
                    "'PIECE', 3.0000, 6.0000, 'NORMAL')"
                ),
                {
                    "id": ids["item"],
                    "tenant": ids["tenant"],
                    "invoice": ids["invoice"],
                    "product": ids["product"],
                },
            )

        command.upgrade(config, "20260826_0008")
        with target_engine.connect() as connection:
            migrated = connection.execute(
                text(
                    "SELECT i.current_revision_id, r.subtotal, item.effective_unit_price "
                    "FROM invoices i JOIN invoice_revisions r ON r.id = i.current_revision_id "
                    "JOIN invoice_revision_items item ON item.invoice_revision_id = r.id "
                    "WHERE i.id = :invoice"
                ),
                {"invoice": ids["invoice"]},
            ).one()
            assert migrated.current_revision_id is not None
            assert migrated.subtotal == Decimal("6.0000")
            assert migrated.effective_unit_price == Decimal("3.0000")
            assert "invoice_items" not in inspect(connection).get_table_names()

        command.upgrade(config, "head")
        with target_engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT line_number FROM invoice_revision_items WHERE id = :item"),
                    {"item": ids["item"]},
                ).scalar_one()
                == 1
            )

        command.downgrade(config, "20260826_0007")
        with target_engine.connect() as connection:
            restored = connection.execute(
                text(
                    "SELECT i.subtotal, item.unit_price FROM invoices i "
                    "JOIN invoice_items item ON item.invoice_id = i.id WHERE i.id = :invoice"
                ),
                {"invoice": ids["invoice"]},
            ).one()
            assert restored.subtotal == Decimal("6.0000")
            assert restored.unit_price == Decimal("3.0000")
        command.upgrade(config, "head")
    finally:
        target_engine.dispose()
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{database_name}"')
        admin_engine.dispose()
