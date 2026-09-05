"""Keep the two narrowly grandfathered migration files immutable, not unchecked."""

from hashlib import sha256
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("filename", "expected_sha256"),
    [
        (
            "20260827_0009_invoice_item_line_order.py",
            "c1c8d1757639e21c77307987844e75e2c68721540c8843800eb04a8be2794d1c",
        ),
        (
            "20260827_0010_financial_confirmation_debt.py",
            "cf9bf734ebcc0f542f3e63096abf3d98879bff85b5d8d22d7654b30003916c8c",
        ),
    ],
    ids=["0009", "0010"],
)
def test_historical_migration_content_is_unchanged(filename: str, expected_sha256: str) -> None:
    migration = Path(__file__).resolve().parents[1] / "alembic" / "versions" / filename
    # Git can convert LF to CRLF at checkout. No other whitespace/content is normalized.
    canonical_bytes = migration.read_bytes().replace(b"\r\n", b"\n")
    assert sha256(canonical_bytes).hexdigest() == expected_sha256, (
        f"Historical migration {filename} changed. Restore its original contents; "
        "do not refresh the fingerprint to conceal an edit. Use a new migration for schema work."
    )
