"""FR-007: package management (Debian / apt)."""

from typing import Annotated

from pydantic import Field

from app.configurations.sections.common import Section, UniqueList, matches

# Debian policy 5.6.1: lower case letters, digits, + - . ; at least two characters.
# An optional version pin (pkg=version) is accepted, as apt and cloud-init allow it.
PackageName = Annotated[
    str,
    matches(
        r"[a-z0-9][a-z0-9+.-]+(?:=[A-Za-z0-9.+:~-]+)?",
        "must be a Debian package name like 'docker.io' (lower case, digits, + - .)",
    ),
]


class Packages(Section):
    update: bool = Field(default=False, description="package_update: refresh package sources.")
    upgrade: bool = Field(default=False, description="package_upgrade: upgrade all packages.")
    reboot_if_required: bool = Field(
        default=False, description="package_reboot_if_required: reboot after upgrades if needed."
    )
    packages: UniqueList[PackageName] = Field(default_factory=list)
