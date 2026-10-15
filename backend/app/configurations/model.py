"""The configuration model: single source of truth for form, REST API and YAML (FR-004).

Each form section is a sub-model in `app.configurations.sections`. Optional fields
that are empty produce no YAML keys. Rules that span several fields (e.g. bridge
members, duplicate mount points) live in `app.configurations.checks`.
"""

from typing import Annotated

from pydantic import Field

from app.configurations.sections.basics import Basics, suggest_instance_id
from app.configurations.sections.commands import Commands
from app.configurations.sections.common import Section
from app.configurations.sections.disks import Disk
from app.configurations.sections.files import WriteFile
from app.configurations.sections.network import Network
from app.configurations.sections.packages import Packages
from app.configurations.sections.ssh import Ssh
from app.configurations.sections.users import Users

__all__ = ["NAME_MAX_LENGTH", "Basics", "Configuration", "suggest_instance_id"]

NAME_MAX_LENGTH = 100


class Configuration(Section):
    """A NoCloud configuration as edited in the form or sent via the REST API."""

    name: Annotated[str, Field(min_length=1, max_length=NAME_MAX_LENGTH)] = Field(
        description="App-internal name of the configuration."
    )
    basics: Basics = Field(default_factory=Basics, description="FR-005")
    network: Network = Field(default_factory=Network, description="FR-006")
    packages: Packages = Field(default_factory=Packages, description="FR-007")
    write_files: list[WriteFile] = Field(default_factory=list, description="FR-008")
    commands: Commands = Field(default_factory=Commands, description="FR-009")
    users: Users = Field(default_factory=Users, description="FR-010")
    ssh: Ssh = Field(default_factory=Ssh, description="FR-011")
    disks: list[Disk] = Field(default_factory=list, description="FR-012")
