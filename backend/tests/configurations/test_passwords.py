"""FR-010, NFR-007: plain-text passwords never leave the request that carries them."""

import logging
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.configurations.sections.users import CRYPT_RE, hash_password
from app.main import create_app
from app.settings import Settings

pytestmark = pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl not installed")

PLAIN = "Correct-Horse-Battery-Staple-42"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "db.json"


@pytest.fixture
def client(db_path: Path):
    with TestClient(create_app(Settings(tinydb_path=db_path))) as client:
        yield client


def body(**user) -> dict:
    return {"name": "pw", "users": {"users": [{"name": "alice", **user}]}}


def test_hash_password_produces_sha512_crypt():
    """FR-010: passwords are hashed as SHA-512-crypt with a random salt."""
    first, second = hash_password(PLAIN), hash_password(PLAIN)
    assert first.startswith("$6$")
    assert CRYPT_RE.fullmatch(first)
    assert first != second  # random salt


def test_plain_password_is_never_stored_returned_rendered_or_logged(client, db_path, caplog):
    """FR-010: neither datastore, YAML, API responses nor logs contain the plain-text password."""
    caplog.set_level(logging.DEBUG)
    created = client.post("/api/configurations", json=body(password=PLAIN, lock_passwd=False))
    assert created.status_code == 201
    config = created.json()
    user = config["users"]["users"][0]
    assert "password" not in user
    assert user["password_hash"].startswith("$6$")

    responses = [
        created,
        client.get(f"/api/configurations/{config['id']}"),
        client.get(f"/api/configurations/{config['id']}/files"),
        client.get(f"/api/configurations/{config['id']}/preview"),
        client.get("/api/configurations"),
        client.post("/api/preview", json=body(password=PLAIN)),
        client.post(f"/api/configurations/{config['id']}/duplicate"),
    ]
    for response in responses:
        assert PLAIN not in response.text, response.request.url
    assert PLAIN not in db_path.read_text()
    assert PLAIN not in caplog.text


def test_yaml_contains_the_hash_under_passwd(client):
    """FR-010: a plain-text password ends up as SHA-512-crypt hash under passwd."""
    config = client.post("/api/configurations", json=body(password=PLAIN)).json()
    user_data = client.get(f"/api/configurations/{config['id']}/files").json()["user-data"]
    stored_hash = config["users"]["users"][0]["password_hash"]
    assert f"passwd: {stored_hash}" in user_data


def test_plain_password_is_not_echoed_in_validation_errors(client):
    """FR-010: even an invalid request never returns the plain-text password."""
    response = client.post(
        "/api/configurations",
        json={"name": "", "users": {"users": [{"name": "Bad Name", "password": PLAIN}]}},
    )
    assert response.status_code == 422
    assert PLAIN not in response.text


def test_stored_hash_is_kept_when_saving_without_new_password(client):
    """FR-010: a stored password stays set when the configuration is saved again."""
    config = client.post("/api/configurations", json=body(password=PLAIN)).json()
    stored_hash = config["users"]["users"][0]["password_hash"]
    config["name"] = "renamed"
    updated = client.put(f"/api/configurations/{config['id']}", json=config).json()
    assert updated["users"]["users"][0]["password_hash"] == stored_hash


def test_password_can_be_replaced_and_removed(client):
    """FR-010: a stored password can be replaced or removed, but not read."""
    config = client.post("/api/configurations", json=body(password=PLAIN)).json()
    old_hash = config["users"]["users"][0]["password_hash"]

    config["users"]["users"][0]["password"] = "another-secret"
    replaced = client.put(f"/api/configurations/{config['id']}", json=config).json()
    new_hash = replaced["users"]["users"][0]["password_hash"]
    assert new_hash != old_hash and new_hash.startswith("$6$")

    replaced["users"]["users"][0]["password_hash"] = None
    removed = client.put(f"/api/configurations/{replaced['id']}", json=replaced).json()
    assert removed["users"]["users"][0]["password_hash"] is None
    files = client.get(f"/api/configurations/{replaced['id']}/files").json()
    assert "passwd" not in files["user-data"]


def test_duplicate_copies_password_hash_and_keys(client):
    """FR-015: duplicating copies password hashes and SSH keys."""
    key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl t"
    config = client.post(
        "/api/configurations", json=body(password=PLAIN, ssh_authorized_keys=[key])
    ).json()
    copy = client.post(f"/api/configurations/{config['id']}/duplicate").json()
    assert (
        copy["users"]["users"][0]["password_hash"] == config["users"]["users"][0]["password_hash"]
    )
    assert copy["users"]["users"][0]["ssh_authorized_keys"] == [key]
