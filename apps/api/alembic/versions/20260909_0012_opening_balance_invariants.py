"""Enforce one immutable opening balance per party and currency.

Revision ID: 20260909_0012
Revises: 20260827_0011
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260909_0012"
down_revision: str | None = "20260827_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
            FROM customer_ledger_entries
            WHERE entry_type = 'OPENING_BALANCE'
            GROUP BY tenant_id, customer_id, currency
            HAVING count(*) > 1
          ) THEN
            RAISE EXCEPTION USING MESSAGE =
              'Duplicate customer openings require reconciliation before migration';
          END IF;
          IF EXISTS (
            SELECT 1
            FROM supplier_ledger_entries
            WHERE entry_type = 'OPENING_BALANCE'
            GROUP BY tenant_id, supplier_id, currency
            HAVING count(*) > 1
          ) THEN
            RAISE EXCEPTION USING MESSAGE =
              'Duplicate supplier openings require reconciliation before migration';
          END IF;
        END $$;
        """
    )
    op.create_index(
        "uq_customer_ledger_one_opening",
        "customer_ledger_entries",
        ["tenant_id", "customer_id", "currency"],
        unique=True,
        postgresql_where=sa.text("entry_type = 'OPENING_BALANCE'"),
    )
    op.create_index(
        "uq_supplier_ledger_one_opening",
        "supplier_ledger_entries",
        ["tenant_id", "supplier_id", "currency"],
        unique=True,
        postgresql_where=sa.text("entry_type = 'OPENING_BALANCE'"),
    )
    op.create_check_constraint(
        "ck_customer_ledger_opening_correction_link",
        "customer_ledger_entries",
        "entry_type <> 'OPENING_BALANCE_CORRECTION' OR reverses_entry_id IS NOT NULL",
    )
    op.create_check_constraint(
        "ck_supplier_ledger_opening_correction_link",
        "supplier_ledger_entries",
        "entry_type <> 'OPENING_BALANCE_CORRECTION' OR reverses_entry_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_supplier_ledger_opening_correction_link",
        "supplier_ledger_entries",
        type_="check",
    )
    op.drop_constraint(
        "ck_customer_ledger_opening_correction_link",
        "customer_ledger_entries",
        type_="check",
    )
    op.drop_index("uq_supplier_ledger_one_opening", table_name="supplier_ledger_entries")
    op.drop_index("uq_customer_ledger_one_opening", table_name="customer_ledger_entries")
