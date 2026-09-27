"""Driver collection reports and customer notifications.

Revision ID: 20260927_0036
Revises: 20260927_0035
Create Date: 2026-09-27

D-114. A collection report records what the driver says was collected at a delivery; it is not a
payment until the owner confirms it through the existing receipt service. Customer notifications
are shown on the customer's own personalized storefront. Both are tenant tables with row-level
security like the others.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260927_0036"
down_revision: str | None = "20260927_0035"
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


def _uuid(
    name: str, target: str | None = None, ondelete: str = "RESTRICT", **kw: bool
) -> sa.Column:
    if target is None:
        return sa.Column(name, postgresql.UUID(as_uuid=True), **kw)
    return sa.Column(
        name, postgresql.UUID(as_uuid=True), sa.ForeignKey(target, ondelete=ondelete), **kw
    )


def upgrade() -> None:
    op.create_table(
        "collection_reports",
        _uuid("id", primary_key=True),
        _uuid("tenant_id", "tenants.id", "CASCADE", nullable=False),
        _uuid("task_id", "delivery_tasks.id", nullable=False),
        _uuid("invoice_id", "invoices.id", nullable=False),
        _uuid("customer_id", "customers.id", nullable=False),
        _uuid("reporter_membership_id", "tenant_memberships.id", nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("amount", sa.Numeric(20, 4)),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="PENDING"),
        _uuid("idempotency_key", nullable=False),
        _uuid("confirmed_payment_id", "payments.id"),
        sa.Column("reason", sa.String(500)),
        _uuid("decided_by_user_id", "users.id", "SET NULL"),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "kind IN ('FULL', 'PARTIAL', 'NONE')", name="ck_collection_reports_kind"
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'CONFIRMED', 'REJECTED')", name="ck_collection_reports_status"
        ),
        sa.CheckConstraint(
            "(kind = 'NONE') = (amount IS NULL) AND (amount IS NULL OR amount > 0)",
            name="ck_collection_reports_amount",
        ),
        sa.CheckConstraint(
            "confirmed_payment_id IS NULL OR (status = 'CONFIRMED' AND kind <> 'NONE')",
            name="ck_collection_reports_payment",
        ),
        sa.UniqueConstraint("tenant_id", "task_id", name="uq_collection_reports_task"),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_collection_reports_idempotency"
        ),
    )
    op.create_index(
        "ix_collection_reports_tenant_status_created",
        "collection_reports",
        ["tenant_id", "status", "created_at"],
    )
    _enable_tenant_rls("collection_reports")

    op.create_table(
        "customer_notifications",
        _uuid("id", primary_key=True),
        _uuid("tenant_id", "tenants.id", "CASCADE", nullable=False),
        _uuid("customer_id", "customers.id", "CASCADE", nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("read_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_customer_notifications_tenant_customer_created",
        "customer_notifications",
        ["tenant_id", "customer_id", "created_at"],
    )
    _enable_tenant_rls("customer_notifications")


def downgrade() -> None:
    op.drop_index(
        "ix_customer_notifications_tenant_customer_created", table_name="customer_notifications"
    )
    op.drop_table("customer_notifications")
    op.drop_index("ix_collection_reports_tenant_status_created", table_name="collection_reports")
    op.drop_table("collection_reports")
