from fastapi.testclient import TestClient

from app.health import register_readiness_check
from app.main import create_app
from app.settings import Settings


def make_client() -> tuple[TestClient, object]:
    app = create_app(Settings())
    return TestClient(app), app


def test_healthz_returns_ok():
    """NFR-004: liveness endpoint /healthz responds with HTTP 200."""
    client, _ = make_client()
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_without_checks_is_ready():
    """NFR-004: readiness endpoint /readyz responds with HTTP 200 when nothing is failing."""
    client, _ = make_client()
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {}}


def test_readyz_reports_passing_check():
    """NFR-004 / DS-006: a passing registered check keeps /readyz at HTTP 200."""
    client, app = make_client()

    async def ok() -> None:
        return None

    register_readiness_check(app, "datastore", ok)
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["checks"] == {"datastore": "ok"}


def test_readyz_returns_503_when_a_check_fails(caplog):
    """NFR-004 / DS-006: a failing check makes /readyz return HTTP 503 without leaking details."""
    client, app = make_client()

    async def ok() -> None:
        return None

    async def failing() -> None:
        raise ConnectionError("http://admin:s3cret@couchdb:5984 unreachable")

    register_readiness_check(app, "other", ok)
    register_readiness_check(app, "datastore", failing)
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "checks": {"other": "ok", "datastore": "failed"},
    }
    # NFR-007: the exception message (which may contain credentials) is never logged or returned.
    assert "s3cret" not in caplog.text
    assert "s3cret" not in response.text


def test_openapi_is_available():
    """NFR-010: the REST API is documented via OpenAPI."""
    client, _ = make_client()
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/healthz" in response.json()["paths"]
