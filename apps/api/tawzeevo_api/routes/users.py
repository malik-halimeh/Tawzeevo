from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from tawzeevo_api.database import get_db
from tawzeevo_api.dependencies import get_current_user, require_system_admin
from tawzeevo_api.models import SystemUserType, User
from tawzeevo_api.schemas.auth import UserResponse
from tawzeevo_api.schemas.users import (
    AdminCreateUserRequest,
    AdminUpdateUserRequest,
    AverageAgeResponse,
    CityCountResponse,
    ProfileUpdateRequest,
    UserCountResponse,
    UserListResponse,
)
from tawzeevo_api.services.users import (
    average_user_age,
    create_user,
    get_user_for_update,
    list_users,
    soft_delete_user,
    top_user_cities,
    update_user_profile,
    user_count,
)

users_router = APIRouter(tags=["users"])
stats_router = APIRouter(prefix="/stats", tags=["public statistics"])


@users_router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def admin_create_user(
    request: AdminCreateUserRequest,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(require_system_admin)],
) -> UserResponse:
    return UserResponse.model_validate(create_user(db, request))


@users_router.get("/users/me", response_model=UserResponse)
def own_profile(user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return UserResponse.model_validate(user)


@users_router.put("/users/me", response_model=UserResponse)
def update_own_profile(
    request: ProfileUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    return UserResponse.model_validate(update_user_profile(db, user, request))


@users_router.get("/users", response_model=UserListResponse)
def admin_list_users(
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(require_system_admin)],
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    age: Annotated[int | None, Query(ge=1, le=120)] = None,
    city: str | None = None,
    system_type: Annotated[SystemUserType | None, Query(alias="type")] = None,
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
    search: str | None = None,
) -> UserListResponse:
    users, total, total_pages = list_users(
        db,
        page=page,
        limit=limit,
        age=age,
        city=city,
        system_type=system_type,
        first_name=first_name,
        last_name=last_name,
        email=email,
        search=search,
    )
    return UserListResponse(
        page=page,
        limit=limit,
        total=total,
        total_pages=total_pages,
        users=[UserResponse.model_validate(user) for user in users],
    )


@users_router.put("/users/{user_id}", response_model=UserResponse)
def admin_update_user(
    user_id: UUID,
    request: AdminUpdateUserRequest,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(require_system_admin)],
) -> UserResponse:
    user = get_user_for_update(db, user_id)
    return UserResponse.model_validate(
        update_user_profile(db, user, request, allow_role_change=True)
    )


@users_router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_user(
    user_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(require_system_admin)],
) -> None:
    soft_delete_user(db, user_id)


@stats_router.get("/count", response_model=UserCountResponse)
def count_users(db: Annotated[Session, Depends(get_db)]) -> UserCountResponse:
    return UserCountResponse(count=user_count(db))


@stats_router.get("/average-age", response_model=AverageAgeResponse)
def average_age(db: Annotated[Session, Depends(get_db)]) -> AverageAgeResponse:
    return AverageAgeResponse(average_age=average_user_age(db))


@stats_router.get("/top-cities", response_model=list[CityCountResponse])
def top_cities(db: Annotated[Session, Depends(get_db)]) -> list[CityCountResponse]:
    return [CityCountResponse.model_validate(row) for row in top_user_cities(db)]
