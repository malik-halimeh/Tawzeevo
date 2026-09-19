"""Customer location provenance for D-061 precedence.

Revision ID: 20260919_0026
Revises: 20260919_0025
Create Date: 2026-09-19

Phase 7 P7-M3 (PHASE_07.md E; D-061). A customer location now carries where it came from
(`gps | manual | geocoded`), when it was captured, its accuracy in metres and whether an operator
confirmed it. A confirmed location is never replaced automatically and a worse reading never
silently replaces a better one; the precedence lives in the service. No GPS history is kept —
only the current best reading per customer.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260919_0026"
down_revision: str | None = "20260919_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("location_source", sa.String(10)))
    op.add_column("customers", sa.Column("location_captured_at", sa.DateTime(timezone=True)))
    op.add_column("customers", sa.Column("location_accuracy_meters", sa.Numeric(10, 2)))
    op.add_column("customers", sa.Column("location_confirmed_at", sa.DateTime(timezone=True)))
    op.add_column(
        "customers", sa.Column("location_confirmed_by_membership_id", postgresql.UUID(as_uuid=True))
    )
    op.create_foreign_key(
        "fk_customers_location_confirmed_by",
        "customers",
        "tenant_memberships",
        ["location_confirmed_by_membership_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_customers_location_source",
        "customers",
        "location_source IS NULL OR location_source IN ('gps', 'manual', 'geocoded')",
    )
    op.create_check_constraint(
        "ck_customers_location_accuracy_nonneg",
        "customers",
        "location_accuracy_meters IS NULL OR location_accuracy_meters >= 0",
    )
    # Existing coordinates were typed by the owner: they are manual, unconfirmed readings.
    op.execute(
        "UPDATE customers SET location_source = 'manual' "
        "WHERE latitude IS NOT NULL AND location_source IS NULL"
    )


def downgrade() -> None:
    op.drop_constraint("ck_customers_location_accuracy_nonneg", "customers", type_="check")
    op.drop_constraint("ck_customers_location_source", "customers", type_="check")
    op.drop_constraint("fk_customers_location_confirmed_by", "customers", type_="foreignkey")
    for column in (
        "location_confirmed_by_membership_id",
        "location_confirmed_at",
        "location_accuracy_meters",
        "location_captured_at",
        "location_source",
    ):
        op.drop_column("customers", column)
