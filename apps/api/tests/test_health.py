from fastapi.testclient import TestClient

from tawzeevo_api.main import app


def test_health() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "tawzeevo-api"}


def test_openapi_uses_tawzeevo_brand() -> None:
    response = TestClient(app).get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Tawzeevo API"
