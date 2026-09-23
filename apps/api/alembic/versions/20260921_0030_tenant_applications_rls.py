"""Row-level security for tenant applications.

Revision ID: 20260921_0030
Revises: 20260920_0029
Create Date: 2026-09-21

Audit remediation (finding TWZ-F-028, rows TWZ-A-001/A-002). `tenant_applications` carried a
tenant link but no row-level security, so a non-bypass role scoped to one tenant could read and
write another business's application row. The table is platform-owned (submitted by a client
user, reviewed by the platform admin) with a tenant link written at approval, so the policies
follow that ownership rather than the generic tenant policy:

- the platform admin scope (`app.platform_admin`, bound by the admin dependency for the request
  transaction) may read and review every application;
- an applicant may insert a PENDING application for themselves and read their own rows
  (`app.current_user_id`, bound at authentication);
- a tenant scope may read the application that created it (`app.current_tenant_id`).

No other path exists: FORCE ROW LEVEL SECURITY makes the policies apply to the table owner too.

Found while proving the flow under a NOBYPASSRLS role: the platform audit insert
(`audit_events`, tenant_id NULL under `app.platform_audit`) returns `occurred_at`, and PostgreSQL
checks SELECT policies on RETURNING rows, for which no platform policy existed. A matching SELECT
policy is added so platform audit events can be written by an RLS-subject application role.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260921_0030"
down_revision: str | None = "20260920_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "tenant_applications"
PLATFORM_ADMIN = "current_setting('app.platform_admin', true) = 'true'"
APPLICANT = "applicant_user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid"
TENANT = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"

POLICIES = (
    f'CREATE POLICY "{TABLE}_platform_admin" ON "{TABLE}" '
    f"USING ({PLATFORM_ADMIN}) WITH CHECK ({PLATFORM_ADMIN})",
    f'CREATE POLICY "{TABLE}_applicant_select" ON "{TABLE}" FOR SELECT USING ({APPLICANT})',
    f'CREATE POLICY "{TABLE}_applicant_insert" ON "{TABLE}" FOR INSERT '
    f"WITH CHECK ({APPLICANT} AND tenant_id IS NULL AND status = 'PENDING')",
    f'CREATE POLICY "{TABLE}_tenant_select" ON "{TABLE}" FOR SELECT USING ({TENANT})',
)


PLATFORM_AUDIT = "tenant_id IS NULL AND current_setting('app.platform_audit', true) = 'true'"


def upgrade() -> None:
    op.execute(f'ALTER TABLE "{TABLE}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{TABLE}" FORCE ROW LEVEL SECURITY')
    for statement in POLICIES:
        op.execute(statement)
    op.execute(
        'CREATE POLICY "audit_events_platform_select" ON "audit_events" '
        f"FOR SELECT USING ({PLATFORM_AUDIT})"
    )


def downgrade() -> None:
    op.execute('DROP POLICY "audit_events_platform_select" ON "audit_events"')
    for name in ("platform_admin", "applicant_select", "applicant_insert", "tenant_select"):
        op.execute(f'DROP POLICY "{TABLE}_{name}" ON "{TABLE}"')
    op.execute(f'ALTER TABLE "{TABLE}" NO FORCE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{TABLE}" DISABLE ROW LEVEL SECURITY')
