"""Encrypted Google backup: connections, wrapped tenant keys, backup and restore records.

Revision ID: 20260918_0016
Revises: 20260918_0015
Create Date: 2026-09-18

Phase 4 (PHASE_04.md L/N; D-055, D-056, D-057). The Drive refresh token and the per-tenant data
key are stored only wrapped by the environment master key; plaintext keys never reach the
database or the logs. Every row is tenant-owned and protected by forced row-level security.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260918_0016"
down_revision: str | None = "20260918_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_EXPRESSION = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"


def _enable_tenant_rls(table_name: str) -> None:
    op.execute(f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table_name}" FORCE ROW LEVEL SECURITY')
    op.execute(
        f'CREATE POLICY "{table_name}_tenant_isolation" ON "{table_name}" '
        f"USING ({TENANT_EXPRESSION}) WITH CHECK ({TENANT_EXPRESSION})"
    )


def upgrade() -> None:
    op.create_table(
        "tenant_backup_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("account_email", sa.String(320), nullable=False),
        sa.Column("folder_id", sa.String(200), nullable=False),
        sa.Column("folder_name", sa.String(200), nullable=False),
        sa.Column("scopes", sa.String(400), nullable=False),
        sa.Column("wrapped_refresh_token", sa.LargeBinary(), nullable=False),
        sa.Column("kek_id", sa.String(80), nullable=False),
        sa.Column("connected_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disconnected_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(400)),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connected_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("provider IN ('google_drive')", name="ck_backup_connections_provider"),
    )
    op.create_index(
        "ix_tenant_backup_connections_tenant_id", "tenant_backup_connections", ["tenant_id"]
    )
    op.create_index(
        "uq_tenant_backup_connections_active",
        "tenant_backup_connections",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("disconnected_at IS NULL"),
    )
    _enable_tenant_rls("tenant_backup_connections")

    op.create_table(
        "tenant_backup_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("wrapped_key", sa.LargeBinary(), nullable=False),
        sa.Column("kek_id", sa.String(80), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("retired_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_tenant_backup_keys_tenant_id", "tenant_backup_keys", ["tenant_id"])
    _enable_tenant_rls("tenant_backup_keys")

    op.create_table(
        "tenant_backups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("key_id", postgresql.UUID(as_uuid=True)),
        sa.Column("file_name", sa.String(200)),
        sa.Column("remote_file_id", sa.String(200)),
        sa.Column("byte_size", sa.BigInteger()),
        sa.Column("checksum", sa.String(64)),
        sa.Column("manifest", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("error", sa.String(400)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["key_id"], ["tenant_backup_keys.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint("kind IN ('DAILY', 'MONTHLY', 'MANUAL')", name="ck_backups_kind"),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'UPLOADED', 'FAILED', 'DELETED')", name="ck_backups_status"
        ),
    )
    op.create_index(
        "ix_tenant_backups_tenant_created", "tenant_backups", ["tenant_id", "created_at"]
    )
    _enable_tenant_rls("tenant_backups")

    op.create_table(
        "tenant_backup_restores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("backup_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("report", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["backup_id"], ["tenant_backups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint("mode IN ('VERIFY', 'IMPORT')", name="ck_backup_restores_mode"),
        sa.CheckConstraint(
            "status IN ('VERIFIED', 'IMPORTED', 'FAILED')", name="ck_backup_restores_status"
        ),
    )
    op.create_index("ix_tenant_backup_restores_tenant_id", "tenant_backup_restores", ["tenant_id"])
    _enable_tenant_rls("tenant_backup_restores")


def downgrade() -> None:
    op.drop_table("tenant_backup_restores")
    op.drop_table("tenant_backups")
    op.drop_table("tenant_backup_keys")
    op.drop_table("tenant_backup_connections")
