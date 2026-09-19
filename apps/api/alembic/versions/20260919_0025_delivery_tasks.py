"""Delivery tasks with a neutral assignee membership (owner or driver).

Revision ID: 20260919_0025
Revises: 20260919_0024
Create Date: 2026-09-19

Phase 7 P7-M1 (PHASE_07.md A/B/K; D-063). A task belongs to one CONFIRMED invoice (optionally
the storefront order behind it) and to exactly one active membership — the owner themself or a
driver; the lifecycle is ASSIGNED → COMPLETED / CANCELLED with both ends terminal. Only one
ASSIGNED task may exist per invoice (a mistaken completion is followed by a new task). Tasks
never touch invoices. The actual performer is recorded at completion. Tenant-owned (RLS).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260919_0025"
down_revision: str | None = "20260919_0024"
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
        "delivery_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True)),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="ASSIGNED"),
        sa.Column("delivery_date", sa.Date()),
        sa.Column("route_sequence", sa.Integer()),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("amount_to_collect", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("notes", sa.String(1000)),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("performed_by_membership_id", postgresql.UUID(as_uuid=True)),
        sa.Column("completion_note", sa.String(500)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancel_reason", sa.String(500)),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["customer_id", "tenant_id"],
            ["customers.id", "customers.tenant_id"],
            ondelete="RESTRICT",
            name="fk_delivery_tasks_customer_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_membership_id"], ["tenant_memberships.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["performed_by_membership_id"], ["tenant_memberships.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_delivery_tasks_id_tenant"),
        sa.CheckConstraint(
            "status IN ('ASSIGNED', 'COMPLETED', 'CANCELLED')", name="ck_delivery_tasks_status"
        ),
        sa.CheckConstraint(
            "(completed_at IS NULL) = (performed_by_membership_id IS NULL)",
            name="ck_delivery_tasks_completion_pair",
        ),
        sa.CheckConstraint(
            "(cancelled_at IS NULL) = (cancel_reason IS NULL)",
            name="ck_delivery_tasks_cancel_pair",
        ),
        sa.CheckConstraint("amount_to_collect >= 0", name="ck_delivery_tasks_amount_nonneg"),
    )
    op.create_index(
        "ix_delivery_tasks_tenant_date_status",
        "delivery_tasks",
        ["tenant_id", "delivery_date", "status"],
    )
    op.create_index(
        "ix_delivery_tasks_assignee", "delivery_tasks", ["tenant_id", "assigned_membership_id"]
    )
    op.create_index(
        "uq_delivery_tasks_open_invoice",
        "delivery_tasks",
        ["invoice_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ASSIGNED'"),
    )
    _enable_tenant_rls("delivery_tasks")


def downgrade() -> None:
    op.drop_table("delivery_tasks")
