"""Separate master and tenant products with explicit barcode ownership.

Revision ID: 20260825_0005
Revises: 20260825_0004
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260825_0005"
down_revision: str | None = "20260825_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

barcode_package_level = postgresql.ENUM(
    "PIECE", "BOX", name="barcode_package_level", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    barcode_package_level.create(bind, checkfirst=True)

    op.create_table(
        "master_products",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("master_category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["master_category_id"],
            ["master_categories.id"],
            name="fk_master_products_category",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_master_products_master_category_id",
        "master_products",
        ["master_category_id"],
    )
    op.execute('ALTER TABLE "master_products" ENABLE ROW LEVEL SECURITY')

    op.create_table(
        "master_barcodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("master_product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("barcode", sa.String(length=64), nullable=False),
        sa.Column("package_level", barcode_package_level, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["master_product_id"],
            ["master_products.id"],
            name="fk_master_barcodes_product",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("barcode", name="uq_master_barcodes_barcode"),
    )
    op.create_index(
        "ix_master_barcodes_master_product_id",
        "master_barcodes",
        ["master_product_id"],
    )
    op.execute('ALTER TABLE "master_barcodes" ENABLE ROW LEVEL SECURITY')

    op.add_column(
        "tenant_products",
        sa.Column("master_product_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "tenant_products",
        sa.Column("is_published", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_foreign_key(
        "fk_tenant_products_master_product",
        "tenant_products",
        "master_products",
        ["master_product_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_tenant_products_master_product_id",
        "tenant_products",
        ["master_product_id"],
    )
    op.create_index(
        "ix_tenant_products_tenant_published",
        "tenant_products",
        ["tenant_id", "is_published"],
    )
    op.create_unique_constraint(
        "uq_tenant_products_tenant_master_product",
        "tenant_products",
        ["tenant_id", "master_product_id"],
    )

    op.create_table(
        "tenant_barcodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("barcode", sa.String(length=64), nullable=False),
        sa.Column("package_level", barcode_package_level, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_tenant_barcodes_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_product_id", "tenant_id"],
            ["tenant_products.id", "tenant_products.tenant_id"],
            name="fk_tenant_barcodes_product_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tenant_barcodes_tenant_id", "tenant_barcodes", ["tenant_id"])
    op.create_index(
        "ix_tenant_barcodes_product_tenant",
        "tenant_barcodes",
        ["tenant_product_id", "tenant_id"],
    )
    op.create_index(
        "ix_tenant_barcodes_tenant_barcode_unique",
        "tenant_barcodes",
        ["tenant_id", "barcode"],
        unique=True,
    )
    op.execute(
        "INSERT INTO tenant_barcodes "
        "(id, tenant_id, tenant_product_id, barcode, package_level) "
        "SELECT gen_random_uuid(), tenant_id, id, barcode, 'PIECE'::barcode_package_level "
        "FROM tenant_products"
    )
    op.drop_constraint("uq_tenant_products_tenant_barcode", "tenant_products", type_="unique")
    op.drop_column("tenant_products", "barcode")

    tenant_expression = (
        "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
    )
    op.execute('ALTER TABLE "tenant_barcodes" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "tenant_barcodes" FORCE ROW LEVEL SECURITY')
    op.execute(
        'CREATE POLICY "tenant_barcodes_tenant_isolation" ON "tenant_barcodes" '
        f"USING ({tenant_expression}) WITH CHECK ({tenant_expression})"
    )


def downgrade() -> None:
    op.add_column("tenant_products", sa.Column("barcode", sa.String(length=64), nullable=True))
    op.execute(
        "UPDATE tenant_products AS product SET barcode = COALESCE("
        "(SELECT barcode FROM tenant_barcodes "
        " WHERE tenant_product_id = product.id AND tenant_id = product.tenant_id "
        " ORDER BY package_level, created_at, id LIMIT 1), "
        "(SELECT barcode FROM master_barcodes "
        " WHERE master_product_id = product.master_product_id "
        " ORDER BY package_level, created_at, id LIMIT 1), "
        "'legacy-' || left(replace(product.id::text, '-', ''), 24))"
    )
    op.alter_column("tenant_products", "barcode", nullable=False)
    op.create_unique_constraint(
        "uq_tenant_products_tenant_barcode",
        "tenant_products",
        ["tenant_id", "barcode"],
    )

    op.drop_table("tenant_barcodes")
    op.drop_constraint(
        "uq_tenant_products_tenant_master_product",
        "tenant_products",
        type_="unique",
    )
    op.drop_index("ix_tenant_products_tenant_published", table_name="tenant_products")
    op.drop_index("ix_tenant_products_master_product_id", table_name="tenant_products")
    op.drop_constraint("fk_tenant_products_master_product", "tenant_products", type_="foreignkey")
    op.drop_column("tenant_products", "is_published")
    op.drop_column("tenant_products", "master_product_id")
    op.drop_table("master_barcodes")
    op.drop_table("master_products")
    barcode_package_level.drop(op.get_bind(), checkfirst=True)
