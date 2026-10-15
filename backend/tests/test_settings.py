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
