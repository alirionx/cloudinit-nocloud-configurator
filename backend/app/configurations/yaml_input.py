"""Safe loading of user-supplied YAML with line numbers (FR-014).

User YAML is untrusted input. Besides `safe_load` semantics, the size and the number
of nodes visited (counting alias expansions) are limited before any Python objects are
constructed. This guards against "billion laughs" style alias and merge-key expansion.
"""

import base64
import datetime
from dataclasses import dataclass, field
from typing import Any

import yaml
from pydantic import BaseModel

MAX_YAML_BYTES = 1024 * 1024
MAX_NODE_VISITS = 100_000

type YamlPath = tuple[str | int, ...]


class YamlIssue(BaseModel):
    """An error or hint located in a YAML file (1-based line, if known)."""

    line: int | None
    path: list[str | int]
    msg: str


class YamlInputError(Exception):
    def __init__(self, issues: list[YamlIssue]) -> None:
        super().__init__(issues[0].msg if issues else "invalid YAML")
        self.issues = issues


@dataclass
class YamlDocument:
    data: Any
    lines: dict[YamlPath, int] = field(default_factory=dict)

    def line_of(self, path: YamlPath) -> int | None:
        """Line of the deepest known prefix of `path`."""
        for length in range(len(path), 0, -1):
            if (line := self.lines.get(path[:length])) is not None:
                return line
        return None


def load_yaml(text: str) -> YamlDocument:
    if len(text.encode()) > MAX_YAML_BYTES:
        raise YamlInputError(
            [YamlIssue(line=None, path=[], msg=f"larger than {MAX_YAML_BYTES // 1024} KiB")]
        )
    try:
        node = yaml.compose(text, Loader=yaml.SafeLoader)
    except yaml.YAMLError as exc:
        raise YamlInputError([_syntax_issue(exc)]) from None
    if node is None:
        return YamlDocument(data=None)
    lines: dict[YamlPath, int] = {}
    _walk(node, (), lines, [0])
    loader = yaml.SafeLoader(text)
    try:
        data = loader.get_single_data()
    except yaml.YAMLError as exc:
        raise YamlInputError([_syntax_issue(exc)]) from None
    finally:
        loader.dispose()
    return YamlDocument(data=_json_compatible(data), lines=lines)


def _syntax_issue(exc: yaml.YAMLError) -> YamlIssue:
    mark = getattr(exc, "problem_mark", None) or getattr(exc, "context_mark", None)
    problem = getattr(exc, "problem", None) or str(exc)
    context = getattr(exc, "context", None)
    msg = f"{context}, {problem}" if context else str(problem)
    return YamlIssue(line=mark.line + 1 if mark else None, path=[], msg=f"YAML syntax error: {msg}")


def _walk(node: yaml.Node, path: YamlPath, lines: dict[YamlPath, int], visits: list[int]) -> None:
    visits[0] += 1
    if visits[0] > MAX_NODE_VISITS:
        raise YamlInputError(
            [YamlIssue(line=None, path=[], msg="too many nodes or aliases (max. 100000)")]
        )
    if isinstance(node, yaml.MappingNode):
        for key_node, value_node in node.value:
            key = key_node.value if isinstance(key_node, yaml.ScalarNode) else str(key_node.tag)
            child = (*path, key)
            lines.setdefault(child, key_node.start_mark.line + 1)
            _walk(value_node, child, lines, visits)
    elif isinstance(node, yaml.SequenceNode):
        for index, item in enumerate(node.value):
            child = (*path, index)
            lines.setdefault(child, item.start_mark.line + 1)
            _walk(item, child, lines, visits)


def _json_compatible(value: Any) -> Any:
    """Stored settings are JSON: dates become ISO strings, binary data Base64."""
    if isinstance(value, dict):
        return {str(key): _json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_compatible(item) for item in value]
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, bytes):
        return base64.b64encode(value).decode()
    return value
