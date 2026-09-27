"""Index for the owner's customers list.

Revision ID: 20260927_0033
Revises: 20260927_0032
Create Date: 2026-09-27

The customers page (D-101) lists one business's customers by name, 20 per page. An index on
(tenant_id, name) serves it; no rows or rules change.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260927_0033"
down_revision: str | None = "20260927_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_customers_tenant_name", "customers", ["tenant_id", "name"])


def downgrade() -> None:
    op.drop_index("ix_customers_tenant_name", table_name="customers")
