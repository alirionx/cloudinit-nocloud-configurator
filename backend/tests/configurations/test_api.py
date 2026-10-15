import re
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings

URL = "/api/configurations"

WEB = {
    "name": "Web server",
    "basics": {
        "instance_id": "iid-web-01",
        "hostname": "web-01",
        "fqdn": "web-01.example.com",
        "timezone": "Europe/Berlin",
        "locale": "de_DE.UTF-8",
    },
}


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app(Settings(tinydb_path=tmp_path / "db.json"))) as client:
        yield client


def create(client: TestClient, body: dict) -> dict:
    response = client.post(URL, json=body)
    assert response.status_code == 201, response.text
    return response.json()


# --- FR-015: create, read, list ---


def test_create_returns_configuration_with_metadata(client):
    """FR-015: creating returns the stored configuration with ID, revision and timestamps."""
    response = client.post(URL, json=WEB)
    assert response.status_code == 201
    body = response.json()
    assert str(uuid.UUID(body["id"])) == body["id"]
    assert body["revision"]
    assert body["name"] == "Web server"
    assert body["basics"] == WEB["basics"]
    assert response.headers["location"] == f"{URL}/{body['id']}"


def test_create_minimal_configuration(client):
    """FR-015: a new, empty configuration only needs a name."""
    body = create(client, {"name": "New configuration"})
    assert body["basics"]["hostname"] is None


def test_get_returns_saved_configuration(client):
    """FR-015: an opened configuration contains exactly the saved values."""
    created = create(client, WEB)
    response = client.get(f"{URL}/{created['id']}")
    assert response.status_code == 200
    assert response.json() == created


def test_get_unknown_configuration_returns_404(client):
    """FR-015: unknown IDs return HTTP 404."""
    assert client.get(f"{URL}/{uuid.uuid4()}").status_code == 404
    assert client.get(f"{URL}/not-a-uuid").status_code == 404


def test_list_shows_name_hostname_and_last_modified(client):
    """FR-015: all configurations are listed with name, hostname and last modified date."""
    web = create(client, WEB)
    db = create(client, {"name": "Database", "basics": {"hostname": "db-01"}})
    empty = create(client, {"name": "Empty"})
    items = client.get(URL).json()
    assert {item["id"] for item in items} == {web["id"], db["id"], empty["id"]}
    by_id = {item["id"]: item for item in items}
    assert by_id[web["id"]] == {
        "id": web["id"],
        "name": "Web server",
        "hostname": "web-01",
        "created_at": web["created_at"],
        "modified_at": web["modified_at"],
    }
    assert by_id[empty["id"]]["hostname"] is None


def test_list_sorting(client):
    """FR-015: the list is sortable by name and by date."""
    for name in ["beta", "Alpha", "gamma"]:
        create(client, {"name": name})

    def names(sort: str) -> list[str]:
        return [item["name"] for item in client.get(URL, params={"sort": sort}).json()]

    assert names("name") == ["Alpha", "beta", "gamma"]
    assert names("-name") == ["gamma", "beta", "Alpha"]
    assert names("created_at") == ["beta", "Alpha", "gamma"]
    assert names("-modified_at") == ["gamma", "Alpha", "beta"]
    assert client.get(URL, params={"sort": "hostname"}).status_code == 422


def test_list_search_by_name_or_hostname(client):
    """FR-015: the list is filterable by name and hostname (case-insensitive)."""
    create(client, {"name": "Web server", "basics": {"hostname": "web-01"}})
    create(client, {"name": "Database", "basics": {"hostname": "pg-01"}})

    def names(search: str) -> list[str]:
        return sorted(i["name"] for i in client.get(URL, params={"search": search}).json())

    assert names("WEB") == ["Web server"]
    assert names("pg-") == ["Database"]
    assert names("01") == ["Database", "Web server"]
    assert names("nothing") == []
    assert names("  ") == ["Database", "Web server"]


# --- FR-005: instance-id suggestion ---


def test_instance_id_is_suggested_when_missing(client):
    """FR-005: without an instance-id, iid-<hostname>-<short-uuid> is generated."""
    body = create(client, {"name": "x", "basics": {"hostname": "web-01"}})
    assert re.fullmatch(r"iid-web-01-[0-9a-f]{8}", body["basics"]["instance_id"])


def test_instance_id_is_kept_on_update(client):
    """FR-005: a saved instance-id stays stable across updates."""
    created = create(client, {"name": "x", "basics": {"hostname": "web-01"}})
    updated = client.put(f"{URL}/{created['id']}", json=created).json()
    assert updated["basics"]["instance_id"] == created["basics"]["instance_id"]


# --- FR-015: update, rename, conflicts ---


def test_update_and_rename(client):
    """FR-015: saving changes (including a rename) returns the new state and revision."""
    created = create(client, WEB)
    changed = {**WEB, "name": "Renamed", "revision": created["revision"]}
    changed["basics"] = {**WEB["basics"], "timezone": "UTC"}
    response = client.put(f"{URL}/{created['id']}", json=changed)
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Renamed"
    assert body["basics"]["timezone"] == "UTC"
    assert body["revision"] != created["revision"]
    assert body["created_at"] == created["created_at"]
    assert client.get(f"{URL}/{created['id']}").json() == body


def test_get_response_can_be_sent_back_unchanged(client):
    """FR-004: a GET-modify-PUT round trip works for REST clients."""
    created = create(client, WEB)
    created["name"] = "Changed"
    assert client.put(f"{URL}/{created['id']}", json=created).status_code == 200


def test_update_with_mismatching_id_is_rejected(client):
    """FR-004: the ID in the body must match the URL."""
    created = create(client, WEB)
    other = create(client, WEB)
    response = client.put(f"{URL}/{created['id']}", json={**created, "id": other["id"]})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "id"]


