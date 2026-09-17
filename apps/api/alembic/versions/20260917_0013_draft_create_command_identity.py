"""One invoice header per tenant draft-create command.

Revision ID: 20260917_0013
Revises: 20260909_0012
Create Date: 2026-09-17

D-045: the client_command_id of an invoice's first revision identifies the create command for the
whole tenant, so a retried create returns the same header instead of a duplicate draft.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260917_0013"
down_revision: str | None = "20260909_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
            FROM invoice_revisions
            WHERE predecessor_revision_id IS NULL
            GROUP BY tenant_id, client_command_id
            HAVING count(*) > 1
          ) THEN
            RAISE EXCEPTION USING MESSAGE =
              'Duplicate draft-create commands require reconciliation before migration';
          END IF;
        END $$;
        """
    )
    op.create_index(
        "uq_invoice_revisions_create_command",
        "invoice_revisions",
        ["tenant_id", "client_command_id"],
        unique=True,
        postgresql_where=sa.text("predecessor_revision_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_invoice_revisions_create_command", table_name="invoice_revisions")
