from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from tawzeevo_api.config import get_settings
from tawzeevo_api.database import get_db
from tawzeevo_api.errors import AppError, AuthenticationError
from tawzeevo_api.routes.auth import auth_router, root_router
from tawzeevo_api.routes.cash_van import cash_van_router
from tawzeevo_api.routes.platform import platform_router, tenant_applications_router
from tawzeevo_api.routes.users import stats_router, users_router

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Tawzeevo platform API",
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
app.include_router(cash_van_router)


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
            samesite="lax",
            path=settings.refresh_cookie_path,
        )
    return response


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "tawzeevo-api"}


@app.get("/health/database", tags=["system"])
def database_health(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "DATABASE_UNAVAILABLE", "message": "Database is unavailable"},
        ) from exc
    return {"status": "ok", "database": "postgresql"}
