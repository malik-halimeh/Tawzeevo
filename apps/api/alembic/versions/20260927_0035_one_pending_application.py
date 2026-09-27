"""One pending tenant application per applicant.

Revision ID: 20260927_0035
Revises: 20260927_0034
Create Date: 2026-09-27

D-111. A partial unique index on applicant_user_id where status = 'PENDING'. If a database already
holds two pending applications from one person, the upgrade stops with a clear message instead of
changing any application: the administrator decides the older ones first.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927_0035"
down_revision: str | None = "20260927_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text("SELECT set_config('app.platform_admin', 'true', true)"))
    duplicates = connection.execute(
        sa.text(
            "SELECT count(*) FROM (SELECT applicant_user_id FROM tenant_applications "
            "WHERE status = 'PENDING' GROUP BY applicant_user_id HAVING count(*) > 1) AS d"
        )
    ).scalar_one()
    if duplicates:
        raise RuntimeError(
            f"{duplicates} applicant(s) have more than one PENDING application; approve or reject "
            "the extra ones first, then run this migration again (D-111)."
        )
    op.create_index(
        "uq_tenant_applications_one_pending",
        "tenant_applications",
        ["applicant_user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'PENDING'"),
    )


def downgrade() -> None:
    op.drop_index("uq_tenant_applications_one_pending", table_name="tenant_applications")
