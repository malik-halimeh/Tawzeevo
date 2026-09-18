"""Tenant sync retention floor for tombstone purging (D-053).

Revision ID: 20260918_0015
Revises: 20260918_0014
Create Date: 2026-09-18

After change records older than the retention window are purged, the tenant records the highest
purged change sequence. A device whose cursor is below that floor cannot catch up incrementally and
must re-bootstrap (410 SYNC_REBOOTSTRAP_REQUIRED).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260918_0015"
down_revision: str | None = "20260918_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "sync_retention_floor", sa.BigInteger(), nullable=False, server_default=sa.text("0")
        ),
    )


def downgrade() -> None:
    op.drop_column("tenants", "sync_retention_floor")
