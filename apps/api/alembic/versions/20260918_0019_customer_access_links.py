"""Personalized customer storefront links and access-policy fields.

Revision ID: 20260918_0019
Revises: 20260918_0018
Create Date: 2026-09-18

Phase 5 P5-M3 (PHASE_05.md C.1; D-071, D-072, D-075). A link maps an opaque capability to the
exact customer; only the SHA-256 of the secret is stored; at most one active link per customer
(partial unique index); no automatic expiry (`expires_at` is a nullable policy field). The access
policy fields exist now so later assurance levels need no schema change; Phase 5 enforces LINK.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260918_0019"
down_revision: str | None = "20260918_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_EXPRESSION = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
POLICY_CHECK = "IN ('LINK', 'VERIFIED', 'ACCOUNT_REQUIRED')"


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("customer_access_policy", sa.String(20), nullable=False, server_default="LINK"),
    )
    op.create_check_constraint(
        "ck_tenants_customer_access_policy", "tenants", f"customer_access_policy {POLICY_CHECK}"
    )
    op.add_column("customers", sa.Column("access_policy_override", sa.String(20), nullable=True))
    op.create_check_constraint(
        "ck_customers_access_policy_override",
        "customers",
        f"access_policy_override IS NULL OR access_policy_override {POLICY_CHECK}",
    )

    op.create_table(
        "customer_access_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_sha256", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_reason", sa.String(40)),
        sa.Column("rotated_from_id", postgresql.UUID(as_uuid=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("token_sha256", name="uq_customer_access_links_token"),
    )
    op.create_index(
        "ix_customer_access_links_tenant_customer",
        "customer_access_links",
        ["tenant_id", "customer_id"],
    )
    op.create_index(
        "uq_customer_access_links_active",
        "customer_access_links",
        ["tenant_id", "customer_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.execute('ALTER TABLE "customer_access_links" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "customer_access_links" FORCE ROW LEVEL SECURITY')
    op.execute(
        'CREATE POLICY "customer_access_links_tenant_isolation" ON "customer_access_links" '
        f"USING ({TENANT_EXPRESSION}) WITH CHECK ({TENANT_EXPRESSION})"
    )


def downgrade() -> None:
    op.drop_table("customer_access_links")
    op.drop_constraint("ck_customers_access_policy_override", "customers", type_="check")
    op.drop_column("customers", "access_policy_override")
    op.drop_constraint("ck_tenants_customer_access_policy", "tenants", type_="check")
    op.drop_column("tenants", "customer_access_policy")
