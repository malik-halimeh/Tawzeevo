from __future__ import annotations

import sys

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from tawzeevo_api.cli import create_admin
from tawzeevo_api.models import SystemUserType, User


def test_admin_bootstrap_uses_hidden_confirmed_password_and_creates_admin(
    monkeypatch: object,
    capsys: object,
    session_factory: sessionmaker[Session],
) -> None:
    monkeypatch.setattr(create_admin, "SessionLocal", session_factory)  # type: ignore[attr-defined]
    password_values = iter(["safe bootstrap password", "safe bootstrap password"])
    monkeypatch.setattr(create_admin.getpass, "getpass", lambda _prompt: next(password_values))  # type: ignore[attr-defined]
    monkeypatch.setattr(  # type: ignore[attr-defined]
        sys,
        "argv",
        [
            "create-admin",
            "--first-name",
            "Platform",
            "--last-name",
            "Owner",
            "--email",
            "owner@example.com",
            "--phone",
            "+96170123456",
            "--city",
            "Beirut",
            "--age",
            "30",
        ],
    )

    assert create_admin.main() == 0

    with session_factory() as db:
        user = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert user is not None
        assert user.type is SystemUserType.ADMIN
        assert user.password_hash.startswith("$argon2id$")
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "safe bootstrap password" not in output


def test_admin_bootstrap_rejects_password_confirmation_mismatch(
    monkeypatch: object, capsys: object
) -> None:
    password_values = iter(["safe bootstrap password", "different password"])
    monkeypatch.setattr(create_admin.getpass, "getpass", lambda _prompt: next(password_values))  # type: ignore[attr-defined]
    monkeypatch.setattr(sys, "argv", ["create-admin"])  # type: ignore[attr-defined]
    monkeypatch.setattr(create_admin, "parser", lambda: _NoArgumentParser())  # type: ignore[attr-defined]

    assert create_admin.main() == 2
    assert "Passwords do not match" in capsys.readouterr().out  # type: ignore[attr-defined]


class _NoArgumentParser:
    def parse_args(self) -> object:
        return object()
