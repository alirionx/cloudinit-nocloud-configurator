"""FR-010: users and groups.

Passwords are never stored in plain text (NFR-007): a plain-text password is accepted
as write-only input, hashed immediately (SHA-512-crypt) and only the hash is kept.
"""

import re
import subprocess
from typing import Annotated

from pydantic import AfterValidator, Field, SecretStr

from app.configurations.sections.common import EmptyAsNone, Section, UniqueList, matches
from app.configurations.sections.ssh import SshPublicKey

# Debian user and group names (adduser's default NAME_REGEX, slightly relaxed for upper case).
_NAME = r"[a-z_][a-z0-9_-]{0,31}"
UserName = Annotated[
    str, matches(_NAME, "must be a user name like 'admin': lower case letters, digits, _ and -")
]
GroupName = Annotated[
    str, matches(_NAME, "must be a group name like 'docker': lower case letters, digits, _ and -")
]

# crypt(3) formats accepted by Debian: SHA-512 ($6$), SHA-256 ($5$) and yescrypt ($y$).
CRYPT_RE = re.compile(
    r"\$6\$(?:rounds=\d+\$)?[./A-Za-z0-9]{1,16}\$[./A-Za-z0-9]{86}"
    r"|\$5\$(?:rounds=\d+\$)?[./A-Za-z0-9]{1,16}\$[./A-Za-z0-9]{43}"
    r"|\$y\$[./A-Za-z0-9]+\$[./A-Za-z0-9]+\$[./A-Za-z0-9]{43}"
)


def _check_hash(value: str) -> str:
    if not CRYPT_RE.fullmatch(value):
        raise ValueError(
            "must be a crypt hash such as SHA-512 ('$6$...', e.g. from 'mkpasswd -m sha-512')"
        )
    return value


def _check_shell(value: str) -> str:
    if not value.startswith("/") or any(c.isspace() for c in value):
        raise ValueError("must be an absolute path like '/bin/bash'")
    return value


def _check_single_line(value: str) -> str:
    if "\n" in value or "\r" in value:
        raise ValueError("must be a single line")
    return value


def _check_gecos(value: str) -> str:
    if ":" in value or "\n" in value:
        raise ValueError("must not contain ':' or line breaks")
    return value


PasswordHash = Annotated[str, AfterValidator(_check_hash)]

PASSWORDLESS_SUDO = "ALL=(ALL) NOPASSWD:ALL"
ADMIN_GROUP = "sudo"  # Debian's administrator group (not 'wheel')


class Group(Section):
    name: GroupName
    members: UniqueList[UserName] = Field(default_factory=list)


class User(Section):
    name: UserName
    gecos: EmptyAsNone[Annotated[str, AfterValidator(_check_gecos)]] = Field(
        default=None, description="Display name."
    )
    primary_group: EmptyAsNone[GroupName] = None
    groups: UniqueList[GroupName] = Field(default_factory=list)
    admin: bool = Field(
        default=False, description=f"Administrator: member of the Debian group '{ADMIN_GROUP}'."
    )
    sudo: EmptyAsNone[Annotated[str, AfterValidator(_check_single_line)]] = Field(
        default=None, description=f"sudo rule, e.g. '{PASSWORDLESS_SUDO}' (passwordless)."
    )
    shell: EmptyAsNone[Annotated[str, AfterValidator(_check_shell)]] = "/bin/bash"
    password: EmptyAsNone[SecretStr] = Field(
        default=None,
        exclude=True,
        description="Write-only plain-text password. Hashed immediately; never stored or returned.",
    )
    password_hash: EmptyAsNone[PasswordHash] = Field(
        default=None, description="Password hash (crypt format) as written to user-data."
    )
    lock_passwd: bool = Field(default=True, description="Disable password login for this user.")
    ssh_authorized_keys: UniqueList[SshPublicKey] = Field(default_factory=list)
    system: bool = Field(default=False, description="Create a system user (no home directory).")

    def all_groups(self) -> list[str]:
        """Supplementary groups including the admin group."""
        groups = list(self.groups)
        if self.admin and ADMIN_GROUP not in groups:
            groups.append(ADMIN_GROUP)
        return groups


class Users(Section):
    keep_default_user: bool = Field(
        default=True,
        description="Keep the distribution's default user (e.g. 'debian') in addition.",
    )
    users: list[User] = Field(default_factory=list)
    groups: list[Group] = Field(default_factory=list)


class PasswordHashingError(Exception):
    pass


def hash_password(password: str) -> str:
    """SHA-512-crypt via `openssl passwd -6` (random salt).

    The password is passed on stdin, never as an argument, so it does not show up in
    process listings (NFR-007).
    """
    try:
        result = subprocess.run(
            ["openssl", "passwd", "-6", "-stdin"],
            input=password.encode() + b"\n",
            capture_output=True,
            timeout=10,
            check=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PasswordHashingError(type(exc).__name__) from None
    hashed = result.stdout.decode().strip()
    if not CRYPT_RE.fullmatch(hashed):
        raise PasswordHashingError("unexpected output")
    return hashed