def test_update_without_revision_is_rejected(client):
    """DS-003: updates must state the revision they are based on."""
    created = create(client, WEB)
    response = client.put(f"{URL}/{created['id']}", json=WEB)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "revision"]


def test_concurrent_change_returns_409(client):
    """FR-015, DS-003: saving over someone else's change returns HTTP 409."""
    created = create(client, WEB)
    first = {**WEB, "name": "First", "revision": created["revision"]}
    second = {**WEB, "name": "Second", "revision": created["revision"]}
    assert client.put(f"{URL}/{created['id']}", json=first).status_code == 200
    response = client.put(f"{URL}/{created['id']}", json=second)
    assert response.status_code == 409
    assert "changed in the meantime" in response.json()["detail"]
    assert client.get(f"{URL}/{created['id']}").json()["name"] == "First"


def test_update_unknown_configuration_returns_404(client):
    """FR-015: updating a missing configuration returns HTTP 404."""
    response = client.put(f"{URL}/{uuid.uuid4()}", json={**WEB, "revision": "1-abc"})
    assert response.status_code == 404


# --- FR-015: delete ---


def test_delete_removes_configuration(client):
    """FR-015: a deleted configuration is gone from the list and GET returns 404."""
    created = create(client, WEB)
    assert client.delete(f"{URL}/{created['id']}").status_code == 204
    assert client.get(f"{URL}/{created['id']}").status_code == 404
    assert client.get(URL).json() == []


def test_delete_unknown_configuration_returns_404(client):
    """FR-015: deleting a missing configuration returns HTTP 404."""
    assert client.delete(f"{URL}/{uuid.uuid4()}").status_code == 404


# --- FR-015: duplicate ---


def test_duplicate_creates_copy_with_new_ids(client):
    """FR-015: duplicating creates "<name> (copy)" with a new ID and a different instance-id."""
    original = create(client, WEB)
    response = client.post(f"{URL}/{original['id']}/duplicate")
    assert response.status_code == 201
    copy = response.json()
    assert copy["name"] == "Web server (copy)"
    assert copy["id"] != original["id"]
    assert copy["basics"]["instance_id"] != original["basics"]["instance_id"]
    assert copy["basics"]["instance_id"].startswith("iid-web-01-")
    assert {**copy["basics"], "instance_id": None} == {**original["basics"], "instance_id": None}
    assert response.headers["location"] == f"{URL}/{copy['id']}"
    assert len(client.get(URL).json()) == 2


def test_duplicate_of_long_name_stays_within_limit(client):
    """FR-015: the copy suffix never makes the name exceed 100 characters."""
    original = create(client, {"name": "x" * 100})
    copy = client.post(f"{URL}/{original['id']}/duplicate").json()
    assert len(copy["name"]) == 100
    assert copy["name"].endswith(" (copy)")


def test_duplicate_unknown_configuration_returns_404(client):
    """FR-015: duplicating a missing configuration returns HTTP 404."""
    assert client.post(f"{URL}/{uuid.uuid4()}/duplicate").status_code == 404


# --- FR-004: validation ---


def test_invalid_values_return_422_with_field_errors(client):
    """FR-004: invalid values yield HTTP 422 with field-level error messages."""
    body = {"name": "x", "basics": {"hostname": "web_01", "timezone": "Mars/Olympus"}}
    response = client.post(URL, json=body)
    assert response.status_code == 422
    locations = {tuple(error["loc"]) for error in response.json()["detail"]}
    assert locations == {("body", "basics", "hostname"), ("body", "basics", "timezone")}


def test_missing_name_returns_422(client):
    """FR-004: the name is required."""
    response = client.post(URL, json={"basics": {}})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "name"]


# --- FR-001, FR-004: rendered files ---


def test_saved_configuration_has_valid_user_data_and_meta_data(client):
    """FR-001: given a saved configuration, valid user-data and meta-data exist."""
    created = create(client, {"name": "minimal"})
    files = client.get(f"{URL}/{created['id']}/files").json()
    assert set(files) == {"user-data", "meta-data", "network-config", "vendor-data"}
    assert files["user-data"].startswith("#cloud-config\n")
    assert yaml.safe_load(files["meta-data"])["instance-id"] == created["basics"]["instance_id"]
    assert files["network-config"] is None


def test_form_and_rest_produce_identical_yaml(client):
    """FR-004: the same values produce identical YAML, however they were entered.

    The form sends empty strings and untrimmed values; a REST client sends clean values.
    """
    form_style = {
        "name": "Web server",
        "basics": {
            "instance_id": "iid-web-01",
            "hostname": " web-01 ",
            "fqdn": "",
            "timezone": "Europe/Berlin",
            "locale": "",
        },
    }
    rest_style = {
        "name": "Web server",
        "basics": {"instance_id": "iid-web-01", "hostname": "web-01", "timezone": "Europe/Berlin"},
    }
    files = [
        client.get(f"{URL}/{create(client, body)['id']}/files").json()
        for body in (form_style, rest_style)
    ]
    assert files[0] == files[1]


def test_files_of_unknown_configuration_returns_404(client):
    """FR-001: rendering a missing configuration returns HTTP 404."""
    assert client.get(f"{URL}/{uuid.uuid4()}/files").status_code == 404


def test_api_is_documented_in_openapi(client):
    """NFR-010: all configuration endpoints appear in the OpenAPI document."""
    paths = client.get("/openapi.json").json()["paths"]
    assert {
        URL,
        f"{URL}/{{configuration_id}}",
        f"{URL}/{{configuration_id}}/duplicate",
        f"{URL}/{{configuration_id}}/files",
    } <= set(paths)
