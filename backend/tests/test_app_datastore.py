"""Wiring of the datastore into the application lifecycle."""

import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.repository.tinydb_repository import TinyDBRepository
from app.settings import Settings


def test_readyz_includes_datastore(tmp_path: Path):
    """DS-006: /readyz reports the datastore check."""
    app = create_app(Settings(tinydb_path=tmp_path / "db.json"))
    with TestClient(app) as client:
        response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["checks"] == {"datastore": "ok"}


def test_readyz_fails_when_datastore_unavailable():
    """DS-006: an unreachable datastore makes /readyz return 503; the app still starts."""
    settings = Settings(
        datastore_backend="couchdb",
        couchdb_url="http://127.0.0.1:1",
        couchdb_user="admin",
        couchdb_password="pw",
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/healthz").status_code == 200
        response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["checks"] == {"datastore": "failed"}


def test_startup_fails_on_unusable_tinydb_path(tmp_path: Path):
    """DS-004: an unusable TINYDB_PATH prevents the app from starting."""
    blocker = tmp_path / "file"
    blocker.write_text("not a directory")
    app = create_app(Settings(tinydb_path=blocker / "db.json"))
    with pytest.raises(OSError), TestClient(app):
        pass


def test_tinydb_startup_warning(tmp_path: Path, caplog):
    """R-02: a warning is logged at startup when TinyDB is active."""
    caplog.set_level(logging.WARNING)
    with TestClient(create_app(Settings(tinydb_path=tmp_path / "db.json"))):
        pass
    assert "R-02" in caplog.text


def test_repository_is_available_to_the_app(tmp_path: Path):
    """DS-001: the app holds exactly one repository behind the common interface."""
    app = create_app(Settings(tinydb_path=tmp_path / "db.json"))
    with TestClient(app):
        assert isinstance(app.state.repository, TinyDBRepository)
