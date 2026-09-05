"""Add versioned master-catalog import provenance and quality evidence.

Revision ID: 20260826_0007
Revises: 20260826_0006
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260826_0007"
down_revision: str | None = "20260826_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamp_columns() -> list[sa.Column[object]]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "master_catalog_imports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_name", sa.String(length=200), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("source_license", sa.String(length=100), nullable=False),
        sa.Column("source_license_url", sa.String(length=500), nullable=False),
        sa.Column("source_attribution", sa.String(length=300), nullable=False),
        sa.Column("import_version", sa.String(length=120), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dataset_sha256", sa.String(length=64), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("inserted_count", sa.Integer(), nullable=False),
        sa.Column("reused_count", sa.Integer(), nullable=False),
        sa.Column("rejected_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("quality_report", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "length(dataset_sha256) = 64",
            name="ck_catalog_imports_sha256_length",
        ),
        sa.CheckConstraint(
            "record_count >= 0 AND inserted_count >= 0 AND reused_count >= 0 "
            "AND rejected_count >= 0 AND duplicate_count >= 0",
            name="ck_catalog_imports_counts_nonnegative",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("import_version", name="uq_master_catalog_imports_version"),
    )
    op.execute('ALTER TABLE "master_catalog_imports" ENABLE ROW LEVEL SECURITY')

    op.create_table(
        "master_product_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("master_product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("catalog_import_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_product_id", sa.String(length=100), nullable=False),
        sa.Column("source_product_url", sa.String(length=500), nullable=False),
        sa.Column("source_categories", sa.String(length=1000), nullable=False),
        sa.Column("source_revision", sa.String(length=100), nullable=False),
        sa.Column("source_last_modified_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["catalog_import_id"],
            ["master_catalog_imports.id"],
            name="fk_master_product_sources_import",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["master_product_id"],
            ["master_products.id"],
            name="fk_master_product_sources_product",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "catalog_import_id",
            "source_product_id",
            name="uq_master_product_sources_import_product",
        ),
    )
    op.create_index(
        "ix_master_product_sources_catalog_import_id",
        "master_product_sources",
        ["catalog_import_id"],
    )
    op.create_index(
        "ix_master_product_sources_master_product_id",
        "master_product_sources",
        ["master_product_id"],
    )
    op.create_index(
        "ix_master_product_sources_product_import",
        "master_product_sources",
        ["master_product_id", "catalog_import_id"],
    )
    op.execute('ALTER TABLE "master_product_sources" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    op.drop_table("master_product_sources")
    op.drop_table("master_catalog_imports")
