"""FR-005: basics and meta-data."""

import uuid
import zoneinfo
from functools import cache
from typing import Annotated

from pydantic import AfterValidator, Field

from app.configurations.sections.common import LABEL, EmptyAsNone, Hostname, Section, matches


def _check_fqdn_length(value: str) -> str:
    if len(value) > 253:
        raise ValueError("must not be longer than 253 characters")
    return value


@cache
def _timezones() -> frozenset[str]:
    return frozenset(zoneinfo.available_timezones())


def _check_timezone(value: str) -> str:
    if value not in _timezones():
        raise ValueError("must be an IANA time zone such as 'Europe/Berlin' or 'UTC'")
    return value


InstanceId = Annotated[
    str,
    matches(
        r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}",
        "must start with a letter or digit and contain only letters, digits and . _ : -"
        " (max. 128 characters)",
    ),
]
Fqdn = Annotated[
    str,
    matches(
        rf"{LABEL}(?:\.{LABEL})+",
        "must be a fully qualified domain name such as 'web-01.example.com' (RFC 1123)",
    ),
    AfterValidator(_check_fqdn_length),
]
Timezone = Annotated[str, AfterValidator(_check_timezone)]
# POSIX locale: language[_TERRITORY][.codeset][@modifier], or C / POSIX.
Locale = Annotated[
    str,
    matches(
        r"(?:C|POSIX|[a-z]{2,3}(?:_[A-Z]{2})?)(?:\.[A-Za-z0-9-]+)?(?:@[A-Za-z0-9]+)?",
        "must be a locale such as 'en_US.UTF-8' or 'C.UTF-8'",
    ),
]


class Basics(Section):
    instance_id: EmptyAsNone[InstanceId] = Field(
        default=None,
        description="NoCloud instance-id. Generated as iid-<hostname>-<short-uuid> if empty.",
    )
    hostname: EmptyAsNone[Hostname] = Field(
        default=None, description="local-hostname (RFC 1123 label, e.g. 'web-01')."
    )
    fqdn: EmptyAsNone[Fqdn] = None
    timezone: EmptyAsNone[Timezone] = Field(
        default=None, description="IANA time zone, e.g. 'Europe/Berlin'."
    )
    locale: EmptyAsNone[Locale] = Field(
        default=None, description="System locale, e.g. 'en_US.UTF-8'."
    )


def suggest_instance_id(hostname: str | None) -> str:
    """FR-005: a unique instance-id, e.g. 'iid-web-01-3f2a9c1e'."""
    short = uuid.uuid4().hex[:8]
    return f"iid-{hostname}-{short}" if hostname else f"iid-{short}"
