from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Tawzeevo API"
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://tawzeevo:change-me@localhost:5432/tawzeevo"
    test_database_url: str | None = None
    cors_allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    jwt_secret: str = "change-me"
    access_token_ttl_minutes: int = Field(default=15, ge=1)
    refresh_token_ttl_days: int = Field(default=30, ge=1)
    refresh_cookie_secure: bool = False
    refresh_cookie_name: str = "tawzeevo_refresh_token"
    refresh_cookie_path: str = "/api/v1/auth"
    jwt_issuer: str = "tawzeevo-api"
    jwt_audience: str = "tawzeevo-operations"

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.app_env.lower() == "production":
            if self.jwt_secret == "change-me":
                raise ValueError("JWT_SECRET must be replaced in production")
            if len(self.jwt_secret.encode("utf-8")) < 32:
                raise ValueError("JWT_SECRET must contain at least 32 bytes in production")
            if not self.refresh_cookie_secure:
                raise ValueError("REFRESH_COOKIE_SECURE must be true in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
