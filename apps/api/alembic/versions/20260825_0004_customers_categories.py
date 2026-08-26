"""Add production customer, grade, location, and category foundations.

Revision ID: 20260825_0004
Revises: 20260820_0003
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260825_0004"
down_revision: str | None = "20260820_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

customer_grade = postgresql.ENUM("A+", "A", "B+", "B", name="customer_grade", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    customer_grade.create(bind, checkfirst=True)

    op.add_column("customers", sa.Column("latitude", sa.Numeric(9, 6), nullable=True))
    op.add_column("customers", sa.Column("longitude", sa.Numeric(10, 6), nullable=True))
    op.add_column("customers", sa.Column("grade", customer_grade, nullable=True))
    op.create_check_constraint(
        "ck_customers_coordinates_paired",
        "customers",
        "(latitude IS NULL) = (longitude IS NULL)",
    )
    op.create_check_constraint(
        "ck_customers_latitude_range",
        "customers",
        "latitude IS NULL OR latitude BETWEEN -90 AND 90",
    )
    op.create_check_constraint(
        "ck_customers_longitude_range",
        "customers",
        "longitude IS NULL OR longitude BETWEEN -180 AND 180",
    )

    op.create_table(
        "master_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name_en", sa.String(length=200), nullable=False),
        sa.Column("name_ar", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "(is_active AND archived_at IS NULL) OR (NOT is_active AND archived_at IS NOT NULL)",
            name="ck_master_categories_archive_state",
        ),
    )
    op.execute('ALTER TABLE "master_categories" ENABLE ROW LEVEL SECURITY')

    op.add_column(
        "categories",
        sa.Column("master_category_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("categories", sa.Column("name_en", sa.String(length=200), nullable=True))
    op.add_column("categories", sa.Column("name_ar", sa.String(length=200), nullable=True))
    op.add_column("categories", sa.Column("slug", sa.String(length=120), nullable=True))
    op.add_column(
        "categories",
        sa.Column("display_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "categories",
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column(
        "categories",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE categories SET "
        "name_en = name, name_ar = name, "
        "slug = 'legacy-' || left(replace(id::text, '-', ''), 24)"
    )
    op.alter_column("categories", "name_en", nullable=False)
    op.alter_column("categories", "name_ar", nullable=False)
    op.alter_column("categories", "slug", nullable=False)
    op.create_foreign_key(
        "fk_categories_master_category",
        "categories",
        "master_categories",
        ["master_category_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_categories_tenant_slug",
        "categories",
        ["tenant_id", "slug"],
    )
    op.create_check_constraint(
        "ck_categories_display_order_nonnegative",
        "categories",
        "display_order >= 0",
    )
    op.create_check_constraint(
        "ck_categories_archive_state",
        "categories",
        "(is_active AND archived_at IS NULL) OR (NOT is_active AND archived_at IS NOT NULL)",
    )
    op.create_index(
        "ix_categories_master_category_id",
        "categories",
        ["master_category_id"],
    )
    op.create_index(
        "ix_categories_tenant_active_order",
        "categories",
        ["tenant_id", "is_active", "display_order"],
    )
    op.drop_column("categories", "name")

    tenant_expression = (
        "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
    )
    user_expression = "user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid"
    op.execute('DROP POLICY "tenant_memberships_tenant_isolation" ON "tenant_memberships"')
    op.execute(
        'CREATE POLICY "tenant_memberships_select_scope" ON "tenant_memberships" '
        f"FOR SELECT USING ({tenant_expression} OR {user_expression})"
    )
    op.execute(
        'CREATE POLICY "tenant_memberships_insert_scope" ON "tenant_memberships" '
        f"FOR INSERT WITH CHECK ({tenant_expression})"
    )
    op.execute(
        'CREATE POLICY "tenant_memberships_update_scope" ON "tenant_memberships" '
        f"FOR UPDATE USING ({tenant_expression}) WITH CHECK ({tenant_expression})"
    )
    op.execute(
        'CREATE POLICY "tenant_memberships_delete_scope" ON "tenant_memberships" '
        f"FOR DELETE USING ({tenant_expression})"
    )


def downgrade() -> None:
    op.execute('DROP POLICY "tenant_memberships_delete_scope" ON "tenant_memberships"')
    op.execute('DROP POLICY "tenant_memberships_update_scope" ON "tenant_memberships"')
    op.execute('DROP POLICY "tenant_memberships_insert_scope" ON "tenant_memberships"')
    op.execute('DROP POLICY "tenant_memberships_select_scope" ON "tenant_memberships"')
    tenant_expression = (
        "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
    )
    op.execute(
        'CREATE POLICY "tenant_memberships_tenant_isolation" ON "tenant_memberships" '
        f"USING ({tenant_expression}) WITH CHECK ({tenant_expression})"
    )

    op.add_column("categories", sa.Column("name", sa.String(length=200), nullable=True))
    op.execute("UPDATE categories SET name = name_en")
    op.alter_column("categories", "name", nullable=False)
    op.drop_index("ix_categories_tenant_active_order", table_name="categories")
    op.drop_index("ix_categories_master_category_id", table_name="categories")
    op.drop_constraint("ck_categories_archive_state", "categories", type_="check")
    op.drop_constraint("ck_categories_display_order_nonnegative", "categories", type_="check")
    op.drop_constraint("uq_categories_tenant_slug", "categories", type_="unique")
    op.drop_constraint("fk_categories_master_category", "categories", type_="foreignkey")
    op.drop_column("categories", "archived_at")
    op.drop_column("categories", "is_active")
    op.drop_column("categories", "display_order")
    op.drop_column("categories", "slug")
    op.drop_column("categories", "name_ar")
    op.drop_column("categories", "name_en")
    op.drop_column("categories", "master_category_id")
    op.drop_table("master_categories")

    op.drop_constraint("ck_customers_longitude_range", "customers", type_="check")
    op.drop_constraint("ck_customers_latitude_range", "customers", type_="check")
    op.drop_constraint("ck_customers_coordinates_paired", "customers", type_="check")
    op.drop_column("customers", "grade")
    op.drop_column("customers", "longitude")
    op.drop_column("customers", "latitude")
    customer_grade.drop(op.get_bind(), checkfirst=True)
