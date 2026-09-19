"""Immutable supplier purchases and their lines.

Revision ID: 20260919_0024
Revises: 20260919_0023
Create Date: 2026-09-19

Phase 6 P6-M4 (PHASE_06.md G/H; D-038, D-039, D-059). A purchase is an immutable header with
lines; its finalization appends ACTUAL_PURCHASE cost entries, one PURCHASE_CHARGE supplier-ledger
entry and increments the linked procurement lines, all in one transaction. A reversal is a
compensating PURCHASE_REVERSAL ledger entry; the purchase row is marked, never edited or deleted.
Internal UUIDs only — no supplier-purchase business sequence. No inventory effect of any kind.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260919_0024"
down_revision: str | None = "20260919_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_EXPRESSION = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
product_price_basis = postgresql.ENUM("PIECE", "BOX", name="product_price_basis", create_type=False)


def _enable_tenant_rls(table_name: str) -> None:
    op.execute(f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table_name}" FORCE ROW LEVEL SECURITY')
    op.execute(
        f'CREATE POLICY "{table_name}_tenant_isolation" ON "{table_name}" '
        f"USING ({TENANT_EXPRESSION}) WITH CHECK ({TENANT_EXPRESSION})"
    )


def upgrade() -> None:
    op.create_table(
        "supplier_purchases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("procurement_list_id", postgresql.UUID(as_uuid=True)),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purchased_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("total_amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("supplier_reference", sa.String(200)),
        sa.Column("notes", sa.String(1000)),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("reversed_at", sa.DateTime(timezone=True)),
        sa.Column("reversal_reason", sa.String(500)),
        sa.Column("reversal_idempotency_key", postgresql.UUID(as_uuid=True)),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["supplier_id", "tenant_id"],
            ["tenant_suppliers.id", "tenant_suppliers.tenant_id"],
            ondelete="RESTRICT",
            name="fk_supplier_purchases_supplier_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["procurement_list_id", "tenant_id"],
            ["procurement_lists.id", "procurement_lists.tenant_id"],
            ondelete="SET NULL",
            name="fk_supplier_purchases_list_tenant",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_supplier_purchases_id_tenant"),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_supplier_purchases_idempotency"
        ),
        sa.CheckConstraint("total_amount >= 0", name="ck_supplier_purchases_total_nonneg"),
        sa.CheckConstraint(
            "(reversed_at IS NULL) = (reversal_reason IS NULL)",
            name="ck_supplier_purchases_reversal_pair",
        ),
    )
    op.create_index(
        "ix_supplier_purchases_supplier",
        "supplier_purchases",
        ["tenant_id", "supplier_id", "purchased_at"],
    )
    _enable_tenant_rls("supplier_purchases")

    op.create_table(
        "supplier_purchase_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("tenant_product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_name", sa.String(200), nullable=False),
        sa.Column("procurement_item_id", postgresql.UUID(as_uuid=True)),
        sa.Column("quantity", sa.Numeric(20, 4), nullable=False),
        sa.Column("price_basis", product_price_basis, nullable=False),
        sa.Column("pieces_per_box", sa.Integer()),
        sa.Column("unit_cost", sa.Numeric(20, 4), nullable=False),
        sa.Column("line_total", sa.Numeric(20, 4), nullable=False),
        sa.Column("cost_entry_id", postgresql.UUID(as_uuid=True)),
        sa.Column("notes", sa.String(500)),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["purchase_id", "tenant_id"],
            ["supplier_purchases.id", "supplier_purchases.tenant_id"],
            ondelete="CASCADE",
            name="fk_supplier_purchase_items_purchase_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_product_id", "tenant_id"],
            ["tenant_products.id", "tenant_products.tenant_id"],
            ondelete="RESTRICT",
            name="fk_supplier_purchase_items_product_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["procurement_item_id", "tenant_id"],
            ["procurement_items.id", "procurement_items.tenant_id"],
            ondelete="SET NULL",
            name="fk_supplier_purchase_items_procurement_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["cost_entry_id"],
            ["tenant_product_cost_entries.id"],
            ondelete="SET NULL",
            name="fk_supplier_purchase_items_cost_entry",
        ),
        sa.UniqueConstraint("purchase_id", "line_number", name="uq_supplier_purchase_items_line"),
        sa.CheckConstraint("quantity > 0", name="ck_supplier_purchase_items_quantity_positive"),
        sa.CheckConstraint("unit_cost >= 0", name="ck_supplier_purchase_items_unit_cost_nonneg"),
        sa.CheckConstraint("line_total >= 0", name="ck_supplier_purchase_items_total_nonneg"),
    )
    op.create_index(
        "ix_supplier_purchase_items_purchase",
        "supplier_purchase_items",
        ["tenant_id", "purchase_id"],
    )
    _enable_tenant_rls("supplier_purchase_items")


def downgrade() -> None:
    op.drop_table("supplier_purchase_items")
    op.drop_table("supplier_purchases")
