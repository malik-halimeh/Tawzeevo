from decimal import Decimal
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
    media_local_root: str = ".local-media"
    media_max_upload_bytes: int = Field(default=5 * 1024 * 1024, ge=1)
    media_max_dimension: int = Field(default=6000, ge=1)
    invoice_fuzzy_match_threshold: Decimal = Field(
        default=Decimal("0.7000"), ge=Decimal("0"), le=Decimal("1")
    )
    # Encrypted Google backup (PHASE_04.md L; D-055..D-057). The master key wraps every
    # per-tenant data key and the Drive refresh tokens; it is a hosting secret, never committed.
    backup_master_key: str | None = None
    backup_kek_id: str = "kek-local-1"
    backup_drive_provider: str = "google"  # "memory" is the test double
    backup_scheduler_enabled: bool = False
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    google_oauth_redirect_uri: str = "http://localhost:5173/backup/google/callback"

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.app_env.lower() == "production":
            if self.jwt_secret == "change-me":
                raise ValueError("JWT_SECRET must be replaced in production")
            if len(self.jwt_secret.encode("utf-8")) < 32:
                raise ValueError("JWT_SECRET must contain at least 32 bytes in production")
            if not self.refresh_cookie_secure:
                raise ValueError("REFRESH_COOKIE_SECURE must be true in production")
            if self.backup_drive_provider != "google":
                raise ValueError("BACKUP_DRIVE_PROVIDER must be google in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
