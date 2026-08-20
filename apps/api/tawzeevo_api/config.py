from functools import lru_cache

from pydantic import Field
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
    refresh_cookie_secure: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
