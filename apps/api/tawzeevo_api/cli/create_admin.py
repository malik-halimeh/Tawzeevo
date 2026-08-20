from __future__ import annotations

import argparse
import getpass

from pydantic import SecretStr, ValidationError

from tawzeevo_api.database import SessionLocal
from tawzeevo_api.errors import AppError
from tawzeevo_api.models import SystemUserType
from tawzeevo_api.schemas.users import AdminCreateUserRequest
from tawzeevo_api.services.users import create_user


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description="Create a Tawzeevo system administrator without exposing a public route."
    )
    command.add_argument("--first-name", required=True)
    command.add_argument("--last-name", required=True)
    command.add_argument("--email", required=True)
    command.add_argument("--phone", required=True)
    command.add_argument("--city", required=True)
    command.add_argument("--age", required=True, type=int)
    return command


def main() -> int:
    arguments = parser().parse_args()
    password = getpass.getpass("Administrator password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        print("Passwords do not match.")
        return 2
    try:
        request = AdminCreateUserRequest(
            first_name=arguments.first_name,
            last_name=arguments.last_name,
            email=arguments.email,
            phone=arguments.phone,
            city=arguments.city,
            age=arguments.age,
            password=SecretStr(password),
            type=SystemUserType.ADMIN,
        )
        with SessionLocal() as db:
            user = create_user(db, request)
    except (ValidationError, AppError) as exc:
        print(f"Administrator was not created: {exc}")
        return 1
    print(f"Created administrator {user.email} ({user.id}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
