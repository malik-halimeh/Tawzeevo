"""Tenant storefront slugs with audited rename redirects and an Arabic product name override.

Revision ID: 20260918_0017
Revises: 20260918_0016
Create Date: 2026-09-18

Phase 5 (PHASE_05.md A/B/N; D-047). The slug is routing identity only, never authorization.
Existing tenants receive a slug derived from their name (suffixed on collision) so every approved
business has a storefront address immediately. Redirect rows are tenant-owned (RLS) and looked
up publicly through a scoped query.
"""

import re
import unicodedata
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260918_0017"
down_revision: str | None = "20260918_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_EXPRESSION = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
RESERVED = {
    "api",
    "admin",
    "app",
    "apps",
    "assets",
    "backup",
    "docs",
    "health",
    "login",
    "logout",
    "platform",
    "profile",
    "public",
    "register",
    "static",
    "stats",
    "storefront",
    "tawzeevo",
    "workspace",
    "www",
}


def _slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    if len(slug) < 3:
        slug = f"shop-{slug}".strip("-")
    return slug[:50].rstrip("-") or "shop"


def upgrade() -> None:
    op.add_column("tenants", sa.Column("slug", sa.String(50), nullable=True))
    op.add_column("tenant_products", sa.Column("name_ar", sa.String(200), nullable=True))

    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, name FROM tenants ORDER BY created_at, id")).all()
    taken: set[str] = set()
    for tenant_id, name in rows:
        base = _slugify(str(name))
        candidate = base if base not in RESERVED else f"{base}-shop"
        suffix = 2
        while candidate in taken:
            tail = f"-{suffix}"
            candidate = f"{base[: 50 - len(tail)]}{tail}"
            suffix += 1
        taken.add(candidate)
        connection.execute(
            sa.text("UPDATE tenants SET slug = :slug WHERE id = :id"),
            {"slug": candidate, "id": tenant_id},
        )
    op.alter_column("tenants", "slug", nullable=False)
    op.create_index("uq_tenants_slug", "tenants", ["slug"], unique=True)
    op.create_check_constraint(
        "ck_tenants_slug_format", "tenants", "slug ~ '^[a-z0-9](?:[a-z0-9-]{1,48}[a-z0-9])?$'"
    )

    op.create_table(
        "tenant_slug_redirects",
        sa.Column("slug", sa.String(50), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("renamed_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["renamed_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_tenant_slug_redirects_tenant_id", "tenant_slug_redirects", ["tenant_id"])
    op.execute('ALTER TABLE "tenant_slug_redirects" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "tenant_slug_redirects" FORCE ROW LEVEL SECURITY')
    op.execute(
        'CREATE POLICY "tenant_slug_redirects_tenant_isolation" ON "tenant_slug_redirects" '
        f"USING ({TENANT_EXPRESSION}) WITH CHECK ({TENANT_EXPRESSION})"
    )
    # Public slug resolution reads redirects without a tenant scope: a read-only policy keyed by
    # the slug itself (the slug is public routing identity, never a secret).
    op.execute(
        'CREATE POLICY "tenant_slug_redirects_public_lookup" ON "tenant_slug_redirects" '
        "FOR SELECT USING (slug = NULLIF(current_setting('app.public_slug', true), ''))"
    )


def downgrade() -> None:
    op.drop_table("tenant_slug_redirects")
    op.drop_constraint("ck_tenants_slug_format", "tenants", type_="check")
    op.drop_index("uq_tenants_slug", table_name="tenants")
    op.drop_column("tenants", "slug")
    op.drop_column("tenant_products", "name_ar")
