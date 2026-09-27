"""Web push subscriptions.

Revision ID: 20260927_0037
Revises: 20260927_0036
Create Date: 2026-09-27

D-116. A subscription belongs to a person: row-level security lets a user see and change only
their own rows (`app.current_user_id`), and the sender reads them only inside a transaction that
binds `app.push_delivery`. `tenant_id` records where it was turned on and is not a tenant scope.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260927_0037"
down_revision: str | None = "20260927_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OWNER_OR_SENDER = (
    "user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid "
    "OR current_setting('app.push_delivery', true) = 'true'"
)


def upgrade() -> None:
    op.create_table(
        "push_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="SET NULL"),
        ),
        sa.Column("endpoint", sa.String(1000), nullable=False),
        sa.Column("p256dh", sa.String(200), nullable=False),
        sa.Column("auth", sa.String(100), nullable=False),
        sa.Column("user_agent", sa.String(300)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_failure_at", sa.DateTime(timezone=True)),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("user_id", "endpoint", name="uq_push_subscriptions_user_endpoint"),
    )
    op.execute('ALTER TABLE "push_subscriptions" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "push_subscriptions" FORCE ROW LEVEL SECURITY')
    op.execute(
        'CREATE POLICY "push_subscriptions_owner_or_sender" ON "push_subscriptions" '
        f"USING ({OWNER_OR_SENDER}) WITH CHECK ({OWNER_OR_SENDER})"
    )


def downgrade() -> None:
    op.drop_table("push_subscriptions")
