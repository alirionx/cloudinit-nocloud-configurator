"""The configuration model: single source of truth for form, REST API and YAML (FR-004).

Each form section is a sub-model. Optional fields that are empty produce no YAML keys.
Further sections (FR-006 to FR-012) are added here as they are implemented.
"""

import re
import uuid
import zoneinfo
from functools import cache
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field

# RFC 1123: a label is 1-63 letters, digits or hyphens, not starting or ending with a hyphen.
_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
HOSTNAME_PATTERN = rf"^{_LABEL}$"
FQDN_RE = re.compile(rf"^{_LABEL}(?:\.{_LABEL})+$")
# instance-id: printable without whitespace, so it is safe in YAML and file names.
INSTANCE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
# POSIX locale: language[_TERRITORY][.codeset][@modifier], or C / POSIX.
NAME_MAX_LENGTH = 100
LOCALE_PATTERN = r"^(C|POSIX|[a-z]{2,3}(_[A-Z]{2})?)(\.[A-Za-z0-9-]+)?(@[A-Za-z0-9]+)?$"


def _empty_to_none(value: Any) -> Any:
    """Forms send empty strings for empty fields; treat them as "not set"."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _check_fqdn(value: str) -> str:
    if len(value) > 253 or not FQDN_RE.fullmatch(value):
        raise ValueError(
            "must be a fully qualified domain name such as 'web-01.example.com' (RFC 1123)"
        )
    return value


@cache
def _timezones() -> frozenset[str]:
    return frozenset(zoneinfo.available_timezones())


def _check_timezone(value: str) -> str:
    if value not in _timezones():
        raise ValueError("must be an IANA time zone such as 'Europe/Berlin' or 'UTC'")
    return value


type EmptyAsNone[T] = Annotated[T | None, BeforeValidator(_empty_to_none)]


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Basics(_Section):
    """FR-005: basics and meta-data."""

    instance_id: EmptyAsNone[Annotated[str, Field(pattern=INSTANCE_ID_PATTERN)]] = Field(
        default=None,
        description="NoCloud instance-id. Generated as iid-<hostname>-<short-uuid> if empty.",
    )
    hostname: EmptyAsNone[Annotated[str, Field(pattern=HOSTNAME_PATTERN)]] = Field(
        default=None, description="local-hostname (RFC 1123 label, e.g. 'web-01')."
    )
    fqdn: EmptyAsNone[Annotated[str, AfterValidator(_check_fqdn)]] = None
    timezone: EmptyAsNone[Annotated[str, AfterValidator(_check_timezone)]] = Field(
        default=None, description="IANA time zone, e.g. 'Europe/Berlin'."
    )
    locale: EmptyAsNone[Annotated[str, Field(pattern=LOCALE_PATTERN)]] = Field(
        default=None, description="System locale, e.g. 'en_US.UTF-8'."
    )


class Configuration(_Section):
    """A NoCloud configuration as edited in the form or sent via the REST API."""

    name: Annotated[str, Field(min_length=1, max_length=NAME_MAX_LENGTH)] = Field(
        description="App-internal name of the configuration."
    )
    basics: Basics = Field(default_factory=Basics)


def suggest_instance_id(hostname: str | None) -> str:
    """FR-005: a unique instance-id, e.g. 'iid-web-01-3f2a9c1e'."""
    short = uuid.uuid4().hex[:8]
    return f"iid-{hostname}-{short}" if hostname else f"iid-{short}"
