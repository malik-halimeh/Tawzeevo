from decimal import Decimal
from functools import lru_cache
from typing import Literal

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
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=5, ge=0, le=50)
    db_pool_recycle_seconds: int = Field(default=1800, ge=60)
    db_pool_timeout_seconds: int = Field(default=10, ge=1)
    # Defense in depth only exists when the application role is subject to RLS (no SUPERUSER, no
    # BYPASSRLS). The API always reports the role's attributes; with this flag it refuses to start
    # otherwise. Off by default so an existing deployment is never taken down by a redeploy; the
    # owner turns it on after provisioning such a role (docs/runbooks/database-role.md).
    db_role_require_rls_subject: bool = False
    cors_allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    jwt_secret: str = "change-me"
    access_token_ttl_minutes: int = Field(default=15, ge=1)
    refresh_token_ttl_days: int = Field(default=30, ge=1)
    refresh_cookie_secure: bool = False
    refresh_cookie_name: str = "tawzeevo_refresh_token"
    refresh_cookie_path: str = "/api/v1/auth"
    # D-026 default. "none" only when the client and the API are served from different sites
    # (two onrender.com hosts): browsers drop a Lax cookie on cross-site fetches, so refresh
    # would never see it. With "none" the cookie-bearing auth routes check the Origin header.
    refresh_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    jwt_issuer: str = "tawzeevo-api"
    jwt_audience: str = "tawzeevo-operations"
    media_local_root: str = ".local-media"
    media_max_upload_bytes: int = Field(default=5 * 1024 * 1024, ge=1)
    media_max_dimension: int = Field(default=6000, ge=1)
    invoice_fuzzy_match_threshold: Decimal = Field(
        default=Decimal("0.7000"), ge=Decimal("0"), le=Decimal("1")
    )
    # Public rate limits are operational policy, not product invariants (D-076): per IP per
    # minute for private capability paths (customer-context, invoice links, orders) and for the
    # anonymous storefront catalog. Never the sole control (hash-only lookups, constant 404s).
    public_private_rate_limit_per_minute: int = Field(default=60, ge=1)
    public_catalog_rate_limit_per_minute: int = Field(default=600, ge=1)
    # How many trusted reverse-proxy hops sit in front of the API (0 = direct). The client IP for
    # the throttles below is the n-th address from the right of X-Forwarded-For; see client_ip.py.
    trusted_proxy_hops: int = Field(default=0, ge=0, le=8)
    # Login and recovery abuse controls (PHASE_09.md B/C): per client IP per 15 minutes.
    auth_failed_logins_per_15_minutes: int = Field(default=10, ge=1)
    auth_reset_requests_per_15_minutes: int = Field(default=10, ge=1)
    # Customer verification (D-073): provider selected at the Phase 9 gate ("dev" until then);
    # the numbers are operational policy (proposed defaults, owner to confirm), not invariants.
    customer_otp_provider: str = "dev"
    customer_otp_ttl_minutes: int = Field(default=5, ge=1, le=30)
    customer_otp_max_attempts: int = Field(default=5, ge=3, le=10)
    customer_otp_starts_per_hour: int = Field(default=5, ge=1, le=20)
    customer_verified_session_days: int = Field(default=7, ge=1, le=90)
    # Password recovery (D-077): link lifetime and where the operations client hosts the page.
    password_reset_ttl_minutes: int = Field(default=30, ge=5, le=120)
    password_reset_url: str = "http://localhost:5173/reset-password"
    # Transactional e-mail (D-077): brevo or resend with a key; memory only outside production.
    email_provider: str = "memory"
    email_api_key: str | None = None
    email_from: str = "Tawzeevo <no-reply@example.com>"
    # Online routing (D-060): OpenRouteService first when its key is set, Google only when its
    # key is set, otherwise the offline stop-order heuristic. Core delivery never depends on it.
    openrouteservice_api_key: str | None = None
    google_maps_api_key: str | None = None
    routing_timeout_seconds: float = Field(default=8.0, gt=0, le=60)
    # Encrypted Google backup (PHASE_04.md L; D-055..D-057). The master key wraps every
    # per-tenant data key and the Drive refresh tokens; it is a hosting secret, never committed.
    backup_master_key: str | None = None
    backup_kek_id: str = "kek-local-1"
    backup_drive_provider: str = "google"  # "memory" is the test double
    # The in-process job scheduler (D-079): backups, storefront view rollup (D-051) and delivery
    # reminders (D-049). Off in tests and local runs; the CLI jobs cover a hosting scheduler.
    backup_scheduler_enabled: bool = False
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    google_oauth_redirect_uri: str = "http://localhost:5173/backup/google/callback"
    # Business Copilot (D-089): Groq chat completions, off until the key is set in the hosting
    # dashboard. The key is a secret (never committed); the model name is operational policy.
    groq_api_key: str | None = None
    # A Groq model with tool use that accounts can call (llama-3.3-70b-versatile is refused for
    # some accounts); COPILOT_MODEL overrides it.
    copilot_model: str = "openai/gpt-oss-120b"
    copilot_timeout_seconds: float = Field(default=20.0, gt=0, le=60)
    copilot_requests_per_hour: int = Field(default=30, ge=1, le=500)
    copilot_max_tool_rounds: int = Field(default=4, ge=1, le=8)

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.app_env.lower() == "production":
            if self.jwt_secret == "change-me":
                raise ValueError("JWT_SECRET must be replaced in production")
            if len(self.jwt_secret.encode("utf-8")) < 32:
                raise ValueError("JWT_SECRET must contain at least 32 bytes in production")
            if not self.refresh_cookie_secure:
                raise ValueError("REFRESH_COOKIE_SECURE must be true in production")
            if self.refresh_cookie_samesite == "none" and not self.cors_allowed_origins:
                raise ValueError("REFRESH_COOKIE_SAMESITE=none needs CORS_ALLOWED_ORIGINS")
            if self.backup_drive_provider != "google":
                raise ValueError("BACKUP_DRIVE_PROVIDER must be google in production")
            if self.email_provider.lower() not in ("brevo", "resend") or not self.email_api_key:
                raise ValueError(
                    "EMAIL_PROVIDER (brevo|resend) and EMAIL_API_KEY are required in production"
                )
            if not self.password_reset_url.startswith("https://"):
                raise ValueError("PASSWORD_RESET_URL must be https in production")
            if self.customer_otp_provider.lower() == "dev":
                # The development adapter delivers nothing outside the process: a VERIFIED
                # customer could never complete verification. Fail closed (D-073 gate).
                raise ValueError(
                    "CUSTOMER_OTP_PROVIDER must name a production delivery provider; "
                    "the dev adapter is refused in production"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
