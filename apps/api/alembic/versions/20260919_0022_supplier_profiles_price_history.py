"""Supplier profiles and cost-entry provenance for the append-only price history.

Revision ID: 20260919_0022
Revises: 20260919_0021
Create Date: 2026-09-19

Phase 6 P6-M1 (PHASE_06.md B/C/K; D-034, D-059). Suppliers gain contact, address, saved location,
notes and a row version (offline edits carry an expected version). Cost entries gain an optional
quantity context and a constrained provenance (`MANUAL`, `OWNER_OVERRIDE`, `QUOTE`,
`ACTUAL_PURCHASE`). No table is duplicated: the D-034 cost entry stays the single price truth.
Applied rows are never edited; existing entries keep their `MANUAL` / `OWNER_OVERRIDE` provenance.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260919_0022"
down_revision: str | None = "20260919_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tenant_suppliers", sa.Column("contact_name", sa.String(length=200)))
    op.add_column("tenant_suppliers", sa.Column("contact_phone", sa.String(length=32)))
    op.add_column("tenant_suppliers", sa.Column("contact_phone_raw", sa.String(length=64)))
    op.add_column("tenant_suppliers", sa.Column("address", sa.String(length=500)))
    op.add_column("tenant_suppliers", sa.Column("latitude", sa.Numeric(9, 6)))
    op.add_column("tenant_suppliers", sa.Column("longitude", sa.Numeric(10, 6)))
    op.add_column("tenant_suppliers", sa.Column("notes", sa.String(length=1000)))
    op.add_column(
        "tenant_suppliers",
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.create_check_constraint(
        "ck_tenant_suppliers_coordinates_paired",
        "tenant_suppliers",
        "(latitude IS NULL) = (longitude IS NULL)",
    )
    op.create_check_constraint(
        "ck_tenant_suppliers_latitude_range",
        "tenant_suppliers",
        "latitude IS NULL OR latitude BETWEEN -90 AND 90",
    )
    op.create_check_constraint(
        "ck_tenant_suppliers_longitude_range",
        "tenant_suppliers",
        "longitude IS NULL OR longitude BETWEEN -180 AND 180",
    )

    op.add_column("tenant_product_cost_entries", sa.Column("quantity_context", sa.Numeric(20, 4)))
    op.create_check_constraint(
        "ck_tenant_product_cost_entries_source_type",
        "tenant_product_cost_entries",
        "source_type IN ('MANUAL', 'OWNER_OVERRIDE', 'QUOTE', 'ACTUAL_PURCHASE')",
    )
    op.create_check_constraint(
        "ck_tenant_product_cost_entries_quantity_context_positive",
        "tenant_product_cost_entries",
        "quantity_context IS NULL OR quantity_context > 0",
    )
    op.create_index(
        "ix_tenant_product_cost_entries_product_supplier_effective",
        "tenant_product_cost_entries",
        ["tenant_id", "tenant_product_id", "supplier_id", "effective_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tenant_product_cost_entries_product_supplier_effective",
        table_name="tenant_product_cost_entries",
    )
    op.drop_constraint(
        "ck_tenant_product_cost_entries_quantity_context_positive",
        "tenant_product_cost_entries",
        type_="check",
    )
    op.drop_constraint(
        "ck_tenant_product_cost_entries_source_type",
        "tenant_product_cost_entries",
        type_="check",
    )
    op.drop_column("tenant_product_cost_entries", "quantity_context")
    for name in (
        "ck_tenant_suppliers_longitude_range",
        "ck_tenant_suppliers_latitude_range",
        "ck_tenant_suppliers_coordinates_paired",
    ):
        op.drop_constraint(name, "tenant_suppliers", type_="check")
    for column in (
        "version",
        "notes",
        "longitude",
        "latitude",
        "address",
        "contact_phone_raw",
        "contact_phone",
        "contact_name",
    ):
        op.drop_column("tenant_suppliers", column)
