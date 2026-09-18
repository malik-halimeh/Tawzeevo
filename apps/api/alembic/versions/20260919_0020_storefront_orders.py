"""Storefront guest orders, checkout idempotency, provisional order references, owner notifications.

Revision ID: 20260919_0020
Revises: 20260918_0019
Create Date: 2026-09-19

Phase 5 P5-M4 (PHASE_05.md E/F/G; D-046, D-049, D-072). An order is RECEIVED with an immutable
contact snapshot and a draft invoice (D-033: one order → at most one invoice header). A
personalized link adds only `intended_customer_id` (a hint for owner review). The provisional
reference is a short-lived hashed secret bound to the checkout, separate from D-042 invoice links.
Every row is tenant-owned (RLS).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260919_0020"
down_revision: str | None = "20260918_0019"
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
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="RECEIVED"),
        sa.Column("contact_name", sa.String(200), nullable=False),
        sa.Column("contact_phone", sa.String(32), nullable=False),
        sa.Column("contact_phone_raw", sa.String(64), nullable=False),
        sa.Column("contact_address", sa.String(500), nullable=False),
        sa.Column("notes", sa.String(1000)),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("intended_customer_id", postgresql.UUID(as_uuid=True)),
        sa.Column("intended_assurance", sa.String(12)),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("decided_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("decision_note", sa.String(500)),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["intended_customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "status IN ('RECEIVED', 'CONFIRMED', 'DECLINED', 'CANCELLED')", name="ck_orders_status"
        ),
        sa.CheckConstraint(
            "intended_assurance IS NULL OR intended_assurance IN ('LINK')",
            name="ck_orders_intended_assurance",
        ),
    )
    op.create_index(
        "ix_orders_tenant_status_created", "orders", ["tenant_id", "status", "created_at"]
    )
    _enable_tenant_rls("orders")

    op.create_table(
        "checkout_idempotency",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("response", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
    )
    _enable_tenant_rls("checkout_idempotency")

    op.create_table(
        "order_access_references",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_sha256", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_sha256", name="uq_order_access_references_token"),
    )
    op.create_index(
        "ix_order_access_references_order", "order_access_references", ["tenant_id", "order_id"]
    )
    _enable_tenant_rls("order_access_references")

    op.create_table(
        "owner_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_owner_notifications_tenant_created", "owner_notifications", ["tenant_id", "created_at"]
    )
    op.create_index(
        "uq_owner_notifications_order_kind",
        "owner_notifications",
        ["tenant_id", "order_id", "kind"],
        unique=True,
        postgresql_where=sa.text("order_id IS NOT NULL"),
    )
    _enable_tenant_rls("owner_notifications")


def downgrade() -> None:
    op.drop_table("owner_notifications")
    op.drop_table("order_access_references")
    op.drop_table("checkout_idempotency")
    op.drop_table("orders")
