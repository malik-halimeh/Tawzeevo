"""Index for the supplier payment history.

Revision ID: 20260927_0032
Revises: 20260921_0031
Create Date: 2026-09-27

The owner's supplier payment history (D-100) lists one business's supplier payments, optionally
for one supplier, newest first. A partial index on the supplier rows of `payments` serves it; the
table, its rows and every financial rule are unchanged.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927_0032"
down_revision: str | None = "20260921_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_payments_tenant_supplier_paid_at",
        "payments",
        ["tenant_id", "supplier_id", "paid_at"],
        postgresql_where=sa.text("supplier_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_payments_tenant_supplier_paid_at", table_name="payments")
