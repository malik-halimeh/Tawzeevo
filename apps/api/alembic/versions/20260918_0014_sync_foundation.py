"""Offline synchronization foundation: device registry, change log, idempotent operations.

Revision ID: 20260918_0014
Revises: 20260917_0013
Create Date: 2026-09-18

Phase 4 (PHASE_04.md C/E/F/N; D-052, D-053, D-054). Mutable conflict-sensitive rows gain a
monotonic version. Every row here is tenant-owned and protected by forced row-level security.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260918_0014"
down_revision: str | None = "20260917_0013"
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
    for table in ("customers", "categories", "tenant_products"):
        op.add_column(
            table,
            sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        )

    op.create_table(
        "sync_devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_installation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("protocol_version", sa.Integer(), nullable=False),
        sa.Column("app_schema_version", sa.Integer(), nullable=False),
        sa.Column(
            "last_acknowledged_change_seq",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_reason", sa.String(length=80)),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["membership_id"],
            ["tenant_memberships.id"],
            name="fk_sync_devices_membership",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_sync_devices_id_tenant"),
    )
    op.create_index("ix_sync_devices_tenant_id", "sync_devices", ["tenant_id"])
    op.create_index(
        "uq_sync_devices_active_installation",
        "sync_devices",
        ["tenant_id", "user_id", "device_installation_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    _enable_tenant_rls("sync_devices")

    op.create_table(
        "sync_changes",
        sa.Column("change_seq", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=60), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation", sa.String(length=10), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True)),
        sa.Column("device_installation_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("operation IN ('upsert', 'delete')", name="ck_sync_changes_operation"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_sync_changes_tenant_seq", "sync_changes", ["tenant_id", "change_seq"])
    op.create_index(
        "ix_sync_changes_tenant_entity", "sync_changes", ["tenant_id", "entity_type", "entity_id"]
    )
    _enable_tenant_rls("sync_changes")

    op.create_table(
        "sync_operations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_installation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=60), nullable=False),
        sa.Column("operation_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('applied', 'rejected', 'conflict')", name="ck_sync_operations_status"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "tenant_id",
            "device_installation_id",
            "operation_id",
            name="uq_sync_operations_command",
        ),
    )
    op.create_index("ix_sync_operations_tenant_id", "sync_operations", ["tenant_id"])
    _enable_tenant_rls("sync_operations")


def downgrade() -> None:
    for table in ("sync_operations", "sync_changes", "sync_devices"):
        op.execute(f'DROP POLICY IF EXISTS "{table}_tenant_isolation" ON "{table}"')
    op.drop_index("ix_sync_operations_tenant_id", table_name="sync_operations")
    op.drop_table("sync_operations")
    op.drop_index("ix_sync_changes_tenant_entity", table_name="sync_changes")
    op.drop_index("ix_sync_changes_tenant_seq", table_name="sync_changes")
    op.drop_table("sync_changes")
    op.drop_index("uq_sync_devices_active_installation", table_name="sync_devices")
    op.drop_index("ix_sync_devices_tenant_id", table_name="sync_devices")
    op.drop_table("sync_devices")
    for table in ("tenant_products", "categories", "customers"):
        op.drop_column(table, "version")
