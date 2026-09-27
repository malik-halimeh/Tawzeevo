"""A request waiting on a slow outside service must not keep a pooled database connection."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from tawzeevo_api.database import SessionLocal, engine
from tawzeevo_api.models import User
from tawzeevo_api.repositories.tenancy import released_for_outside_call, set_tenant_scope


def test_outside_call_hands_the_connection_back_and_restores_the_tenant_scope():
    tenant_id = uuid4()
    with SessionLocal() as db:
        set_tenant_scope(db, tenant_id)
        held = engine.pool.checkedout()
        assert held >= 1
        with released_for_outside_call(db, tenant_id):
            assert engine.pool.checkedout() == held - 1  # free for other requests meanwhile
        scope = db.scalar(text("SELECT current_setting('app.current_tenant_id', true)"))
        assert scope == str(tenant_id)


def test_outside_call_without_a_tenant_leaves_no_scope_behind():
    with SessionLocal() as db:
        set_tenant_scope(db, uuid4())
        with released_for_outside_call(db):
            pass
        assert not db.scalar(text("SELECT current_setting('app.current_tenant_id', true)"))


def test_outside_call_refuses_to_commit_pending_changes_early():
    with SessionLocal() as db:
        db.add(User(email=f"{uuid4()}@example.com", first_name="A", last_name="B"))
        with pytest.raises(RuntimeError), released_for_outside_call(db):
            pass
        db.rollback()
