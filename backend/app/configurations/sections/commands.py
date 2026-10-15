"""FR-009: commands run at boot (bootcmd on every boot, runcmd once)."""

from typing import Annotated

from pydantic import AfterValidator, Field

from app.configurations.sections.common import Section


def _non_empty_command(value: str | list[str]) -> str | list[str]:
    if isinstance(value, str):
        if not value.strip():
            raise ValueError("must not be empty")
        return value
    if not value or not value[0].strip():
        raise ValueError("a command with arguments needs at least the command itself")
    return value


# A shell line (string) or a command with arguments (list), as in cloud-init.
Command = Annotated[str | list[str], AfterValidator(_non_empty_command)]


class Commands(Section):
    bootcmd: list[Command] = Field(
        default_factory=list, description="Run very early on every boot."
    )
    runcmd: list[Command] = Field(
        default_factory=list, description="Run once at the end of the first boot."
    )

    # Commands are kept exactly as entered (indentation in scripts matters).
    model_config = Section.model_config | {"str_strip_whitespace": False}
