"""Pickup reports: what a runner picked up, waiting for the owner.

Revision ID: 20260927_0034
Revises: 20260927_0033
Create Date: 2026-09-27

D-106. A report is not a purchase; the owner's confirmation records one purchase through the
existing purchase service. Tenant row-level security like the other tenant tables.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260927_0034"
down_revision: str | None = "20260927_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_EXPRESSION = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "pickup_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "procurement_list_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("procurement_lists.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "supplier_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenant_suppliers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "reporter_membership_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenant_memberships.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(10), nullable=False, server_default="PENDING"),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("lines", postgresql.JSONB(), nullable=False),
        sa.Column("notes", sa.String(500)),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "confirmed_purchase_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("supplier_purchases.id", ondelete="RESTRICT"),
        ),
        sa.Column("reason", sa.String(500)),
        sa.Column(
            "decided_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'CONFIRMED', 'REJECTED')", name="ck_pickup_reports_status"
        ),
        sa.CheckConstraint(
            "(status = 'CONFIRMED') = (confirmed_purchase_id IS NOT NULL)",
            name="ck_pickup_reports_confirmed_purchase",
        ),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_pickup_reports_idempotency"),
    )
    op.create_index(
        "ix_pickup_reports_tenant_status_created",
        "pickup_reports",
        ["tenant_id", "status", "created_at"],
    )
    op.execute('ALTER TABLE "pickup_reports" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "pickup_reports" FORCE ROW LEVEL SECURITY')
    op.execute(
        'CREATE POLICY "pickup_reports_tenant_isolation" ON "pickup_reports" '
        f"USING ({TENANT_EXPRESSION}) WITH CHECK ({TENANT_EXPRESSION})"
    )


def downgrade() -> None:
    op.drop_index("ix_pickup_reports_tenant_status_created", table_name="pickup_reports")
    op.drop_table("pickup_reports")
