"""Add tenant debt settings and preserve zero-delta invoice adjustments.

Revision ID: 20260827_0010
Revises: 20260827_0009
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260827_0010"
down_revision: str | None = "20260827_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenant_financial_settings",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_overdue_threshold_days", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "customer_overdue_threshold_days IS NULL "
            "OR customer_overdue_threshold_days >= 0",
            name="ck_tenant_financial_settings_overdue_nonnegative",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tenant_id"),
    )
    tenant_expression = (
        "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
    )
    op.execute("ALTER TABLE tenant_financial_settings ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_financial_settings FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_financial_settings_tenant_isolation "
        "ON tenant_financial_settings "
        f"USING ({tenant_expression}) WITH CHECK ({tenant_expression})"
    )

    op.drop_constraint(
        "ck_customer_ledger_amount_nonzero",
        "customer_ledger_entries",
        type_="check",
    )
    op.create_check_constraint(
        "ck_customer_ledger_amount_nonzero",
        "customer_ledger_entries",
        "signed_amount <> 0 OR entry_type = 'INVOICE_ADJUSTMENT'",
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE customer_ledger_entries "
        "DISABLE TRIGGER customer_ledger_entries_immutable"
    )
    op.execute(
        "DELETE FROM customer_ledger_entries "
        "WHERE entry_type = 'INVOICE_ADJUSTMENT' AND signed_amount = 0"
    )
    op.execute(
        "ALTER TABLE customer_ledger_entries "
        "ENABLE TRIGGER customer_ledger_entries_immutable"
    )
    op.drop_constraint(
        "ck_customer_ledger_amount_nonzero",
        "customer_ledger_entries",
        type_="check",
    )
    op.create_check_constraint(
        "ck_customer_ledger_amount_nonzero",
        "customer_ledger_entries",
        "signed_amount <> 0",
    )
    op.drop_table("tenant_financial_settings")
