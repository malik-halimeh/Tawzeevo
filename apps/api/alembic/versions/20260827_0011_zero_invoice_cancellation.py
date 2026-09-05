"""Preserve the cancellation effect for a zero-value confirmed invoice.

Revision ID: 20260827_0011
Revises: 20260827_0010
Create Date: 2026-08-27
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260827_0011"
down_revision: str | None = "20260827_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_customer_ledger_amount_nonzero",
        "customer_ledger_entries",
        type_="check",
    )
    op.create_check_constraint(
        "ck_customer_ledger_amount_nonzero",
        "customer_ledger_entries",
        "signed_amount <> 0 OR entry_type IN ('INVOICE_ADJUSTMENT', 'INVOICE_REVERSAL')",
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE customer_ledger_entries DISABLE TRIGGER customer_ledger_entries_immutable"
    )
    op.execute(
        "DELETE FROM customer_ledger_entries "
        "WHERE entry_type = 'INVOICE_REVERSAL' AND signed_amount = 0"
    )
    op.execute(
        "ALTER TABLE customer_ledger_entries ENABLE TRIGGER customer_ledger_entries_immutable"
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
