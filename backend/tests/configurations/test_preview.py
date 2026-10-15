from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app(Settings(tinydb_path=tmp_path / "db.json"))) as client:
        yield client


def test_preview_renders_unsaved_input(client):
    """FR-013: the preview endpoint renders the current form input without saving it."""
    body = {"name": "x", "basics": {"instance_id": "iid-1", "hostname": "web-01"}}
    response = client.post("/api/preview", json=body)
    assert response.status_code == 200
    files = response.json()["files"]
    assert yaml.safe_load(files["meta-data"]) == {
        "instance-id": "iid-1",
        "local-hostname": "web-01",
    }
    assert files["user-data"].startswith("#cloud-config\n")
    assert client.get("/api/configurations").json() == []


def test_preview_equals_saved_files(client):
    """FR-013: the preview shows exactly what saving and downloading produce."""
    body = {
        "name": "x",
        "basics": {"instance_id": "iid-1", "hostname": "web-01", "timezone": "UTC"},
    }
    preview = client.post("/api/preview", json=body).json()["files"]
    created = client.post("/api/configurations", json=body).json()
    assert client.get(f"/api/configurations/{created['id']}/files").json() == preview
    assert client.get(f"/api/configurations/{created['id']}/preview").json()["files"] == preview


def test_preview_suggests_instance_id(client):
    """FR-005: without an instance-id, the preview contains a suggested one."""
    body = {"name": "x", "basics": {"hostname": "web-01"}}
    meta = yaml.safe_load(client.post("/api/preview", json=body).json()["files"]["meta-data"])
    assert meta["instance-id"].startswith("iid-web-01-")


def test_preview_returns_field_errors(client):
    """FR-013, FR-004: invalid input yields field-level errors with readable messages."""
    response = client.post("/api/preview", json={"name": "x", "basics": {"hostname": "web_01"}})
    assert response.status_code == 422
    [error] = response.json()["detail"]
    assert error["loc"] == ["body", "basics", "hostname"]
    assert error["msg"].startswith("must be a host name")


def test_validation_errors_never_echo_input(client):
    """NFR-007: submitted values (possibly secrets) are not part of error responses."""
    body = {"name": "x", "basics": {"hostname": "s3cret value"}}
    response = client.post("/api/configurations", json=body)
    assert response.status_code == 422
    assert "s3cret" not in response.text
    assert set(response.json()["detail"][0]) == {"loc", "msg", "type"}


SSH_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl test"
WITH_KEY = {"ssh": {"authorized_keys": [SSH_KEY]}}


def test_warning_for_fqdn_not_matching_hostname(client):
    """FR-005: an FQDN that does not start with the hostname is a warning, not an error."""
    body = {"name": "x", "basics": {"hostname": "web-01", "fqdn": "db-01.example.com"}, **WITH_KEY}
    response = client.post("/api/preview", json=body)
    assert response.status_code == 200
    assert response.json()["warnings"] == [
        {"loc": ["basics", "fqdn"], "msg": "does not start with the hostname 'web-01'"}
    ]


def test_no_warnings_for_consistent_input(client):
    """FR-005: matching hostname and FQDN produce no warning."""
    body = {"name": "x", "basics": {"hostname": "web-01", "fqdn": "web-01.example.com"}, **WITH_KEY}
    assert client.post("/api/preview", json=body).json()["warnings"] == []


def test_defaults_provide_a_new_configuration_with_secure_ssh(client):
    """FR-015, FR-011: a new configuration starts empty with secure defaults."""
    data = client.get("/api/defaults").json()
    config = data["configuration"]
    assert config["name"] == "New configuration"
    assert config["ssh"]["password_authentication"] is False
    assert config["ssh"]["disable_root"] is True
    assert config["network"] == {"ethernets": [], "bridges": []}
    # The defaults are accepted as they are.
    assert client.post("/api/preview", json=config).status_code == 200


def test_defaults_provide_item_templates(client):
    """FR-004: list entries start from the model's defaults (single source of truth)."""
    items = client.get("/api/defaults").json()["items"]
    assert set(items) == {"ethernet", "bridge", "write_file", "user", "group", "disk", "partition"}
    assert items["user"]["shell"] == "/bin/bash"
    assert items["user"]["lock_passwd"] is True
    assert "password" not in items["user"]
    assert items["disk"]["overwrite"] is False
    assert items["partition"]["mount_options"] == "defaults,nofail"
    assert items["write_file"]["encoding"] == "text"
