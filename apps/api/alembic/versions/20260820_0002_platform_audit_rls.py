"""Permit explicitly scoped platform audit inserts.

Revision ID: 20260820_0002
Revises: 20260820_0001
Create Date: 2026-08-20
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260820_0002"
down_revision: str | None = "20260820_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        'CREATE POLICY "audit_events_platform_insert" ON "audit_events" '
        "FOR INSERT WITH CHECK ("
        "tenant_id IS NULL AND current_setting('app.platform_audit', true) = 'true'"
        ")"
    )


def downgrade() -> None:
    op.execute('DROP POLICY "audit_events_platform_insert" ON "audit_events"')
