import os

import pytest
from sqlalchemy import create_engine, text


@pytest.mark.integration
def test_postgresql_connection() -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for the PostgreSQL integration test")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1
            assert connection.dialect.name == "postgresql"
    finally:
        engine.dispose()
