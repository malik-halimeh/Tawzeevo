"""Database-role preflight: is the application role subject to row-level security?

Tenant isolation is enforced twice (00_PROJECT_CONTRACT: tenant-scoped services, then PostgreSQL
RLS as defense in depth). FORCE ROW LEVEL SECURITY is inert for a role that is SUPERUSER or has
BYPASSRLS, so the second layer only exists when the role the API connects with has neither
attribute. This module reports that fact (health endpoint, startup log) and, when the deployment
opts in, refuses to start with a role that bypasses RLS. It never changes roles or privileges.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("tawzeevo.database")


@dataclass(frozen=True)
class DatabaseRoleAttributes:
    name: str
    superuser: bool
    bypass_rls: bool

    @property
    def rls_enforced(self) -> bool:
        return not (self.superuser or self.bypass_rls)


def inspect_database_role(db: Session) -> DatabaseRoleAttributes:
    """Read the attributes of the role the current connection runs as (pg_roles is readable by
    every role; the query touches no tenant data)."""
    row = db.execute(
        text("SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
    ).one()
    return DatabaseRoleAttributes(name=str(row[0]), superuser=bool(row[1]), bypass_rls=bool(row[2]))


def check_database_role(db: Session, *, require_rls_subject: bool) -> DatabaseRoleAttributes:
    """Startup preflight. Logs the role's attributes; refuses to start only when the deployment
    requires an RLS-subject role (DB_ROLE_REQUIRE_RLS_SUBJECT=true) and the role bypasses RLS."""
    role = inspect_database_role(db)
    if role.rls_enforced:
        logger.info(
            "database role %s is subject to row-level security "
            "(rolsuper=false, rolbypassrls=false)",
            role.name,
        )
        return role
    message = (
        f"database role {role.name} bypasses row-level security "
        f"(rolsuper={str(role.superuser).lower()}, rolbypassrls={str(role.bypass_rls).lower()}); "
        "tenant isolation rests on application predicates only"
    )
    if require_rls_subject:
        raise RuntimeError(message + " and DB_ROLE_REQUIRE_RLS_SUBJECT is true")
    logger.warning(message)
    return role
