from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from tawzeevo_api.config import Settings, get_settings
from tawzeevo_api.database import get_db
from tawzeevo_api.dependencies import AuthContext, get_auth_context
from tawzeevo_api.errors import AppError, AuthenticationError
from tawzeevo_api.public_invoice_security import PublicInvoiceRateLimiter
from tawzeevo_api.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)
from tawzeevo_api.services.auth import login, logout, register_client, rotate_refresh_token
from tawzeevo_api.services.password_reset import request_reset, reset_password

root_router = APIRouter()
auth_router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])

# Brute-force and recovery abuse controls (PHASE_09.md B/C): per-process sliding windows keyed
# by client IP, counting failures only for login. Limits come from settings; the limiters are
# created lazily so tests can override the settings before the first request.
_login_failures: PublicInvoiceRateLimiter | None = None
_reset_requests: PublicInvoiceRateLimiter | None = None


def _limiters(settings: Settings) -> tuple[PublicInvoiceRateLimiter, PublicInvoiceRateLimiter]:
    global _login_failures, _reset_requests
    if _login_failures is None or _reset_requests is None:
        _login_failures = PublicInvoiceRateLimiter(
            limit=settings.auth_failed_logins_per_15_minutes, window=900
        )
        _reset_requests = PublicInvoiceRateLimiter(
            limit=settings.auth_reset_requests_per_15_minutes, window=900
        )
    return _login_failures, _reset_requests


def reset_auth_limiters() -> None:
    """Test hook: forget every window (the limiters live for the process)."""
    global _login_failures, _reset_requests
    _login_failures = _reset_requests = None


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _too_many() -> AppError:
    return AppError(429, "RATE_LIMITED", "Too many attempts; please try again later")


def set_refresh_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=settings.refresh_token_ttl_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
        path=settings.refresh_cookie_path,
    )


def clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
        path=settings.refresh_cookie_path,
    )


@root_router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["authentication"],
)
def register(request: RegisterRequest, db: Annotated[Session, Depends(get_db)]) -> UserResponse:
    return UserResponse.model_validate(register_client(db, request))


@root_router.post("/login", response_model=TokenResponse, tags=["authentication"])
def login_route(
    request: LoginRequest,
    http_request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    settings = get_settings()
    failures, _ = _limiters(settings)
    client = _client_ip(http_request)
    if not failures.allow(client):
        raise _too_many()
    tokens = login(db, request, settings)
    # A successful login gives the budget back: only failures accumulate.
    failures.forgive(client)
    set_refresh_cookie(response, tokens.refresh_token, settings)
    return TokenResponse(
        access_token=tokens.access_token,
        expires_in=settings.access_token_ttl_minutes * 60,
    )


def _require_allowed_origin(request: Request, settings: Settings) -> None:
    """CSRF guard for cookie-bearing auth routes when the cookie is SameSite=None: a browser
    always sends Origin on cross-site POSTs, and only the configured client origins may use the
    refresh cookie. Same-site and non-browser calls carry no Origin and pass unchanged."""
    origin = request.headers.get("origin")
    if origin and origin not in settings.cors_allowed_origins:
        raise AuthenticationError(
            "ORIGIN_NOT_ALLOWED", "Origin is not allowed", clear_refresh_cookie=True
        )


@auth_router.post("/refresh", response_model=TokenResponse)
def refresh(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    settings = get_settings()
    _require_allowed_origin(request, settings)
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if refresh_token is None:
        raise AuthenticationError(clear_refresh_cookie=True)
    try:
        tokens = rotate_refresh_token(db, refresh_token, settings)
    except AuthenticationError as exc:
        exc.clear_refresh_cookie = True
        raise
    set_refresh_cookie(response, tokens.refresh_token, settings)
    return TokenResponse(
        access_token=tokens.access_token,
        expires_in=settings.access_token_ttl_minutes * 60,
    )


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout_route(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> None:
    _require_allowed_origin(request, get_settings())
    logout(db, context.auth_session)
    clear_refresh_cookie(response, get_settings())


@auth_router.post(
    "/password/forgot",
    status_code=status.HTTP_202_ACCEPTED,
    description="Always 202: the answer never reveals whether the address is registered.",
)
def forgot_password(
    request: ForgotPasswordRequest,
    http_request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    settings = get_settings()
    _, resets = _limiters(settings)
    if not resets.allow(_client_ip(http_request)):
        raise _too_many()
    request_reset(db, str(request.email), settings)
    return {"status": "accepted"}


@auth_router.post("/password/reset", status_code=status.HTTP_204_NO_CONTENT)
def reset_password_route(
    request: ResetPasswordRequest,
    http_request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    settings = get_settings()
    _, resets = _limiters(settings)
    if not resets.allow(_client_ip(http_request)):
        raise _too_many()
    reset_password(db, request.token, request.password.get_secret_value())
    clear_refresh_cookie(response, settings)
