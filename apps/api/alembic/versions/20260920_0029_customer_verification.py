"""Customer verification challenges and verified sessions.

Revision ID: 20260920_0029
Revises: 20260919_0028
Create Date: 2026-09-20

Phase 9 P9-M5 (PHASE_09.md, D-072/D-073). A verification challenge is a short-lived one-time
code sent to the customer's own phone through a provider-neutral delivery adapter; a verified
session is the hash-only proof that a challenge succeeded, bound to the personalized link it was
started from (revoking or rotating the link ends every session). Orders may now record the
`VERIFIED` assurance they were submitted with. Both tables are tenant-scoped with forced RLS.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260920_0029"
down_revision: str | None = "20260919_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_EXPRESSION = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"


def _rls(table: str) -> None:
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
    op.execute(
        f'CREATE POLICY "{table}_tenant_isolation" ON "{table}" '
        f"USING ({TENANT_EXPRESSION}) WITH CHECK ({TENANT_EXPRESSION})"
    )


def upgrade() -> None:
    op.create_table(
        "customer_verification_challenges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "link_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer_access_links.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code_sha256", sa.String(64), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("consumed_reason", sa.String(30)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_customer_verification_challenges_customer",
        "customer_verification_challenges",
        ["tenant_id", "customer_id", "created_at"],
    )
    _rls("customer_verification_challenges")

    op.create_table(
        "customer_verified_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "link_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer_access_links.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_reason", sa.String(30)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_customer_verified_sessions_customer",
        "customer_verified_sessions",
        ["tenant_id", "customer_id"],
    )
    _rls("customer_verified_sessions")

    # Orders may carry the assurance the checkout was submitted with (LINK or VERIFIED).
    op.drop_constraint("ck_orders_intended_assurance", "orders", type_="check")
    op.create_check_constraint(
        "ck_orders_intended_assurance",
        "orders",
        "intended_assurance IS NULL OR intended_assurance IN ('LINK', 'VERIFIED')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_orders_intended_assurance", "orders", type_="check")
    op.create_check_constraint(
        "ck_orders_intended_assurance",
        "orders",
        "intended_assurance IS NULL OR intended_assurance IN ('LINK')",
    )
    op.drop_table("customer_verified_sessions")
    op.drop_table("customer_verification_challenges")
