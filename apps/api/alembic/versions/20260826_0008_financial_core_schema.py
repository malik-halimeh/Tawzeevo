"""Establish the immutable Phase 3 financial source-of-truth schema.

Revision ID: 20260826_0008
Revises: 20260826_0007
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260826_0008"
down_revision: str | None = "20260826_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

product_price_basis = postgresql.ENUM("PIECE", "BOX", name="product_price_basis", create_type=False)
customer_grade = postgresql.ENUM("A+", "A", "B+", "B", name="customer_grade", create_type=False)
price_resolution_source = postgresql.ENUM(
    "NORMAL",
    "GRADE_DISCOUNT",
    "EXPLICIT_GRADE_PRICE",
    name="price_resolution_source",
    create_type=False,
)


def _created_at_column() -> sa.Column[object]:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def _timestamp_columns() -> list[sa.Column[object]]:
    return [
        _created_at_column(),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def _enable_tenant_rls(table_name: str) -> None:
    tenant_expression = (
        "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
    )
    op.execute(f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table_name}" FORCE ROW LEVEL SECURITY')
    op.execute(
        f'CREATE POLICY "{table_name}_tenant_isolation" ON "{table_name}" '
        f"USING ({tenant_expression}) WITH CHECK ({tenant_expression})"
    )


def _make_immutable(table_name: str) -> None:
    op.execute(
        f'CREATE TRIGGER "{table_name}_immutable" '
        f'BEFORE UPDATE OR DELETE ON "{table_name}" '
        "FOR EACH ROW EXECUTE FUNCTION tawzeevo_reject_financial_mutation()"
    )


def upgrade() -> None:
    op.execute("ALTER TYPE invoice_status ADD VALUE IF NOT EXISTS 'CONFIRMED'")
    op.execute("ALTER TYPE invoice_status ADD VALUE IF NOT EXISTS 'CANCELLED'")

    op.create_table(
        "tenant_suppliers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_tenant_suppliers_id_tenant"),
    )
    op.create_index("ix_tenant_suppliers_tenant_id", "tenant_suppliers", ["tenant_id"])
    op.create_index("ix_tenant_suppliers_tenant_name", "tenant_suppliers", ["tenant_id", "name"])

    op.add_column(
        "tenant_products",
        sa.Column("preferred_supplier_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_tenant_products_preferred_supplier_id",
        "tenant_products",
        ["preferred_supplier_id"],
    )
    op.create_foreign_key(
        "fk_tenant_products_preferred_supplier_tenant",
        "tenant_products",
        "tenant_suppliers",
        ["preferred_supplier_id", "tenant_id"],
        ["id", "tenant_id"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "tenant_product_cost_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("unit_cost", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("cost_basis", product_price_basis, nullable=False),
        sa.Column("pieces_per_box", sa.Integer(), nullable=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        _created_at_column(),
        sa.CheckConstraint(
            "cost_basis != 'BOX' OR pieces_per_box IS NOT NULL",
            name="ck_product_cost_entries_box_has_piece_count",
        ),
        sa.CheckConstraint(
            "pieces_per_box IS NULL OR pieces_per_box > 0",
            name="ck_product_cost_entries_piece_count_positive",
        ),
        sa.CheckConstraint("unit_cost >= 0", name="ck_product_cost_entries_cost_nonnegative"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["supplier_id", "tenant_id"],
            ["tenant_suppliers.id", "tenant_suppliers.tenant_id"],
            name="fk_product_cost_entries_supplier_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["tenant_product_id", "tenant_id"],
            ["tenant_products.id", "tenant_products.tenant_id"],
            name="fk_product_cost_entries_product_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id",
            "tenant_id",
            "tenant_product_id",
            "supplier_id",
            name="uq_product_cost_entries_identity_scope",
        ),
    )
    op.create_index(
        "ix_tenant_product_cost_entries_tenant_id",
        "tenant_product_cost_entries",
        ["tenant_id"],
    )
    op.create_index(
        "ix_product_cost_entries_latest",
        "tenant_product_cost_entries",
        [
            "tenant_id",
            "tenant_product_id",
            "supplier_id",
            "currency",
            "cost_basis",
            "effective_at",
            "created_at",
            "id",
        ],
    )

    op.create_table(
        "invoice_sequences",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("last_number", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("last_number >= 0", name="ck_invoice_sequences_last_number_nonnegative"),
        sa.CheckConstraint("year BETWEEN 2000 AND 9999", name="ck_invoice_sequences_year_range"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tenant_id", "year"),
    )

    op.add_column("invoices", sa.Column("order_id", postgresql.UUID(as_uuid=True)))
    op.add_column("invoices", sa.Column("official_invoice_number", sa.String(length=11)))
    op.add_column("invoices", sa.Column("official_invoice_year", sa.Integer()))
    op.add_column("invoices", sa.Column("official_sequence_number", sa.Integer()))
    op.add_column("invoices", sa.Column("current_revision_id", postgresql.UUID(as_uuid=True)))
    op.add_column("invoices", sa.Column("confirmed_revision_id", postgresql.UUID(as_uuid=True)))
    op.add_column("invoices", sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True)))
    op.add_column("invoices", sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True)))
    op.add_column("invoices", sa.Column("confirmed_at", sa.DateTime(timezone=True)))
    op.add_column("invoices", sa.Column("cancelled_at", sa.DateTime(timezone=True)))
    op.create_index(
        "ix_invoices_tenant_order_unique",
        "invoices",
        ["tenant_id", "order_id"],
        unique=True,
        postgresql_where=sa.text("order_id IS NOT NULL"),
    )
    op.create_unique_constraint(
        "uq_invoices_tenant_official_number",
        "invoices",
        ["tenant_id", "official_invoice_number"],
    )
    op.create_unique_constraint(
        "uq_invoices_tenant_year_sequence",
        "invoices",
        ["tenant_id", "official_invoice_year", "official_sequence_number"],
    )
    op.create_check_constraint(
        "ck_invoices_official_number_complete",
        "invoices",
        "(official_invoice_number IS NULL AND official_invoice_year IS NULL "
        "AND official_sequence_number IS NULL) OR "
        "(official_invoice_number IS NOT NULL AND official_invoice_year IS NOT NULL "
        "AND official_sequence_number IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_invoices_official_year_range",
        "invoices",
        "official_invoice_year IS NULL OR official_invoice_year BETWEEN 2000 AND 9999",
    )
    op.create_check_constraint(
        "ck_invoices_official_sequence_positive",
        "invoices",
        "official_sequence_number IS NULL OR official_sequence_number > 0",
    )
    op.create_foreign_key(
        "fk_invoices_created_by_user",
        "invoices",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_invoices_updated_by_user",
        "invoices",
        "users",
        ["updated_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "invoice_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("predecessor_revision_id", postgresql.UUID(as_uuid=True)),
        sa.Column("server_revision_number", sa.Integer(), nullable=False),
        sa.Column("pricing_version", sa.String(length=40), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True)),
        sa.Column("customer_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("prior_balance_snapshot", sa.Numeric(20, 4), nullable=False),
        sa.Column("subtotal", sa.Numeric(20, 4), nullable=False),
        sa.Column("discount_total", sa.Numeric(20, 4), nullable=False),
        sa.Column("markup_total", sa.Numeric(20, 4), nullable=False),
        sa.Column("net_sales", sa.Numeric(20, 4), nullable=False),
        sa.Column("amount_due_display", sa.Numeric(20, 4), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("reason", sa.String(length=500)),
        _created_at_column(),
        sa.CheckConstraint("discount_total >= 0", name="ck_invoice_revisions_discount_nonnegative"),
        sa.CheckConstraint("markup_total >= 0", name="ck_invoice_revisions_markup_nonnegative"),
        sa.CheckConstraint("net_sales >= 0", name="ck_invoice_revisions_net_sales_nonnegative"),
        sa.CheckConstraint(
            "server_revision_number > 0", name="ck_invoice_revisions_number_positive"
        ),
        sa.CheckConstraint("subtotal >= 0", name="ck_invoice_revisions_subtotal_nonnegative"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["customer_id", "tenant_id"],
            ["customers.id", "customers.tenant_id"],
            name="fk_invoice_revisions_customer_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id", "tenant_id"],
            ["invoices.id", "invoices.tenant_id"],
            name="fk_invoice_revisions_invoice_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["predecessor_revision_id", "tenant_id", "invoice_id"],
            ["invoice_revisions.id", "invoice_revisions.tenant_id", "invoice_revisions.invoice_id"],
            name="fk_invoice_revisions_predecessor_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_invoice_revisions_id_tenant"),
        sa.UniqueConstraint(
            "id", "tenant_id", "invoice_id", name="uq_invoice_revisions_identity_scope"
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "invoice_id",
            "client_command_id",
            name="uq_invoice_revisions_client_command",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "invoice_id",
            "server_revision_number",
            name="uq_invoice_revisions_server_number",
        ),
    )
    op.create_index("ix_invoice_revisions_tenant_id", "invoice_revisions", ["tenant_id"])
    op.create_index("ix_invoice_revisions_invoice_id", "invoice_revisions", ["invoice_id"])
    op.create_index(
        "ix_invoice_revisions_one_successor",
        "invoice_revisions",
        ["tenant_id", "invoice_id", "predecessor_revision_id"],
        unique=True,
        postgresql_where=sa.text("predecessor_revision_id IS NOT NULL"),
    )

    op.execute(
        "INSERT INTO invoice_revisions "
        "(id, tenant_id, invoice_id, client_command_id, server_revision_number, "
        "pricing_version, currency, customer_id, customer_snapshot, prior_balance_snapshot, "
        "subtotal, discount_total, markup_total, net_sales, amount_due_display, created_at) "
        "SELECT gen_random_uuid(), i.tenant_id, i.id, gen_random_uuid(), 1, 'pricing-v1', "
        "i.currency, i.customer_id, jsonb_build_object('id', c.id, 'name', c.name, "
        "'phone', c.phone, 'address', c.address, 'grade', c.grade), 0.0000, i.subtotal, "
        "0.0000, 0.0000, i.subtotal, i.subtotal, i.created_at "
        "FROM invoices i JOIN customers c ON c.id = i.customer_id AND c.tenant_id = i.tenant_id"
    )
    op.execute(
        "UPDATE invoices i SET current_revision_id = r.id "
        "FROM invoice_revisions r "
        "WHERE r.invoice_id = i.id AND r.tenant_id = i.tenant_id"
    )
    op.alter_column("invoices", "current_revision_id", nullable=False)

    op.create_table(
        "invoice_revision_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_product_id", postgresql.UUID(as_uuid=True)),
        sa.Column("product_name", sa.String(length=200), nullable=False),
        sa.Column("barcode", sa.String(length=64)),
        sa.Column("media_snapshot", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("quantity", sa.Numeric(20, 4), nullable=False),
        sa.Column("price_basis", product_price_basis, nullable=False),
        sa.Column("pieces_per_box", sa.Integer()),
        sa.Column("normal_unit_price", sa.Numeric(20, 4), nullable=False),
        sa.Column("grade_rule_snapshot", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("effective_unit_price", sa.Numeric(20, 4), nullable=False),
        sa.Column("line_discount", sa.Numeric(20, 4), server_default="0.0000", nullable=False),
        sa.Column("line_markup", sa.Numeric(20, 4), server_default="0.0000", nullable=False),
        sa.Column("line_total", sa.Numeric(20, 4), nullable=False),
        sa.Column("customer_grade", customer_grade),
        sa.Column("price_source", price_resolution_source, server_default="NORMAL", nullable=False),
        sa.Column("grade_discount_percent", sa.Numeric(7, 4)),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True)),
        sa.Column("product_cost_entry_id", postgresql.UUID(as_uuid=True)),
        sa.Column("unit_cost", sa.Numeric(20, 4)),
        sa.Column("cost_currency", sa.String(length=3)),
        sa.Column("cost_basis", product_price_basis),
        sa.Column("cost_pieces_per_box", sa.Integer()),
        sa.Column("cost_source_type", sa.String(length=40)),
        sa.Column("is_cost_override", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("cost_override_reason", sa.String(length=500)),
        _created_at_column(),
        sa.CheckConstraint(
            "effective_unit_price >= 0",
            name="ck_invoice_revision_items_effective_price_nonnegative",
        ),
        sa.CheckConstraint(
            "grade_discount_percent IS NULL OR "
            "(grade_discount_percent >= 0 AND grade_discount_percent <= 100)",
            name="ck_invoice_revision_items_grade_discount_percent_range",
        ),
        sa.CheckConstraint(
            "line_discount >= 0", name="ck_invoice_revision_items_discount_nonnegative"
        ),
        sa.CheckConstraint("line_markup >= 0", name="ck_invoice_revision_items_markup_nonnegative"),
        sa.CheckConstraint("line_total >= 0", name="ck_invoice_revision_items_total_nonnegative"),
        sa.CheckConstraint(
            "normal_unit_price >= 0",
            name="ck_invoice_revision_items_normal_price_nonnegative",
        ),
        sa.CheckConstraint(
            "pieces_per_box IS NULL OR pieces_per_box > 0",
            name="ck_invoice_revision_items_piece_count_positive",
        ),
        sa.CheckConstraint("quantity > 0", name="ck_invoice_revision_items_quantity_positive"),
        sa.CheckConstraint(
            "unit_cost IS NULL OR unit_cost >= 0",
            name="ck_invoice_revision_items_cost_nonnegative",
        ),
        sa.CheckConstraint(
            "cost_pieces_per_box IS NULL OR cost_pieces_per_box > 0",
            name="ck_invoice_revision_items_cost_piece_count_positive",
        ),
        sa.CheckConstraint(
            "(unit_cost IS NULL AND cost_currency IS NULL AND cost_basis IS NULL "
            "AND cost_source_type IS NULL) OR "
            "(unit_cost IS NOT NULL AND cost_currency IS NOT NULL AND cost_basis IS NOT NULL "
            "AND cost_source_type IS NOT NULL)",
            name="ck_invoice_revision_items_cost_snapshot_complete",
        ),
        sa.CheckConstraint(
            "(NOT is_cost_override AND cost_override_reason IS NULL) OR "
            "(is_cost_override AND unit_cost IS NOT NULL "
            "AND length(btrim(coalesce(cost_override_reason, ''))) > 0)",
            name="ck_invoice_revision_items_override_reason",
        ),
        sa.ForeignKeyConstraint(
            ["invoice_revision_id", "tenant_id"],
            ["invoice_revisions.id", "invoice_revisions.tenant_id"],
            name="fk_invoice_revision_items_revision_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_cost_entry_id", "tenant_id", "tenant_product_id", "supplier_id"],
            [
                "tenant_product_cost_entries.id",
                "tenant_product_cost_entries.tenant_id",
                "tenant_product_cost_entries.tenant_product_id",
                "tenant_product_cost_entries.supplier_id",
            ],
            name="fk_invoice_revision_items_cost_source_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id", "tenant_id"],
            ["tenant_suppliers.id", "tenant_suppliers.tenant_id"],
            name="fk_invoice_revision_items_supplier_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_product_id", "tenant_id"],
            ["tenant_products.id", "tenant_products.tenant_id"],
            name="fk_invoice_revision_items_product_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_invoice_revision_items_id_tenant"),
    )
    op.create_index("ix_invoice_revision_items_tenant_id", "invoice_revision_items", ["tenant_id"])
    op.create_index(
        "ix_invoice_revision_items_invoice_revision_id",
        "invoice_revision_items",
        ["invoice_revision_id"],
    )
    op.create_index(
        "ix_invoice_revision_items_tenant_product_id",
        "invoice_revision_items",
        ["tenant_product_id"],
    )
    op.execute(
        "INSERT INTO invoice_revision_items "
        "(id, tenant_id, invoice_revision_id, tenant_product_id, product_name, barcode, "
        "quantity, price_basis, pieces_per_box, normal_unit_price, grade_rule_snapshot, "
        "effective_unit_price, line_discount, line_markup, line_total, customer_grade, "
        "price_source, grade_discount_percent, created_at) "
        "SELECT old.id, old.tenant_id, rev.id, old.product_id, old.product_name, old.barcode, "
        "old.quantity, old.price_basis, product.pieces_per_box, product.unit_price, "
        "jsonb_build_object('customer_grade', old.customer_grade, 'price_source', "
        "old.price_source, 'discount_percent', old.grade_discount_percent), old.unit_price, "
        "0.0000, 0.0000, old.line_total, old.customer_grade, old.price_source, "
        "old.grade_discount_percent, old.created_at "
        "FROM invoice_items old "
        "JOIN invoice_revisions rev ON rev.invoice_id = old.invoice_id "
        "AND rev.tenant_id = old.tenant_id "
        "JOIN tenant_products product ON product.id = old.product_id "
        "AND product.tenant_id = old.tenant_id"
    )

    op.create_foreign_key(
        "fk_invoices_current_revision_scope",
        "invoices",
        "invoice_revisions",
        ["current_revision_id", "tenant_id", "id"],
        ["id", "tenant_id", "invoice_id"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_foreign_key(
        "fk_invoices_confirmed_revision_scope",
        "invoices",
        "invoice_revisions",
        ["confirmed_revision_id", "tenant_id", "id"],
        ["id", "tenant_id", "invoice_id"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.alter_column("invoices", "customer_id", nullable=True)
    op.drop_table("invoice_items")
    op.drop_constraint("ck_invoices_subtotal_nonnegative", "invoices", type_="check")
    op.drop_column("invoices", "subtotal")
    op.drop_column("invoices", "currency")

    op.create_table(
        "customer_ledger_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("signed_amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("entry_type", sa.String(length=50), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True)),
        sa.Column("source_effect_key", sa.String(length=160), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("reverses_entry_id", postgresql.UUID(as_uuid=True)),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True)),
        sa.Column("metadata_json", postgresql.JSONB(), server_default="{}", nullable=False),
        _created_at_column(),
        sa.CheckConstraint("signed_amount <> 0", name="ck_customer_ledger_amount_nonzero"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["customer_id", "tenant_id"],
            ["customers.id", "customers.tenant_id"],
            name="fk_customer_ledger_customer_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reverses_entry_id", "tenant_id"],
            ["customer_ledger_entries.id", "customer_ledger_entries.tenant_id"],
            name="fk_customer_ledger_reversal_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_customer_ledger_id_tenant"),
        sa.UniqueConstraint(
            "id",
            "tenant_id",
            "currency",
            "customer_id",
            name="uq_customer_ledger_allocation_scope",
        ),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_customer_ledger_idempotency"),
        sa.UniqueConstraint(
            "tenant_id", "reverses_entry_id", name="uq_customer_ledger_single_reversal"
        ),
        sa.UniqueConstraint(
            "tenant_id", "source_effect_key", name="uq_customer_ledger_source_effect"
        ),
    )
    op.create_index(
        "ix_customer_ledger_entries_tenant_id", "customer_ledger_entries", ["tenant_id"]
    )
    op.create_index(
        "ix_customer_ledger_balance",
        "customer_ledger_entries",
        ["tenant_id", "customer_id", "currency", "effective_at", "created_at", "id"],
    )

    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True)),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True)),
        sa.Column("direction", sa.String(length=50), nullable=False),
        sa.Column("amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("method", sa.String(length=80)),
        sa.Column("reference", sa.String(length=200)),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("recorded_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_device_id", postgresql.UUID(as_uuid=True)),
        sa.Column("reverses_payment_id", postgresql.UUID(as_uuid=True)),
        sa.Column("notes", sa.String(length=500)),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        sa.CheckConstraint(
            "((direction IN ('CUSTOMER_RECEIPT', 'CUSTOMER_RECEIPT_REVERSAL', "
            "'CUSTOMER_REFUND')) AND customer_id IS NOT NULL AND supplier_id IS NULL) OR "
            "((direction IN ('SUPPLIER_PAYMENT', 'SUPPLIER_PAYMENT_REVERSAL')) "
            "AND supplier_id IS NOT NULL AND customer_id IS NULL)",
            name="ck_payments_party_matches_direction",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id", "tenant_id"],
            ["customers.id", "customers.tenant_id"],
            name="fk_payments_customer_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["reverses_payment_id", "tenant_id"],
            ["payments.id", "payments.tenant_id"],
            name="fk_payments_reversal_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id", "tenant_id"],
            ["tenant_suppliers.id", "tenant_suppliers.tenant_id"],
            name="fk_payments_supplier_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_payments_id_tenant"),
        sa.UniqueConstraint(
            "id", "tenant_id", "currency", "customer_id", name="uq_payments_customer_scope"
        ),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_payments_idempotency"),
        sa.UniqueConstraint("tenant_id", "reverses_payment_id", name="uq_payments_single_reversal"),
    )
    op.create_index("ix_payments_tenant_id", "payments", ["tenant_id"])

    op.create_table(
        "payment_allocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_ledger_entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("reverses_allocation_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        _created_at_column(),
        sa.CheckConstraint("amount > 0", name="ck_payment_allocations_amount_positive"),
        sa.CheckConstraint(
            "(kind = 'APPLY' AND reverses_allocation_id IS NULL) OR "
            "(kind = 'REVERSAL' AND reverses_allocation_id IS NOT NULL)",
            name="ck_payment_allocations_reversal_shape",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["payment_id", "tenant_id", "currency", "customer_id"],
            ["payments.id", "payments.tenant_id", "payments.currency", "payments.customer_id"],
            name="fk_payment_allocations_payment_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reverses_allocation_id", "tenant_id"],
            ["payment_allocations.id", "payment_allocations.tenant_id"],
            name="fk_payment_allocations_reversal_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["target_ledger_entry_id", "tenant_id", "currency", "customer_id"],
            [
                "customer_ledger_entries.id",
                "customer_ledger_entries.tenant_id",
                "customer_ledger_entries.currency",
                "customer_ledger_entries.customer_id",
            ],
            name="fk_payment_allocations_target_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_payment_allocations_id_tenant"),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_payment_allocations_idempotency"
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "reverses_allocation_id",
            name="uq_payment_allocations_single_reversal",
        ),
    )
    op.create_index("ix_payment_allocations_tenant_id", "payment_allocations", ["tenant_id"])

    op.create_table(
        "supplier_ledger_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("signed_amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("entry_type", sa.String(length=50), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True)),
        sa.Column("source_effect_key", sa.String(length=160), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("reverses_entry_id", postgresql.UUID(as_uuid=True)),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True)),
        sa.Column("metadata_json", postgresql.JSONB(), server_default="{}", nullable=False),
        _created_at_column(),
        sa.CheckConstraint("signed_amount <> 0", name="ck_supplier_ledger_amount_nonzero"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["reverses_entry_id", "tenant_id"],
            ["supplier_ledger_entries.id", "supplier_ledger_entries.tenant_id"],
            name="fk_supplier_ledger_reversal_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id", "tenant_id"],
            ["tenant_suppliers.id", "tenant_suppliers.tenant_id"],
            name="fk_supplier_ledger_supplier_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_supplier_ledger_id_tenant"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_supplier_ledger_idempotency"),
        sa.UniqueConstraint(
            "tenant_id", "reverses_entry_id", name="uq_supplier_ledger_single_reversal"
        ),
        sa.UniqueConstraint(
            "tenant_id", "source_effect_key", name="uq_supplier_ledger_source_effect"
        ),
    )
    op.create_index(
        "ix_supplier_ledger_entries_tenant_id", "supplier_ledger_entries", ["tenant_id"]
    )
    op.create_index(
        "ix_supplier_ledger_balance",
        "supplier_ledger_entries",
        ["tenant_id", "supplier_id", "currency", "effective_at", "created_at", "id"],
    )

    op.create_table(
        "public_invoice_capabilities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_sha256", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("rotated_from_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "length(token_sha256) = 64",
            name="ck_public_invoice_capabilities_hash_length",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["invoice_id", "tenant_id"],
            ["invoices.id", "invoices.tenant_id"],
            name="fk_public_invoice_capabilities_invoice_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["rotated_from_id", "tenant_id"],
            ["public_invoice_capabilities.id", "public_invoice_capabilities.tenant_id"],
            name="fk_public_invoice_capabilities_rotation_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_public_invoice_capabilities_id_tenant"),
        sa.UniqueConstraint(
            "tenant_id",
            "rotated_from_id",
            name="uq_public_invoice_capabilities_single_rotation",
        ),
        sa.UniqueConstraint("token_sha256"),
    )
    op.create_index(
        "ix_public_invoice_capabilities_tenant_id",
        "public_invoice_capabilities",
        ["tenant_id"],
    )

    tenant_tables = (
        "tenant_suppliers",
        "tenant_product_cost_entries",
        "invoice_sequences",
        "invoice_revisions",
        "invoice_revision_items",
        "customer_ledger_entries",
        "payments",
        "payment_allocations",
        "supplier_ledger_entries",
        "public_invoice_capabilities",
    )
    for table_name in tenant_tables:
        _enable_tenant_rls(table_name)

    op.execute(
        "CREATE FUNCTION tawzeevo_reject_financial_mutation() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN "
        "RAISE EXCEPTION 'immutable financial row: %', TG_TABLE_NAME "
        "USING ERRCODE = '55000'; END; $$"
    )
    for table_name in (
        "tenant_product_cost_entries",
        "invoice_revisions",
        "invoice_revision_items",
        "customer_ledger_entries",
        "payments",
        "payment_allocations",
        "supplier_ledger_entries",
    ):
        _make_immutable(table_name)


def downgrade() -> None:
    for table_name in (
        "tenant_product_cost_entries",
        "invoice_revisions",
        "invoice_revision_items",
        "customer_ledger_entries",
        "payments",
        "payment_allocations",
        "supplier_ledger_entries",
    ):
        op.execute(f'DROP TRIGGER IF EXISTS "{table_name}_immutable" ON "{table_name}"')
    op.execute("DROP FUNCTION tawzeevo_reject_financial_mutation()")

    op.create_table(
        "invoice_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_name", sa.String(length=200), nullable=False),
        sa.Column("barcode", sa.String(length=64), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 4), nullable=False),
        sa.Column("price_basis", product_price_basis, nullable=False),
        sa.Column("unit_price", sa.Numeric(20, 4), nullable=False),
        sa.Column("line_total", sa.Numeric(20, 4), nullable=False),
        sa.Column("customer_grade", customer_grade),
        sa.Column("price_source", price_resolution_source, server_default="NORMAL", nullable=False),
        sa.Column("grade_discount_percent", sa.Numeric(7, 4)),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "grade_discount_percent IS NULL OR "
            "(grade_discount_percent >= 0 AND grade_discount_percent <= 100)",
            name="ck_invoice_items_grade_discount_percent_range",
        ),
        sa.CheckConstraint("line_total >= 0", name="ck_invoice_items_line_total_nonnegative"),
        sa.CheckConstraint("quantity > 0", name="ck_invoice_items_quantity_positive"),
        sa.CheckConstraint("unit_price >= 0", name="ck_invoice_items_unit_price_nonnegative"),
        sa.ForeignKeyConstraint(
            ["invoice_id", "tenant_id"],
            ["invoices.id", "invoices.tenant_id"],
            name="fk_invoice_items_invoice_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id", "tenant_id"],
            ["tenant_products.id", "tenant_products.tenant_id"],
            name="fk_invoice_items_product_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invoice_items_tenant_id", "invoice_items", ["tenant_id"])
    op.create_index("ix_invoice_items_invoice_id", "invoice_items", ["invoice_id"])
    op.create_index("ix_invoice_items_product_id", "invoice_items", ["product_id"])
    _enable_tenant_rls("invoice_items")

    op.add_column("invoices", sa.Column("currency", sa.String(length=3)))
    op.add_column("invoices", sa.Column("subtotal", sa.Numeric(20, 4)))
    op.execute(
        "UPDATE invoices i SET currency = r.currency, subtotal = r.subtotal "
        "FROM invoice_revisions r WHERE r.id = i.current_revision_id"
    )
    op.alter_column("invoices", "currency", nullable=False)
    op.alter_column("invoices", "subtotal", nullable=False)
    op.create_check_constraint("ck_invoices_subtotal_nonnegative", "invoices", "subtotal >= 0")
    op.execute(
        "INSERT INTO invoice_items "
        "(id, tenant_id, invoice_id, product_id, product_name, barcode, quantity, "
        "price_basis, unit_price, line_total, customer_grade, price_source, "
        "grade_discount_percent, created_at, updated_at) "
        "SELECT item.id, item.tenant_id, revision.invoice_id, item.tenant_product_id, "
        "item.product_name, item.barcode, item.quantity, item.price_basis, "
        "item.effective_unit_price, item.line_total, item.customer_grade, item.price_source, "
        "item.grade_discount_percent, item.created_at, item.created_at "
        "FROM invoice_revision_items item "
        "JOIN invoice_revisions revision ON revision.id = item.invoice_revision_id "
        "JOIN invoices invoice ON invoice.current_revision_id = revision.id "
        "WHERE item.tenant_product_id IS NOT NULL AND item.barcode IS NOT NULL"
    )

    op.drop_constraint("fk_invoices_confirmed_revision_scope", "invoices", type_="foreignkey")
    op.drop_constraint("fk_invoices_current_revision_scope", "invoices", type_="foreignkey")
    op.drop_table("public_invoice_capabilities")
    op.drop_table("payment_allocations")
    op.drop_table("payments")
    op.drop_table("customer_ledger_entries")
    op.drop_table("supplier_ledger_entries")
    op.drop_table("invoice_revision_items")
    op.drop_table("invoice_revisions")
    op.drop_table("invoice_sequences")

    op.alter_column("invoices", "customer_id", nullable=False)
    op.drop_constraint("fk_invoices_updated_by_user", "invoices", type_="foreignkey")
    op.drop_constraint("fk_invoices_created_by_user", "invoices", type_="foreignkey")
    op.drop_constraint("ck_invoices_official_sequence_positive", "invoices", type_="check")
    op.drop_constraint("ck_invoices_official_year_range", "invoices", type_="check")
    op.drop_constraint("ck_invoices_official_number_complete", "invoices", type_="check")
    op.drop_constraint("uq_invoices_tenant_year_sequence", "invoices", type_="unique")
    op.drop_constraint("uq_invoices_tenant_official_number", "invoices", type_="unique")
    op.drop_index("ix_invoices_tenant_order_unique", table_name="invoices")
    for column_name in (
        "cancelled_at",
        "confirmed_at",
        "updated_by_user_id",
        "created_by_user_id",
        "confirmed_revision_id",
        "current_revision_id",
        "official_sequence_number",
        "official_invoice_year",
        "official_invoice_number",
        "order_id",
    ):
        op.drop_column("invoices", column_name)

    op.drop_table("tenant_product_cost_entries")
    op.drop_constraint(
        "fk_tenant_products_preferred_supplier_tenant",
        "tenant_products",
        type_="foreignkey",
    )
    op.drop_index("ix_tenant_products_preferred_supplier_id", table_name="tenant_products")
    op.drop_column("tenant_products", "preferred_supplier_id")
    op.drop_table("tenant_suppliers")

    op.execute("ALTER TABLE invoices ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TYPE invoice_status RENAME TO invoice_status_phase3")
    op.execute("CREATE TYPE invoice_status AS ENUM ('DRAFT')")
    op.execute(
        "ALTER TABLE invoices ALTER COLUMN status TYPE invoice_status "
        "USING status::text::invoice_status"
    )
    op.execute("ALTER TABLE invoices ALTER COLUMN status SET DEFAULT 'DRAFT'")
    op.execute("DROP TYPE invoice_status_phase3")
