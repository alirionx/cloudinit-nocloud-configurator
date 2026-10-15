"""Default values for new configurations and list entries (FR-004, FR-015).

The model stays the single source of truth for defaults (e.g. the secure SSH
defaults of FR-011): the form fetches them instead of duplicating them.
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.configurations.model import Configuration
from app.configurations.sections.disks import Disk, Partition
from app.configurations.sections.files import WriteFile
from app.configurations.sections.network import Bridge, Ethernet
from app.configurations.sections.users import Group, User

router = APIRouter(prefix="/api", tags=["defaults"])

NEW_CONFIGURATION_NAME = "New configuration"


class Defaults(BaseModel):
    configuration: dict[str, Any]
    items: dict[str, dict[str, Any]]


def _template(model: type[BaseModel], **required: Any) -> dict[str, Any]:
    """Defaults of a model; required fields get empty placeholders for the form."""
    return model.model_construct(**required).model_dump(mode="json")


@router.get("/defaults")
async def defaults() -> Defaults:
    """A new, empty configuration with secure defaults, and templates for list entries."""
    return Defaults(
        configuration=Configuration(name=NEW_CONFIGURATION_NAME).model_dump(mode="json"),
        items={
            "ethernet": _template(Ethernet, name=""),
            "bridge": _template(Bridge, name=""),
            "write_file": _template(WriteFile, path=""),
            "user": _template(User, name=""),
            "group": _template(Group, name=""),
            "disk": _template(Disk, device="", partitions=[Partition()]),
            "partition": _template(Partition),
        },
    )
