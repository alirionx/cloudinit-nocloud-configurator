from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from app.configurations.checks import CheckResult, check
from app.configurations.model import Configuration
from app.configurations.rendering import render_files


def config(**sections: Any) -> Configuration:
    return Configuration.model_validate(
        {"name": "test", "basics": {"instance_id": "iid-test"}, **sections}
    )


def user_data(cfg: Configuration) -> dict[str, Any]:
    return yaml.safe_load(render_files(cfg)["user-data"])


def network_config(cfg: Configuration) -> dict[str, Any] | None:
    text = render_files(cfg)["network-config"]
    return yaml.safe_load(text) if text else None


def locs(issues) -> list[list[str | int]]:
    return [issue.loc for issue in issues]


def checked(**sections: Any) -> CheckResult:
    return check(config(**sections))


def field_error(**sections: Any) -> list[tuple]:
    """Locations of model validation errors."""
    with pytest.raises(ValidationError) as excinfo:
        config(**sections)
    return [error["loc"] for error in excinfo.value.errors()]
