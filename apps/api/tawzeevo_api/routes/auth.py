from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from tawzeevo_api.config import Settings, get_settings
from tawzeevo_api.database import get_db
from tawzeevo_api.dependencies import AuthContext, get_auth_context
from tawzeevo_api.errors import AuthenticationError
from tawzeevo_api.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from tawzeevo_api.services.auth import login, logout, register_client, rotate_refresh_token

root_router = APIRouter()
auth_router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


def set_refresh_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=settings.refresh_token_ttl_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite="lax",
        path=settings.refresh_cookie_path,
    )


def clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite="lax",
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
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    settings = get_settings()
    tokens = login(db, request, settings)
    set_refresh_cookie(response, tokens.refresh_token, settings)
    return TokenResponse(
        access_token=tokens.access_token,
        expires_in=settings.access_token_ttl_minutes * 60,
    )


@auth_router.post("/refresh", response_model=TokenResponse)
def refresh(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    settings = get_settings()
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
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> None:
    logout(db, context.auth_session)
    clear_refresh_cookie(response, get_settings())
