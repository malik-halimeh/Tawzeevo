"""Migration-head readiness (PHASE_09.md H, D-028): the schema the code expects versus the schema
the database has. Used by the startup preflight, `/health` (readiness) and `/health/database`
(live values); the deploy workflow compares the reported head with the repository head.

The expected head is read from the Alembic script directory next to `alembic.ini`, which the
service runs from (`rootDir: apps/api`). When no script directory can be found (an installed
package without the migrations tree) the expected head is unknown and readiness is not blocked.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("tawzeevo.database")


def _alembic_ini() -> Path | None:
    for candidate in (
        Path.cwd() / "alembic.ini",
        Path(__file__).resolve().parents[1] / "alembic.ini",
    ):
        if candidate.is_file():
            return candidate
    return None


def expected_migration_head() -> str | None:
    """The single head revision of the migration scripts shipped with this code, or None when the
    scripts are not available at runtime."""
    ini = _alembic_ini()
    if ini is None:
        return None
    heads = ScriptDirectory.from_config(Config(str(ini))).get_heads()
    if len(heads) != 1:
        raise RuntimeError(f"expected exactly one migration head, found {heads}")
    return heads[0]


def current_migration_head(db: Session) -> str | None:
    return db.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()


@dataclass(frozen=True)
class MigrationState:
    expected: str | None
    current: str | None

    @property
    def is_current(self) -> bool | None:
        """True/False when both sides are known; None when the expected head is unknown."""
        if self.expected is None:
            return None
        return self.expected == self.current


def migration_state(db: Session) -> MigrationState:
    return MigrationState(expected=expected_migration_head(), current=current_migration_head(db))


_ready_state: MigrationState | None = None


def record_startup_state(state: MigrationState | None) -> None:
    """Remember the startup preflight result for the cheap readiness answer of `/health`."""
    global _ready_state
    _ready_state = state
    if state is None or state.is_current is None:
        logger.info("migration readiness: expected head unknown at startup; not enforced")
    elif state.is_current:
        logger.info("migration readiness: database at expected head %s", state.expected)
    else:
        logger.error(
            "migration readiness: database at %s, code expects %s", state.current, state.expected
        )


def startup_state() -> MigrationState | None:
    return _ready_state


def migrations_ready() -> bool:
    """False only when the startup preflight positively found the database behind or ahead of
    the code; unknown (no scripts, database unreachable at startup) never blocks readiness."""
    return _ready_state is None or _ready_state.is_current is not False
