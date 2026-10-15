"""Application settings, read exclusively from environment variables (NFR-003)."""

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Invalid values abort startup with a clear error."""

    model_config = SettingsConfigDict(extra="ignore")

    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["debug", "info", "warning", "error", "critical"] = "info"
    # Directory containing the built frontend (index.html). Unset: API only.
    static_dir: Path | None = None

    @field_validator("log_level", mode="before")
    @classmethod
    def _lowercase_log_level(cls, value: object) -> object:
        return value.lower() if isinstance(value, str) else value

    @field_validator("static_dir")
    @classmethod
    def _static_dir_has_index(cls, value: Path | None) -> Path | None:
        if value is not None and not (value / "index.html").is_file():
            raise ValueError(f"STATIC_DIR '{value}' does not contain an index.html")
        return value
