"""Add pricing-v1 grade rules and provider-neutral product image metadata.

Revision ID: 20260826_0006
Revises: 20260825_0005
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260826_0006"
down_revision: str | None = "20260825_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

customer_grade = postgresql.ENUM("A+", "A", "B+", "B", name="customer_grade", create_type=False)
price_resolution_source = postgresql.ENUM(
    "NORMAL",
    "GRADE_DISCOUNT",
    "EXPLICIT_GRADE_PRICE",
    name="price_resolution_source",
    create_type=False,
)


def _timestamp_columns() -> list[sa.Column[object]]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
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


def upgrade() -> None:
    price_resolution_source.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "tenant_grade_discounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("grade", customer_grade, nullable=False),
        sa.Column("discount_percent", sa.Numeric(precision=7, scale=4), nullable=False),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "discount_percent >= 0 AND discount_percent <= 100",
            name="ck_tenant_grade_discounts_percent_range",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], ondelete="CASCADE", name="fk_grade_discounts_tenant"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "grade", name="uq_tenant_grade_discounts_tenant_grade"),
    )
    op.create_index("ix_tenant_grade_discounts_tenant_id", "tenant_grade_discounts", ["tenant_id"])
    _enable_tenant_rls("tenant_grade_discounts")

    op.create_table(
        "product_grade_prices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("grade", customer_grade, nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=20, scale=4), nullable=False),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "unit_price >= 0", name="ck_product_grade_prices_unit_price_nonnegative"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            ondelete="CASCADE",
            name="fk_product_grade_prices_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_product_id", "tenant_id"],
            ["tenant_products.id", "tenant_products.tenant_id"],
            ondelete="CASCADE",
            name="fk_product_grade_prices_product_tenant",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "tenant_product_id",
            "grade",
            name="uq_product_grade_prices_product_grade",
        ),
    )
    op.create_index("ix_product_grade_prices_tenant_id", "product_grade_prices", ["tenant_id"])
    op.create_index(
        "ix_product_grade_prices_product_tenant",
        "product_grade_prices",
        ["tenant_product_id", "tenant_id"],
    )
    _enable_tenant_rls("product_grade_prices")

    image_columns: list[sa.Column[object]] = [
        sa.Column("object_key", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=50), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("alt_text", sa.String(length=300), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
    ]
    image_checks = (
        sa.CheckConstraint("byte_size > 0", name="ck_master_product_images_byte_size_positive"),
        sa.CheckConstraint(
            "width > 0 AND height > 0", name="ck_master_product_images_dimensions_positive"
        ),
        sa.CheckConstraint(
            "display_order >= 0", name="ck_master_product_images_display_order_nonnegative"
        ),
    )
    op.create_table(
        "master_product_images",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("master_product_id", postgresql.UUID(as_uuid=True), nullable=False),
        *image_columns,
        *_timestamp_columns(),
        *image_checks,
        sa.ForeignKeyConstraint(
            ["master_product_id"],
            ["master_products.id"],
            ondelete="CASCADE",
            name="fk_master_product_images_product",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key", name="uq_master_product_images_object_key"),
    )
    op.create_index(
        "ix_master_product_images_master_product_id",
        "master_product_images",
        ["master_product_id"],
    )
    op.create_index(
        "ix_master_product_images_product_order",
        "master_product_images",
        ["master_product_id", "display_order", "id"],
    )
    op.execute('ALTER TABLE "master_product_images" ENABLE ROW LEVEL SECURITY')

    op.create_table(
        "tenant_product_images",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("object_key", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=50), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("alt_text", sa.String(length=300), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        *_timestamp_columns(),
        sa.CheckConstraint("byte_size > 0", name="ck_tenant_product_images_byte_size_positive"),
        sa.CheckConstraint(
            "width > 0 AND height > 0", name="ck_tenant_product_images_dimensions_positive"
        ),
        sa.CheckConstraint(
            "display_order >= 0", name="ck_tenant_product_images_display_order_nonnegative"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            ondelete="CASCADE",
            name="fk_tenant_product_images_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_product_id", "tenant_id"],
            ["tenant_products.id", "tenant_products.tenant_id"],
            ondelete="CASCADE",
            name="fk_tenant_product_images_product_tenant",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key", name="uq_tenant_product_images_object_key"),
    )
    op.create_index("ix_tenant_product_images_tenant_id", "tenant_product_images", ["tenant_id"])
    op.create_index(
        "ix_tenant_product_images_product_tenant_order",
        "tenant_product_images",
        ["tenant_product_id", "tenant_id", "display_order", "id"],
    )
    _enable_tenant_rls("tenant_product_images")

    op.add_column("invoice_items", sa.Column("customer_grade", customer_grade, nullable=True))
    op.add_column(
        "invoice_items",
        sa.Column(
            "price_source",
            price_resolution_source,
            server_default=sa.text("'NORMAL'"),
            nullable=False,
        ),
    )
    op.add_column(
        "invoice_items",
        sa.Column("grade_discount_percent", sa.Numeric(precision=7, scale=4), nullable=True),
    )
    op.create_check_constraint(
        "ck_invoice_items_grade_discount_percent_range",
        "invoice_items",
        "grade_discount_percent IS NULL OR "
        "(grade_discount_percent >= 0 AND grade_discount_percent <= 100)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_invoice_items_grade_discount_percent_range", "invoice_items", type_="check"
    )
    op.drop_column("invoice_items", "grade_discount_percent")
    op.drop_column("invoice_items", "price_source")
    op.drop_column("invoice_items", "customer_grade")
    op.drop_table("tenant_product_images")
    op.drop_table("master_product_images")
    op.drop_table("product_grade_prices")
    op.drop_table("tenant_grade_discounts")
    price_resolution_source.drop(op.get_bind(), checkfirst=True)
