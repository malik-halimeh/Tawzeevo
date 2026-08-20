"""Create Tawzeevo Phase 1 foundation tables.

Revision ID: 20260820_0001
Revises: None
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260820_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

user_type = postgresql.ENUM("admin", "client", name="system_user_type", create_type=False)
tenant_status = postgresql.ENUM(
    "ACTIVE", "SUSPENDED", "CLOSED", name="tenant_status", create_type=False
)
tenant_role = postgresql.ENUM("owner", "driver", name="tenant_role", create_type=False)
application_status = postgresql.ENUM(
    "PENDING", "APPROVED", "REJECTED", name="tenant_application_status", create_type=False
)
suspension_reason = postgresql.ENUM(
    "SUBSCRIPTION_OVERDUE",
    "ADMINISTRATIVE",
    "SECURITY",
    "OTHER",
    name="suspension_reason",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    user_type.create(bind, checkfirst=True)
    tenant_status.create(bind, checkfirst=True)
    tenant_role.create(bind, checkfirst=True)
    application_status.create(bind, checkfirst=True)
    suspension_reason.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("phone_raw", sa.String(length=64), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("type", user_type, nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("security_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("age BETWEEN 1 AND 120", name="ck_users_age_range"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email_unique", "users", ["email"], unique=True)

    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", tenant_status, server_default="ACTIVE", nullable=False),
        sa.Column("access_until", sa.Date(), nullable=True),
        sa.Column("grace_until", sa.Date(), nullable=True),
        sa.Column("suspension_reason", suspension_reason, nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "grace_until IS NULL OR access_until IS NULL OR grace_until >= access_until",
            name="ck_tenants_grace_not_before_access",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tenants_name", "tenants", ["name"], unique=False)

    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=255), nullable=False),
        sa.Column("security_version", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(length=80), nullable=True),
        sa.Column("replaced_by_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["replaced_by_session_id"], ["auth_sessions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("refresh_token_hash"),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"], unique=False)

    op.create_table(
        "tenant_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", tenant_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tenant_memberships_tenant_user_unique",
        "tenant_memberships",
        ["tenant_id", "user_id"],
        unique=True,
    )
    op.create_index("ix_tenant_memberships_tenant_id", "tenant_memberships", ["tenant_id"])
    op.create_index("ix_tenant_memberships_user_id", "tenant_memberships", ["user_id"])

    op.create_table(
        "tenant_invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invited_email", sa.String(length=320), nullable=False),
        sa.Column("role", tenant_role, nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_tenant_invitations_tenant_id", "tenant_invitations", ["tenant_id"])

    op.create_table(
        "tenant_applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("applicant_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("business_name", sa.String(length=200), nullable=False),
        sa.Column("status", application_status, server_default="PENDING", nullable=False),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["applicant_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id"),
    )
    op.create_index(
        "ix_tenant_applications_applicant_user_id",
        "tenant_applications",
        ["applicant_user_id"],
    )
    op.create_index("ix_tenant_applications_status", "tenant_applications", ["status"])

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"])
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"])
    op.create_index("ix_audit_events_tenant_id", "audit_events", ["tenant_id"])

    tenant_expression = (
        "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
    )
    for table in ("tenant_memberships", "tenant_invitations"):
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(
            f'CREATE POLICY "{table}_tenant_isolation" ON "{table}" '
            f"USING ({tenant_expression}) WITH CHECK ({tenant_expression})"
        )

    op.execute('ALTER TABLE "audit_events" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "audit_events" FORCE ROW LEVEL SECURITY')
    op.execute(
        'CREATE POLICY "audit_events_tenant_isolation" ON "audit_events" '
        f"USING ({tenant_expression}) WITH CHECK ({tenant_expression})"
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("tenant_applications")
    op.drop_table("tenant_invitations")
    op.drop_table("tenant_memberships")
    op.drop_table("auth_sessions")
    op.drop_table("tenants")
    op.drop_table("users")

    bind = op.get_bind()
    suspension_reason.drop(bind, checkfirst=True)
    application_status.drop(bind, checkfirst=True)
    tenant_role.drop(bind, checkfirst=True)
    tenant_status.drop(bind, checkfirst=True)
    user_type.drop(bind, checkfirst=True)
