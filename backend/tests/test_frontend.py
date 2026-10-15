from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<html>index</html>")
    (static / "assets" / "app.js").write_text("console.log('app')")
    (tmp_path / "secret.txt").write_text("outside")
    return TestClient(create_app(Settings(static_dir=static)))


def test_root_serves_index(client):
    """Section 8.1: the built frontend is served by FastAPI."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.text == "<html>index</html>"


def test_static_asset_is_served(client):
    """Section 8.1: built assets are served as static files."""
    response = client.get("/assets/app.js")
    assert response.status_code == 200
    assert "console.log" in response.text


def test_unknown_path_falls_back_to_index(client):
    """Section 8.1: client-side routes fall back to index.html."""
    response = client.get("/configurations/123")
    assert response.status_code == 200
    assert response.text == "<html>index</html>"


def test_unknown_api_path_returns_404(client):
    """Section 8.1: unknown API paths are not swallowed by the frontend fallback."""
    assert client.get("/api/does-not-exist").status_code == 404


def test_health_routes_take_precedence(client):
    """NFR-004: health endpoints work with the frontend mounted."""
    assert client.get("/healthz").json() == {"status": "ok"}


def test_path_traversal_does_not_escape_static_dir(client):
    """Section 8.1: files outside the static directory are never served."""
    response = client.get("/..%2Fsecret.txt")
    assert "outside" not in response.text


def test_swagger_ui_uses_local_assets(tmp_path: Path):
    """NFR-010, NFR-012: /docs works without loading assets from external CDNs."""
    static = tmp_path / "static"
    (static / "swagger").mkdir(parents=True)
    (static / "index.html").write_text("<html>index</html>")
    (static / "swagger" / "swagger-ui-bundle.js").write_text("// bundle")
    client = TestClient(create_app(Settings(static_dir=static)))
    html = client.get("/docs").text
    assert "/swagger/swagger-ui-bundle.js" in html
    assert "/swagger/swagger-ui.css" in html
    assert "http://" not in html and "https://" not in html
    assert "cdn.jsdelivr" not in client.get("/redoc").text


def test_frontend_build_references_no_external_assets():
    """NFR-012: the built frontend loads no scripts, styles or fonts from other hosts."""
    dist = Path(__file__).parents[2] / "frontend" / "dist"
    if not (dist / "index.html").is_file():
        pytest.skip("frontend not built")
    html = (dist / "index.html").read_text()
    assert "http://" not in html and "https://" not in html
    for css in (dist / "assets").glob("*.css"):
        assert "url(http" not in css.read_text().replace(" ", ""), css.name
