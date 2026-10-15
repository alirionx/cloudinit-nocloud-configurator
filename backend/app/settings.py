"""Application settings, read exclusively from environment variables (NFR-003)."""

from pathlib import Path
from typing import Literal, Self

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Invalid values abort startup with a clear error (DS-004)."""

    model_config = SettingsConfigDict(extra="ignore")

    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["debug", "info", "warning", "error", "critical"] = "info"
    # Directory containing the built frontend (index.html). Unset: API only.
    static_dir: Path | None = None

    # Datastore (section 8.3)
    datastore_backend: Literal["tinydb", "couchdb"] = "tinydb"
    tinydb_path: Path = Path("./data/db.json")
    couchdb_url: AnyHttpUrl | None = None
    couchdb_user: str | None = None
    couchdb_password: SecretStr | None = None
    # CouchDB database name rules: https://docs.couchdb.org/en/stable/api/database/common.html
    couchdb_database: str = Field(default="cloudinit", pattern=r"^[a-z][a-z0-9_$()+/-]*$")

    @field_validator("log_level", "datastore_backend", mode="before")
    @classmethod
    def _lowercase(cls, value: object) -> object:
        return value.lower() if isinstance(value, str) else value

    @field_validator("static_dir")
    @classmethod
    def _static_dir_has_index(cls, value: Path | None) -> Path | None:
        if value is not None and not (value / "index.html").is_file():
            raise ValueError(f"STATIC_DIR '{value}' does not contain an index.html")
        return value

    @model_validator(mode="after")
    def _couchdb_settings_complete(self) -> Self:
        if self.datastore_backend == "couchdb":
            missing = [
                name.upper()
                for name in ("couchdb_url", "couchdb_user", "couchdb_password")
                if not getattr(self, name)
            ]
            if missing:
                raise ValueError(
                    f"DATASTORE_BACKEND=couchdb requires {', '.join(missing)} to be set"
                )
        return self
