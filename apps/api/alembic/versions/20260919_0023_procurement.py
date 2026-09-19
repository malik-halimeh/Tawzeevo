"""Procurement lists and items with neutral assignee (owner or driver membership).

Revision ID: 20260919_0023
Revises: 20260919_0022
Create Date: 2026-09-19

Phase 6 P6-M3 (PHASE_06.md A/E/F; D-058). Quantities are demand and purchasing progress only:
`required_quantity` (from confirmed demand), `target_quantity` (owner adjustable),
`purchased_quantity` (incremented by P6-M4 purchases); remaining is derived. No stock, on-hand,
reserved or availability column exists or may be added. Lines are never deleted: a removed or
waived line stays with its reason; carry-forward links the old line to the new one. Assignee is
an active tenant membership (owner or driver); the driver projection is computed in the service
and never includes prices. Every table is tenant-owned (RLS).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260919_0023"
down_revision: str | None = "20260919_0022"
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
        "procurement_lists",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="OPEN"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("demand_from", sa.Date()),
        sa.Column("demand_to", sa.Date()),
        sa.Column("notes", sa.String(1000)),
        sa.Column("assignee_membership_id", postgresql.UUID(as_uuid=True)),
        sa.Column("carried_from_list_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancel_reason", sa.String(500)),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["assignee_membership_id"], ["tenant_memberships.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["carried_from_list_id"], ["procurement_lists.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_procurement_lists_id_tenant"),
        sa.CheckConstraint(
            "status IN ('OPEN', 'PARTIALLY_PURCHASED', 'COMPLETE', 'CANCELLED')",
            name="ck_procurement_lists_status",
        ),
        sa.CheckConstraint(
            "demand_from IS NULL OR demand_to IS NULL OR demand_from <= demand_to",
            name="ck_procurement_lists_demand_range",
        ),
    )
    op.create_index(
        "ix_procurement_lists_tenant_status", "procurement_lists", ["tenant_id", "status"]
    )
    op.create_index(
        "ix_procurement_lists_assignee",
        "procurement_lists",
        ["tenant_id", "assignee_membership_id"],
    )
    _enable_tenant_rls("procurement_lists")

    op.create_table(
        "procurement_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("list_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_name", sa.String(200), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True)),
        sa.Column("price_basis", product_price_basis, nullable=False),
        sa.Column("pieces_per_box", sa.Integer()),
        sa.Column("origin", sa.String(16), nullable=False),
        sa.Column("required_quantity", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("target_quantity", sa.Numeric(20, 4), nullable=False),
        sa.Column("purchased_quantity", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("demand_invoice_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("removed_at", sa.DateTime(timezone=True)),
        sa.Column("remove_reason", sa.String(300)),
        sa.Column("waived_at", sa.DateTime(timezone=True)),
        sa.Column("waive_reason", sa.String(300)),
        sa.Column("carried_from_item_id", postgresql.UUID(as_uuid=True)),
        sa.Column("carried_to_item_id", postgresql.UUID(as_uuid=True)),
        sa.Column("notes", sa.String(500)),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["list_id", "tenant_id"],
            ["procurement_lists.id", "procurement_lists.tenant_id"],
            ondelete="CASCADE",
            name="fk_procurement_items_list_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_product_id", "tenant_id"],
            ["tenant_products.id", "tenant_products.tenant_id"],
            ondelete="RESTRICT",
            name="fk_procurement_items_product_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id", "tenant_id"],
            ["tenant_suppliers.id", "tenant_suppliers.tenant_id"],
            ondelete="SET NULL",
            name="fk_procurement_items_supplier_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["carried_from_item_id"], ["procurement_items.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["carried_to_item_id"], ["procurement_items.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_procurement_items_id_tenant"),
        sa.CheckConstraint(
            "origin IN ('DEMAND', 'MANUAL', 'CARRY_FORWARD')", name="ck_procurement_items_origin"
        ),
        sa.CheckConstraint("required_quantity >= 0", name="ck_procurement_items_required_nonneg"),
        sa.CheckConstraint("target_quantity >= 0", name="ck_procurement_items_target_nonneg"),
        sa.CheckConstraint("purchased_quantity >= 0", name="ck_procurement_items_purchased_nonneg"),
        sa.CheckConstraint(
            "(waived_at IS NULL) = (waive_reason IS NULL)", name="ck_procurement_items_waive_pair"
        ),
        sa.CheckConstraint(
            "(removed_at IS NULL) = (remove_reason IS NULL)",
            name="ck_procurement_items_remove_pair",
        ),
    )
    op.create_index("ix_procurement_items_list", "procurement_items", ["tenant_id", "list_id"])
    op.create_index(
        "ix_procurement_items_product", "procurement_items", ["tenant_id", "tenant_product_id"]
    )
    _enable_tenant_rls("procurement_items")


def downgrade() -> None:
    op.drop_table("procurement_items")
    op.drop_table("procurement_lists")
