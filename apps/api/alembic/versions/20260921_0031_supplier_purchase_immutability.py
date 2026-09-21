"""Supplier purchases immutable at the database.

Revision ID: 20260921_0031
Revises: 20260921_0030
Create Date: 2026-09-21

Audit remediation (finding TWZ-F-021). Supplier purchase headers and lines are financial history
(PHASE_06.md P6-M4) but, unlike the other financial tables, were immutable in application code
only. Purchase lines now reject every UPDATE/DELETE through the existing financial-mutation
trigger function. Purchase headers reject DELETE and every UPDATE except the one reversal
transition the service performs: `reversed_at`/`reversal_reason`/`reversal_idempotency_key` may
be written once, from NULL, with every other column unchanged; a reversed header is frozen.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260921_0031"
down_revision: str | None = "20260921_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REVERSAL_COLUMNS = "'reversed_at' - 'reversal_reason' - 'reversal_idempotency_key'"


def upgrade() -> None:
    op.execute(
        'CREATE TRIGGER "supplier_purchase_items_immutable" '
        'BEFORE UPDATE OR DELETE ON "supplier_purchase_items" '
        "FOR EACH ROW EXECUTE FUNCTION tawzeevo_reject_financial_mutation()"
    )
    op.execute(
        "CREATE FUNCTION tawzeevo_reject_purchase_mutation() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN "
        "IF TG_OP = 'DELETE' THEN "
        "  RAISE EXCEPTION 'immutable financial row: %', TG_TABLE_NAME USING ERRCODE = '55000'; "
        "END IF; "
        "IF OLD.reversed_at IS NOT NULL THEN "
        "  RAISE EXCEPTION 'immutable financial row: % (already reversed)', TG_TABLE_NAME "
        "  USING ERRCODE = '55000'; "
        "END IF; "
        "IF NEW.reversed_at IS NULL OR NEW.reversal_idempotency_key IS NULL THEN "
        "  RAISE EXCEPTION 'immutable financial row: % (only a reversal may update)', "
        "  TG_TABLE_NAME USING ERRCODE = '55000'; "
        "END IF; "
        f"IF (to_jsonb(OLD) - {REVERSAL_COLUMNS}) IS DISTINCT FROM "
        f"   (to_jsonb(NEW) - {REVERSAL_COLUMNS}) THEN "
        "  RAISE EXCEPTION 'immutable financial row: % (reversal may not alter the purchase)', "
        "  TG_TABLE_NAME USING ERRCODE = '55000'; "
        "END IF; "
        "RETURN NEW; END; $$"
    )
    op.execute(
        'CREATE TRIGGER "supplier_purchases_immutable" '
        'BEFORE UPDATE OR DELETE ON "supplier_purchases" '
        "FOR EACH ROW EXECUTE FUNCTION tawzeevo_reject_purchase_mutation()"
    )


def downgrade() -> None:
    op.execute('DROP TRIGGER IF EXISTS "supplier_purchases_immutable" ON "supplier_purchases"')
    op.execute("DROP FUNCTION IF EXISTS tawzeevo_reject_purchase_mutation()")
    op.execute(
        'DROP TRIGGER IF EXISTS "supplier_purchase_items_immutable" ON "supplier_purchase_items"'
    )
