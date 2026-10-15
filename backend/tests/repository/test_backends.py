"""Backend-specific behavior that is outside the shared contract."""

import logging
import uuid
from pathlib import Path

import httpx2
import pytest

from app.repository import DatastoreUnavailableError, create_repository
from app.repository.couchdb_repository import CouchDBRepository
from app.repository.tinydb_repository import TinyDBRepository
from app.settings import Settings

pytestmark = pytest.mark.anyio


async def test_tinydb_persists_across_instances(tmp_path: Path):
    """Section 8.3: TinyDB data survives a restart (same file)."""
    path = tmp_path / "db.json"
    first = TinyDBRepository(path)
    created = await first.create({"name": "persisted"})
    await first.close()

    second = TinyDBRepository(path)
    assert await second.get(created.id) == created
    await second.close()


async def test_tinydb_creates_missing_directories(tmp_path: Path):
    """Section 8.3: TINYDB_PATH may point into a directory that does not exist yet."""
    repo = TinyDBRepository(tmp_path / "nested" / "dir" / "db.json")
    await repo.check()
    assert (tmp_path / "nested" / "dir" / "db.json").is_file()
    await repo.close()


def test_tinydb_unusable_path_fails_immediately(tmp_path: Path):
    """DS-004: a TINYDB_PATH that cannot be created fails at startup."""
    blocker = tmp_path / "file"
    blocker.write_text("not a directory")
    with pytest.raises(OSError):
        TinyDBRepository(blocker / "db.json")


async def test_couchdb_creates_missing_database(couchdb_server):
    """DS-005: a missing CouchDB database is created by the startup/readiness check."""
    database = f"test_{uuid.uuid4().hex}"
    auth = (couchdb_server.user, couchdb_server.password)
    db_url = f"{couchdb_server.url}/{database}"
    assert httpx2.get(db_url, auth=auth).status_code == 404

    repo = CouchDBRepository(
        couchdb_server.url, couchdb_server.user, couchdb_server.password, database
    )
    await repo.check()
    await repo.check()  # idempotent
    assert httpx2.get(db_url, auth=auth).status_code == 200
    await repo.close()
    httpx2.delete(db_url, auth=auth)


async def test_couchdb_wrong_credentials_fail_check(couchdb_server):
    """DS-006: wrong credentials make the readiness check fail."""
    repo = CouchDBRepository(couchdb_server.url, couchdb_server.user, "wrong", "cloudinit")
    with pytest.raises(DatastoreUnavailableError):
        await repo.check()
    await repo.close()


async def test_couchdb_unreachable_fails_check_without_leaking_secrets(caplog):
    """DS-006, NFR-007: an unreachable server fails the check; the password is not exposed."""
    caplog.set_level(logging.DEBUG)
    repo = CouchDBRepository("http://127.0.0.1:1", "admin", "s3cret-pw", "cloudinit", timeout=1)
    with pytest.raises(DatastoreUnavailableError) as excinfo:
        await repo.check()
    await repo.close()
    assert "s3cret-pw" not in str(excinfo.value)
    assert "s3cret-pw" not in caplog.text


def test_factory_selects_tinydb_by_default(tmp_path: Path, monkeypatch):
    """Section 8.3: DATASTORE_BACKEND defaults to tinydb."""
    monkeypatch.delenv("DATASTORE_BACKEND", raising=False)
    repo = create_repository(Settings(tinydb_path=tmp_path / "db.json"))
    assert isinstance(repo, TinyDBRepository)


def test_factory_selects_couchdb():
    """Section 8.3: DATASTORE_BACKEND=couchdb selects the CouchDB backend."""
    settings = Settings(
        datastore_backend="couchdb",
        couchdb_url="http://couchdb:5984",
        couchdb_user="admin",
        couchdb_password="pw",
    )
    assert isinstance(create_repository(settings), CouchDBRepository)
