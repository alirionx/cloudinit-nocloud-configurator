"""FR-008: create files on the VM (write_files)."""

import base64
import binascii
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, BeforeValidator, Field, model_validator

from app.configurations.sections.common import EmptyAsNone, Section, matches

MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # characters; keeps seed images small (NFR-011)


def _normalize_permissions(value: str) -> str:
    return value.rjust(4, "0")


def _check_path(value: str) -> str:
    if not value.startswith("/"):
        raise ValueError("must be an absolute path starting with '/'")
    if value.endswith("/"):
        raise ValueError("must be a file path, not a directory")
    if "\x00" in value or "\n" in value:
        raise ValueError("must not contain control characters")
    return value


# Absolute path of a file on the VM.
FilePath = Annotated[str, Field(max_length=4096), AfterValidator(_check_path)]
# user, user:group or numeric IDs, e.g. 'root:root' or 'www-data:www-data'.
Owner = Annotated[
    str,
    matches(
        r"[a-z_][a-z0-9_-]*\$?(?::[a-z_][a-z0-9_-]*\$?)?|\d+(?::\d+)?",
        "must be 'user' or 'user:group', e.g. 'root:root'",
    ),
]
Permissions = Annotated[
    str,
    BeforeValidator(lambda value: format(value, "o") if isinstance(value, int) else value),
    matches(r"0?[0-7]{3,4}", "must be octal permissions like '0644'"),
    AfterValidator(_normalize_permissions),
]


class WriteFile(Section):
    path: FilePath
    content: Annotated[str, Field(max_length=MAX_CONTENT_LENGTH)] = ""
    encoding: Literal["text", "b64"] = Field(
        default="text", description="'b64' for binary content (Base64-encoded)."
    )
    owner: EmptyAsNone[Owner] = None
    permissions: EmptyAsNone[Permissions] = None
    append: bool = False
    defer: bool = Field(
        default=False, description="Write the file only after users and packages are set up."
    )

    # Content is not trimmed: whitespace can be significant in files.
    model_config = Section.model_config | {"str_strip_whitespace": False}

    @model_validator(mode="after")
    def _check_base64(self) -> Self:
        if self.encoding == "b64":
            try:
                base64.b64decode(self.content, validate=True)
            except (binascii.Error, ValueError):
                raise ValueError("content is not valid Base64") from None
        return self

    def owner_user(self) -> str | None:
        return self.owner.split(":", 1)[0] if self.owner else None
