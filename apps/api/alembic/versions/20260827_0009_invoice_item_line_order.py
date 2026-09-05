"""Make invoice revision item order deterministic.

Revision ID: 20260827_0009
Revises: 20260826_0008
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260827_0009"
down_revision: str | None = "20260826_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "invoice_revision_items",
        sa.Column("line_number", sa.Integer(), nullable=True),
    )
    op.execute(
        "ALTER TABLE invoice_revision_items "
        "DISABLE TRIGGER invoice_revision_items_immutable"
    )
    op.execute(
        "WITH ordered AS ("
        "SELECT id, row_number() OVER ("
        "PARTITION BY tenant_id, invoice_revision_id ORDER BY created_at, id"
        ") AS line_number FROM invoice_revision_items"
        ") UPDATE invoice_revision_items item SET line_number = ordered.line_number "
        "FROM ordered WHERE ordered.id = item.id"
    )
    op.execute(
        "ALTER TABLE invoice_revision_items "
        "ENABLE TRIGGER invoice_revision_items_immutable"
    )
    op.alter_column("invoice_revision_items", "line_number", nullable=False)
    op.create_check_constraint(
        "ck_invoice_revision_items_line_number_positive",
        "invoice_revision_items",
        "line_number > 0",
    )
    op.create_unique_constraint(
        "uq_invoice_revision_items_line_number",
        "invoice_revision_items",
        ["tenant_id", "invoice_revision_id", "line_number"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_invoice_revision_items_line_number",
        "invoice_revision_items",
        type_="unique",
    )
    op.drop_constraint(
        "ck_invoice_revision_items_line_number_positive",
        "invoice_revision_items",
        type_="check",
    )
    op.drop_column("invoice_revision_items", "line_number")
