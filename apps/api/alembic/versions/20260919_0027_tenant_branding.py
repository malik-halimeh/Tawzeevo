"""Tenant branding and presentation settings.

Revision ID: 20260919_0027
Revises: 20260919_0026
Create Date: 2026-09-19

Phase 8 P8-M3 (PHASE_08.md F/I). One optional branding row per business: identity/contact,
storefront theme tokens and texts, invoice header/footer/terms/thank-you, localization defaults,
and the logo as a processed image in object storage. Branding is presentation only: it never
touches roles, tenant scoping, pricing, ledgers, cancellation, stock or API authority. RLS.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260919_0027"
down_revision: str | None = "20260919_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_EXPRESSION = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "tenant_branding",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("description", sa.String(1000)),
        sa.Column("phone", sa.String(32)),
        sa.Column("whatsapp", sa.String(32)),
        sa.Column("email", sa.String(254)),
        sa.Column("address", sa.String(500)),
        sa.Column("primary_color", sa.String(7)),
        sa.Column("secondary_color", sa.String(7)),
        sa.Column("storefront_title", sa.String(120)),
        sa.Column("banner_text", sa.String(300)),
        sa.Column("social_links", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("about_text", sa.String(4000)),
        sa.Column("contact_text", sa.String(2000)),
        sa.Column("privacy_text", sa.String(8000)),
        sa.Column("terms_text", sa.String(8000)),
        sa.Column("invoice_header", sa.String(500)),
        sa.Column("invoice_footer", sa.String(500)),
        sa.Column("invoice_terms", sa.String(2000)),
        sa.Column("thank_you_text", sa.String(300)),
        sa.Column("invoice_qr_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("default_language", sa.String(2), nullable=False, server_default="en"),
        sa.Column("date_format", sa.String(12), nullable=False, server_default="DD/MM/YYYY"),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Asia/Beirut"),
        sa.Column("display_currency", sa.String(3)),
        sa.Column("logo_object_key", sa.String(500)),
        sa.Column("logo_content_type", sa.String(50)),
        sa.Column("logo_width", sa.Integer()),
        sa.Column("logo_height", sa.Integer()),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.CheckConstraint("default_language IN ('en', 'ar')", name="ck_tenant_branding_language"),
        sa.CheckConstraint(
            "primary_color IS NULL OR primary_color ~ '^#[0-9a-fA-F]{6}$'",
            name="ck_tenant_branding_primary_color",
        ),
        sa.CheckConstraint(
            "secondary_color IS NULL OR secondary_color ~ '^#[0-9a-fA-F]{6}$'",
            name="ck_tenant_branding_secondary_color",
        ),
        sa.CheckConstraint(
            "date_format IN ('DD/MM/YYYY', 'YYYY-MM-DD', 'MM/DD/YYYY')",
            name="ck_tenant_branding_date_format",
        ),
    )
    op.execute('ALTER TABLE "tenant_branding" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "tenant_branding" FORCE ROW LEVEL SECURITY')
    op.execute(
        'CREATE POLICY "tenant_branding_tenant_isolation" ON "tenant_branding" '
        f"USING ({TENANT_EXPRESSION}) WITH CHECK ({TENANT_EXPRESSION})"
    )


def downgrade() -> None:
    op.drop_table("tenant_branding")
