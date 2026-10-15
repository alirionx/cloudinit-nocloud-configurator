"""Shared building blocks for the configuration sections (FR-004)."""

import re
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict


def _empty_to_none(value: Any) -> Any:
    """Forms send empty strings for empty fields; treat them as "not set"."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


type EmptyAsNone[T] = Annotated[T | None, BeforeValidator(_empty_to_none)]


def matches(regex: str, message: str) -> AfterValidator:
    """Validate a string against `regex` with a readable error message."""
    compiled = re.compile(regex)

    def check(value: str) -> str:
        if not compiled.fullmatch(value):
            raise ValueError(message)
        return value

    return AfterValidator(check)


def _strip_items(value: Any) -> Any:
    """Trim string items and drop empty ones before they are validated."""
    if isinstance(value, list):
        items = [item.strip() if isinstance(item, str) else item for item in value]
        return [item for item in items if item != ""]
    return value


def _drop_empty_and_duplicates(value: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for item in value:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


type UniqueList[T] = Annotated[
    list[T], BeforeValidator(_strip_items), AfterValidator(_drop_empty_and_duplicates)
]
"""A list of strings without empty entries and duplicates (order preserved)."""


class Section(BaseModel):
    """Base class for all form sections: unknown fields are errors, strings are trimmed."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# RFC 1123: a label is 1-63 letters, digits or hyphens, not starting or ending with a hyphen.
LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"

Hostname = Annotated[
    str, matches(LABEL, "must be a host name like 'web-01': letters, digits and hyphens (RFC 1123)")
]
