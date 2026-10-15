import pytest
from pydantic import ValidationError

from app.settings import Settings


def test_defaults(monkeypatch):
    """NFR-003: sensible defaults apply when no environment variables are set."""
    for name in ("HOST", "PORT", "LOG_LEVEL", "STATIC_DIR"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings()
    assert settings.port == 8000
    assert settings.log_level == "info"
    assert settings.static_dir is None


def test_reads_environment_variables(monkeypatch, tmp_path):
    """NFR-003: configuration is read from environment variables."""
    (tmp_path / "index.html").write_text("<html></html>")
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("STATIC_DIR", str(tmp_path))
    settings = Settings()
    assert settings.port == 9000
    assert settings.log_level == "debug"
    assert settings.static_dir == tmp_path


@pytest.mark.parametrize(
    ("name", "value"),
    [("PORT", "0"), ("PORT", "not-a-number"), ("LOG_LEVEL", "verbose")],
)
def test_invalid_values_are_rejected(monkeypatch, name, value):
    """NFR-003: invalid environment values abort startup with a clear error."""
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        Settings()


def test_static_dir_without_index_is_rejected(monkeypatch, tmp_path):
    """NFR-003: a STATIC_DIR without index.html aborts startup."""
    monkeypatch.setenv("STATIC_DIR", str(tmp_path))
    with pytest.raises(ValidationError, match="index.html"):
        Settings()


@pytest.fixture
def clean_datastore_env(monkeypatch):
    for name in (
        "DATASTORE_BACKEND",
        "TINYDB_PATH",
        "COUCHDB_URL",
        "COUCHDB_USER",
        "COUCHDB_PASSWORD",
        "COUCHDB_DATABASE",
    ):
        monkeypatch.delenv(name, raising=False)


def test_datastore_defaults(clean_datastore_env):
    """Section 8.3: TinyDB is the default backend with the documented defaults."""
    settings = Settings()
    assert settings.datastore_backend == "tinydb"
    assert str(settings.tinydb_path) == "data/db.json"
    assert settings.couchdb_database == "cloudinit"


def test_couchdb_settings_from_environment(clean_datastore_env, monkeypatch):
    """Section 8.3: CouchDB is configured via environment variables."""
    monkeypatch.setenv("DATASTORE_BACKEND", "CouchDB")
    monkeypatch.setenv("COUCHDB_URL", "http://couchdb:5984")
    monkeypatch.setenv("COUCHDB_USER", "admin")
    monkeypatch.setenv("COUCHDB_PASSWORD", "s3cret")
    monkeypatch.setenv("COUCHDB_DATABASE", "configs")
    settings = Settings()
    assert settings.datastore_backend == "couchdb"
    assert settings.couchdb_password.get_secret_value() == "s3cret"
    assert "s3cret" not in repr(settings)  # NFR-007
    assert settings.couchdb_database == "configs"


@pytest.mark.parametrize("missing", ["COUCHDB_URL", "COUCHDB_USER", "COUCHDB_PASSWORD"])
def test_incomplete_couchdb_settings_are_rejected(clean_datastore_env, monkeypatch, missing):
    """DS-004: CouchDB without URL, user or password is an invalid configuration."""
    values = {
        "DATASTORE_BACKEND": "couchdb",
        "COUCHDB_URL": "http://couchdb:5984",
        "COUCHDB_USER": "admin",
        "COUCHDB_PASSWORD": "pw",
    }
    del values[missing]
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError, match=missing):
        Settings()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("DATASTORE_BACKEND", "mongodb"),
        ("COUCHDB_URL", "not a url"),
        ("COUCHDB_DATABASE", "Invalid-Name"),
        ("COUCHDB_DATABASE", "_users"),
    ],
)
def test_invalid_datastore_values_are_rejected(clean_datastore_env, monkeypatch, name, value):
    """DS-004: invalid datastore values abort startup."""
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        Settings()


def test_startup_exits_with_readable_error(clean_datastore_env, monkeypatch, capsys):
    """DS-004: invalid configuration stops the app with a clear message and no secrets."""
    from app.__main__ import load_settings

    monkeypatch.setenv("DATASTORE_BACKEND", "couchdb")
    monkeypatch.setenv("COUCHDB_URL", "http://admin:url-s3cret@couchdb:5984")
    monkeypatch.setenv("COUCHDB_PASSWORD", "pw-s3cret")
    monkeypatch.setenv("PORT", "70000")
    with pytest.raises(SystemExit) as excinfo:
        load_settings()
    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "Invalid configuration" in err
    assert "PORT" in err
    assert "s3cret" not in err
