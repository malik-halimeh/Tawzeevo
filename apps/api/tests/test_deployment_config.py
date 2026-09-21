"""Deployment blueprint checks (audit findings TWZ-F-007 / TWZ-F-010): render.yaml declares every
variable production refuses to start without, holds no secret value, and does not auto-deploy
the live services on push (live deploys are gated by deploy.yml after green CI)."""

from __future__ import annotations

import re
from pathlib import Path

RENDER_YAML = Path(__file__).resolve().parents[3] / "render.yaml"
DEPLOY_YML = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "deploy.yml"

# Variables validate_production_security refuses to start without (config.py), plus the two-site
# cookie attribute (D-088) and the trusted-proxy hop count the throttles depend on.
PRODUCTION_REQUIRED = {
    "APP_ENV",
    "DATABASE_URL",
    "JWT_SECRET",
    "REFRESH_COOKIE_SECURE",
    "REFRESH_COOKIE_SAMESITE",
    "CORS_ALLOWED_ORIGINS",
    "EMAIL_PROVIDER",
    "EMAIL_API_KEY",
    "PASSWORD_RESET_URL",
    "CUSTOMER_OTP_PROVIDER",
    "TRUSTED_PROXY_HOPS",
}
SECRETS = {
    "DATABASE_URL",
    "JWT_SECRET",
    "EMAIL_API_KEY",
    "BACKUP_MASTER_KEY",
    "GOOGLE_OAUTH_CLIENT_SECRET",
    "GOOGLE_OAUTH_CLIENT_ID",
}


def _api_service_block(text: str) -> str:
    start = text.index("name: tawzeevo-api-malik-halimeh")
    end = text.index("\n  - type: web", start)
    return text[start:end]


def _env_entries(block: str) -> dict[str, str]:
    """key -> the line that follows it (value/sync/generateValue), from the envVars list."""
    entries: dict[str, str] = {}
    for match in re.finditer(r"- key: ([A-Z0-9_]+)\n\s+(\S.*)", block):
        entries[match.group(1)] = match.group(2).strip()
    return entries


def test_render_blueprint_declares_production_required_settings_without_secret_values():
    text = RENDER_YAML.read_text(encoding="utf-8")
    entries = _env_entries(_api_service_block(text))
    missing = sorted(PRODUCTION_REQUIRED - set(entries))
    assert missing == [], f"render.yaml does not declare: {missing}"
    for key in SECRETS & set(entries):
        assert entries[key] in ("sync: false", "generateValue: true"), (key, entries[key])
    assert entries["APP_ENV"] == "value: production"
    assert entries["REFRESH_COOKIE_SAMESITE"] == "value: none"
    assert entries["CUSTOMER_OTP_PROVIDER"] == "sync: false"  # never the dev adapter in production
    assert "postgres://" not in text and "postgresql://" not in text


def test_live_services_do_not_auto_deploy_on_push_and_the_gate_compares_the_migration_head():
    text = RENDER_YAML.read_text(encoding="utf-8")
    assert "autoDeployTrigger: commit" not in text
    assert text.count("autoDeployTrigger: off") == 3
    deploy = DEPLOY_YML.read_text(encoding="utf-8")
    assert "scripts/migration_head.py" in deploy
    assert '"migration_head\\":\\"$EXPECTED_HEAD' in deploy
