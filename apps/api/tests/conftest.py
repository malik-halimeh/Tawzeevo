import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from tawzeevo_api.database import get_db
from tawzeevo_api.main import app


@pytest.fixture(scope="session")
def test_engine() -> Generator[Engine]:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL-backed API tests")
    engine = create_engine(database_url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_database(test_engine: Engine) -> Generator[None]:
    with test_engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE auth_sessions, users CASCADE"))
    yield
    with test_engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE auth_sessions, users CASCADE"))


@pytest.fixture
def session_factory(test_engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Generator[TestClient]:
    def override_get_db() -> Generator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client
    app.dependency_overrides.clear()
