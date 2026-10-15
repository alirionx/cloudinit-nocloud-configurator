"""Validation against the official cloud-init JSON schemas (NFR-008, FR-014).

Violations are hints, not errors: saving stays possible, the download shows a warning.
"""

import json
import re
from functools import cache
from importlib import resources
from typing import Any

from jsonschema import Draft4Validator, Draft7Validator
from jsonschema.exceptions import ValidationError
from pydantic import BaseModel

from app.configurations.rendering import NETWORK_CONFIG, USER_DATA, VENDOR_DATA
from app.configurations.yaml_input import YamlInputError, load_yaml

MAX_ISSUES_PER_FILE = 20


class SchemaIssue(BaseModel):
    file: str
    path: list[str | int]
    line: int | None
    msg: str


@cache
def _validator(name: str, draft: type) -> Any:
    schema = json.loads(resources.files("app.schemas").joinpath(name).read_text("utf-8"))
    return draft(schema)


def _cloud_config_validator() -> Any:
    return _validator("schema-cloud-config-v1.json", Draft4Validator)


def _network_validator() -> Any:
    return _validator("schema-network-config-v2.json", Draft7Validator)


def _is_known_false_positive(error: ValidationError) -> bool:
    """cloud-init's schema rejects numeric fs_setup partitions, although its documentation
    and code support them (cc_disk_setup: `partition.isdigit()`)."""
    path = list(error.absolute_path)
    return (
        len(path) == 3
        and path[0] == "fs_setup"
        and path[2] == "partition"
        and isinstance(error.instance, int)
    )


def _message(error: ValidationError) -> str:
    # oneOf/anyOf errors are long; the most specific sub-error is more helpful.
    if error.context:
        best = min(error.context, key=lambda e: len(e.message))
        return best.message[:300]
    return error.message[:300]


def validate_files(files: dict[str, str | None]) -> list[SchemaIssue]:
    issues: list[SchemaIssue] = []
    for file_name, validator in (
        (USER_DATA, _cloud_config_validator()),
        (VENDOR_DATA, _cloud_config_validator()),
        (NETWORK_CONFIG, _network_validator()),
    ):
        text = files.get(file_name)
        if not text:
            continue
        try:
            doc = load_yaml(text)
        except YamlInputError as exc:
            issues.extend(
                SchemaIssue(file=file_name, path=[], line=i.line, msg=i.msg) for i in exc.issues
            )
            continue
        errors = [
            error
            for error in validator.iter_errors(doc.data if doc.data is not None else {})
            if not _is_known_false_positive(error)
        ]
        errors.sort(key=lambda e: [str(p) for p in e.absolute_path])
        for error in errors[:MAX_ISSUES_PER_FILE]:
            path = tuple(error.absolute_path)
            # For unexpected keys, point at the first such key instead of its parent.
            unexpected = re.search(r"\('([^']+)'", error.message)
            if error.validator == "additionalProperties" and unexpected:
                path = (*path, unexpected.group(1))
            issues.append(
                SchemaIssue(
                    file=file_name,
                    path=list(path),
                    line=doc.line_of(path) if path else 1,
                    msg=_message(error),
                )
            )
    return issues
