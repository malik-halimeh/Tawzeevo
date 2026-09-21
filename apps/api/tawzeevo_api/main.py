import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from tawzeevo_api import metrics
from tawzeevo_api.config import get_settings
from tawzeevo_api.database import SessionLocal, get_db
from tawzeevo_api.db_role import check_database_role, inspect_database_role
from tawzeevo_api.errors import AppError, AuthenticationError
from tawzeevo_api.observability import RequestContextMiddleware, configure_logging
from tawzeevo_api.public_invoice_security import (
    PublicInvoicePrivacyMiddleware,
    install_capability_log_redaction,
)
from tawzeevo_api.routes.analytics import analytics_router
from tawzeevo_api.routes.auth import auth_router, root_router
from tawzeevo_api.routes.backup import backup_router, platform_backup_router
from tawzeevo_api.routes.branding import branding_router
from tawzeevo_api.routes.cash_van import cash_van_router, tenant_contexts_router
from tawzeevo_api.routes.customer_ledger import customer_ledger_router
from tawzeevo_api.routes.delivery import delivery_router, routes_router
from tawzeevo_api.routes.invoices import invoices_router
from tawzeevo_api.routes.payments import payments_router
from tawzeevo_api.routes.platform import platform_router, tenant_applications_router
from tawzeevo_api.routes.procurement import procurement_router
from tawzeevo_api.routes.public_invoices import capabilities_router, public_invoices_router
from tawzeevo_api.routes.storefront import storefront_owner_router, storefront_public_router
from tawzeevo_api.routes.supplier_ledger import supplier_ledger_router, supplier_payments_router
from tawzeevo_api.routes.supplier_purchases import outstanding_router, supplier_purchases_router
from tawzeevo_api.routes.suppliers import supplier_prices_router, suppliers_router
from tawzeevo_api.routes.sync import sync_router
from tawzeevo_api.routes.team import team_router
from tawzeevo_api.routes.users import stats_router, users_router
from tawzeevo_api.services.backup import run_due_backups
from tawzeevo_api.services.sync_changes import register_change_tracking

settings = get_settings()
install_capability_log_redaction()
logger = logging.getLogger("tawzeevo.backup")

BACKUP_TICK_SECONDS = 3600


def _backup_timer(stop: threading.Event) -> None:
    """In-process daily backup timer for the pilot; a hosting scheduler may call the CLI instead."""
    while not stop.wait(BACKUP_TICK_SECONDS):
        try:
            with SessionLocal() as db:
                run_due_backups(db)
        except Exception:  # noqa: BLE001 - the timer must survive one bad tick
            logger.exception("scheduled backup tick failed")


def database_role_preflight() -> None:
    """Report (and, when required, enforce) that the application role is subject to RLS."""
    try:
        with SessionLocal() as db:
            check_database_role(db, require_rls_subject=settings.db_role_require_rls_subject)
    except SQLAlchemyError:
        # An unreachable database is reported by /health/database; startup itself does not
        # depend on the preflight succeeding.
        logging.getLogger("tawzeevo.database").warning("database role preflight skipped")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    database_role_preflight()
    stop = threading.Event()
    worker: threading.Thread | None = None
    if settings.backup_scheduler_enabled:
        worker = threading.Thread(target=_backup_timer, args=(stop,), daemon=True)
        worker.start()
    try:
        yield
    finally:
        stop.set()
        if worker is not None:
            worker.join(timeout=5)


OPENAPI_TAGS = [
    {"name": "system", "description": "Service and PostgreSQL health checks."},
    {"name": "authentication", "description": "Registration, login, refresh, and logout."},
    {"name": "users", "description": "Authenticated profiles and administrator user management."},
    {
        "name": "public statistics",
        "description": "Aggregate, non-sensitive public user statistics.",
    },
    {"name": "tenant applications", "description": "Client business onboarding applications."},
    {
        "name": "platform administration",
        "description": "Application review and tenant lifecycle/access controls.",
    },
    {
        "name": "tenant operations",
        "description": "Owner-authorized, tenant-scoped Phase 1 Cash Van operations.",
    },
    {
        "name": "invoice editor",
        "description": (
            "Owner-only production invoice calculation, confirmation, and revision history."
        ),
    },
    {
        "name": "customer ledger",
        "description": "Owner-only customer balances, opening balances, and overdue debt.",
    },
    {
        "name": "payments",
        "description": (
            "Owner-only immutable customer receipts, allocations, reversals, and refunds."
        ),
    },
    {
        "name": "storefront",
        "description": (
            "Public per-business storefront catalog (published products only, public prices) "
            "and owner storefront settings."
        ),
    },
    {
        "name": "backup",
        "description": (
            "Owner-only encrypted Google Drive backup: connection, manifests, restore drills."
        ),
    },
]

configure_logging()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Tawzeevo platform API",
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(root_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(stats_router)
app.include_router(tenant_applications_router)
app.include_router(platform_router)
app.include_router(tenant_contexts_router)
app.include_router(cash_van_router)
app.include_router(invoices_router)
app.include_router(customer_ledger_router)
app.include_router(payments_router)
app.include_router(capabilities_router)
app.include_router(public_invoices_router)
app.include_router(supplier_ledger_router)
app.include_router(supplier_payments_router)
app.include_router(suppliers_router)
app.include_router(supplier_prices_router)
app.include_router(procurement_router)
app.include_router(supplier_purchases_router)
app.include_router(outstanding_router)
app.include_router(delivery_router)
app.include_router(routes_router)
app.include_router(team_router)
app.include_router(analytics_router)
app.include_router(branding_router)
app.include_router(sync_router)
app.include_router(backup_router)
app.include_router(platform_backup_router)
app.include_router(storefront_public_router)
app.include_router(storefront_owner_router)
register_change_tracking()
app.add_middleware(
    PublicInvoicePrivacyMiddleware,
    private_limit=get_settings().public_private_rate_limit_per_minute,
    catalog_limit=get_settings().public_catalog_rate_limit_per_minute,
)
# Outermost: every response carries X-Request-ID and one structured access-log line (P9-M3).
app.add_middleware(RequestContextMiddleware)


@app.exception_handler(AppError)
def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
    response = JSONResponse(
        status_code=exc.status_code,
        content={"detail": {"code": exc.code, "message": exc.message}},
        headers=headers,
    )
    if isinstance(exc, AuthenticationError) and exc.clear_refresh_cookie:
        response.delete_cookie(
            key=settings.refresh_cookie_name,
            httponly=True,
            secure=settings.refresh_cookie_secure,
            samesite=settings.refresh_cookie_samesite,
            path=settings.refresh_cookie_path,
        )
    return response


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "tawzeevo-api"}


@app.get("/health/metrics", tags=["system"])
def health_metrics() -> dict[str, object]:
    """Process counters for the external alert probe (P9-M3); no tenant or user content."""
    return metrics.snapshot()


@app.get("/health/database", tags=["system"])
def database_health(db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        head = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
        role = inspect_database_role(db)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "DATABASE_UNAVAILABLE", "message": "Database is unavailable"},
        ) from exc
    # The migration head lets a deploy check confirm the schema without reading logs (P9-M3);
    # the role flag lets the alert probe confirm RLS is not bypassed. No names, no secrets.
    return {
        "status": "ok",
        "database": "postgresql",
        "migration_head": head or "none",
        "database_role_rls_enforced": role.rls_enforced,
    }
