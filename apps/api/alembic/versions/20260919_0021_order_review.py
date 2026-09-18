"""Order review: delivery date, delivery reminders, cancellation requests.

Revision ID: 20260919_0021
Revises: 20260919_0020
Create Date: 2026-09-19

Phase 5 P5-M5 (PHASE_05.md G/H/I/J; D-049, D-063 boundary). The delivery date is a tenant-local
date set only after confirmation; its reminder is a transactional job record executed in UTC.
Cancellation requests are customer *requests*; the owner decides; approval delegates to the Phase 3
cancellation accounting. Every row is tenant-owned (RLS).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260919_0021"
down_revision: str | None = "20260919_0020"
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
    # Only the arrival notification is unique per order; cancellation requests may repeat.
    op.drop_index("uq_owner_notifications_order_kind", table_name="owner_notifications")
    op.create_index(
        "uq_owner_notifications_order_received",
        "owner_notifications",
        ["tenant_id", "order_id"],
        unique=True,
        postgresql_where=sa.text("order_id IS NOT NULL AND kind = 'ORDER_RECEIVED'"),
    )
    op.add_column("orders", sa.Column("delivery_date", sa.Date(), nullable=True))
    op.add_column("orders", sa.Column("linked_customer_id", postgresql.UUID(as_uuid=True)))
    op.create_foreign_key(
        "fk_orders_linked_customer",
        "orders",
        "customers",
        ["linked_customer_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "delivery_reminders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delivery_date", sa.Date(), nullable=False),
        sa.Column("remind_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="SCHEDULED"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("order_id", name="uq_delivery_reminders_order"),
        sa.CheckConstraint(
            "status IN ('SCHEDULED', 'SENT', 'CANCELLED')", name="ck_delivery_reminders_status"
        ),
    )
    op.create_index("ix_delivery_reminders_due", "delivery_reminders", ["status", "remind_at"])
    _enable_tenant_rls("delivery_reminders")

    op.create_table(
        "order_cancellation_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="PENDING"),
        sa.Column("reason", sa.String(500)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("decided_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("decision_note", sa.String(500)),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED')",
            name="ck_order_cancellation_requests_status",
        ),
    )
    op.create_index(
        "ix_order_cancellation_requests_order",
        "order_cancellation_requests",
        ["tenant_id", "order_id"],
    )
    op.create_index(
        "uq_order_cancellation_requests_pending",
        "order_cancellation_requests",
        ["order_id"],
        unique=True,
        postgresql_where=sa.text("status = 'PENDING'"),
    )
    _enable_tenant_rls("order_cancellation_requests")


def downgrade() -> None:
    op.drop_index("uq_owner_notifications_order_received", table_name="owner_notifications")
    op.create_index(
        "uq_owner_notifications_order_kind",
        "owner_notifications",
        ["tenant_id", "order_id", "kind"],
        unique=True,
        postgresql_where=sa.text("order_id IS NOT NULL"),
    )
    op.drop_table("order_cancellation_requests")
    op.drop_table("delivery_reminders")
    op.drop_constraint("fk_orders_linked_customer", "orders", type_="foreignkey")
    op.drop_column("orders", "linked_customer_id")
    op.drop_column("orders", "delivery_date")
