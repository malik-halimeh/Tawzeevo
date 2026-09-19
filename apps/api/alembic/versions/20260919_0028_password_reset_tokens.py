"""Password reset tokens.

Revision ID: 20260919_0028
Revises: 20260919_0027
Create Date: 2026-09-19

Phase 9 P9-M1 (PHASE_09.md C, D-077). One-time password reset tokens stored as SHA-256 hashes
with a short expiry and a single use; the reset bumps the user's security version so every
session and access token dies. Platform-level table (users are not tenant-scoped).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260919_0028"
down_revision: str | None = "20260919_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("token_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("password_reset_tokens")
