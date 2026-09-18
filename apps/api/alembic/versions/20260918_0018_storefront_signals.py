"""Storefront interactions, monthly rollups and featured campaigns.

Revision ID: 20260918_0018
Revises: 20260918_0017
Create Date: 2026-09-18

Phase 5 (PHASE_05.md D/K/N; D-048, D-051, D-062). Views are pseudonymous (a hashed session key,
no identity); purchases are read from confirmed, non-cancelled sales and never stored twice.
Raw view rows are rolled up into monthly counts after 90 days. Every row is tenant-owned (RLS).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260918_0018"
down_revision: str | None = "20260918_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_EXPRESSION = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"


def _enable_tenant_rls(table_name: str) -> None:
    op.execute(f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table_name}" FORCE ROW LEVEL SECURITY')
    op.execute(
        f'CREATE POLICY "{table_name}_tenant_isolation" ON "{table_name}" '
        f"USING ({TENANT_EXPRESSION}) WITH CHECK ({TENANT_EXPRESSION})"
    )


def upgrade() -> None:
    op.create_table(
        "product_interactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_key", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False, server_default="VIEW"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_product_id"], ["tenant_products.id"], ondelete="CASCADE"),
        sa.CheckConstraint("kind IN ('VIEW')", name="ck_product_interactions_kind"),
    )
    op.create_index(
        "ix_product_interactions_dedupe",
        "product_interactions",
        ["tenant_id", "tenant_product_id", "session_key", "occurred_at"],
    )
    op.create_index(
        "ix_product_interactions_tenant_occurred",
        "product_interactions",
        ["tenant_id", "occurred_at"],
    )
    _enable_tenant_rls("product_interactions")

    op.create_table(
        "product_interaction_rollups",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_product_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("month", sa.Date(), primary_key=True),
        sa.Column("views", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_product_id"], ["tenant_products.id"], ondelete="CASCADE"),
    )
    _enable_tenant_rls("product_interaction_rollups")

    op.create_table(
        "featured_campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_product_id"], ["tenant_products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint("ends_at > starts_at", name="ck_featured_campaigns_interval"),
    )
    op.create_index(
        "ix_featured_campaigns_tenant_window",
        "featured_campaigns",
        ["tenant_id", "starts_at", "ends_at"],
    )
    _enable_tenant_rls("featured_campaigns")


def downgrade() -> None:
    op.drop_table("featured_campaigns")
    op.drop_table("product_interaction_rollups")
    op.drop_table("product_interactions")
