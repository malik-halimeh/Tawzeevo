"""Migration-head readiness (audit finding TWZ-F-010): the code knows the head it expects, the
health endpoints report it, and `/health` refuses readiness when the startup preflight found the
database at another revision."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tawzeevo_api import migrations
from tawzeevo_api.migrations import MigrationState, expected_migration_head, migration_state

API_ROOT = Path(__file__).resolve().parents[1]


def test_expected_head_matches_alembic_heads_and_the_repository_script():
    expected = expected_migration_head()
    assert expected and expected == "20260921_0030"
    cli = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"], cwd=API_ROOT, capture_output=True, text=True
    )
    assert cli.returncode == 0, cli.stderr
    assert expected in cli.stdout
    # The dependency-free script the deploy workflow uses agrees with Alembic.
    script = subprocess.run(
        [sys.executable, str(API_ROOT / "scripts" / "migration_head.py")],
        capture_output=True,
        text=True,
    )
    assert script.returncode == 0, script.stderr
    assert script.stdout.strip() == expected


def test_database_health_reports_expected_and_current_heads(client, session_factory):
    with session_factory() as db:
        state = migration_state(db)
    assert state.is_current is True
    body = client.get("/health/database").json()
    assert body["migration_head"] == body["expected_migration_head"] == state.expected
    assert body["migration_current"] is True


def test_health_is_not_ready_when_startup_found_another_revision(client, monkeypatch):
    monkeypatch.setattr(
        migrations, "_ready_state", MigrationState("20260921_0030", "20260920_0029")
    )
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "MIGRATION_HEAD_MISMATCH"
    assert response.json()["detail"]["migration_head"] == "20260920_0029"
    # Unknown expected head (no scripts shipped) or an unreachable database never blocks.
    monkeypatch.setattr(migrations, "_ready_state", MigrationState(None, "20260920_0029"))
    assert client.get("/health").status_code == 200
    monkeypatch.setattr(migrations, "_ready_state", None)
    assert client.get("/health").status_code == 200
    monkeypatch.setattr(
        migrations, "_ready_state", MigrationState("20260921_0030", "20260921_0030")
    )
    assert client.get("/health").json() == {"status": "ok", "service": "tawzeevo-api"}
