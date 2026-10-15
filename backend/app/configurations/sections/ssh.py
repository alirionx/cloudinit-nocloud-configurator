"""FR-011: SSH configuration with secure defaults."""

import base64
import binascii
import struct
from typing import Annotated, Literal

from pydantic import AfterValidator, Field

from app.configurations.sections.common import Section, UniqueList

KEY_TYPES = {
    "ssh-ed25519",
    "ssh-rsa",
    "ecdsa-sha2-nistp256",
    "ecdsa-sha2-nistp384",
    "ecdsa-sha2-nistp521",
    "sk-ssh-ed25519@openssh.com",
    "sk-ecdsa-sha2-nistp256@openssh.com",
}
HOST_KEY_TYPES = ("rsa", "ecdsa", "ed25519")


def _check_public_key(value: str) -> str:
    """An OpenSSH public key line: '<type> <base64> [comment]'.

    The Base64 blob must decode and name the same key type, which catches truncated
    or mixed-up keys. Options before the key type (authorized_keys syntax) are not accepted.
    """
    value = " ".join(value.split())
    parts = value.split(" ", 2)
    message = "must be an SSH public key like 'ssh-ed25519 AAAA... user@host'"
    if len(parts) < 2 or parts[0] not in KEY_TYPES:
        raise ValueError(message)
    try:
        blob = base64.b64decode(parts[1], validate=True)
        (length,) = struct.unpack(">I", blob[:4])
        embedded_type = blob[4 : 4 + length].decode("ascii")
    except (binascii.Error, ValueError, struct.error, UnicodeDecodeError):
        raise ValueError(f"{message}; the key data is not valid") from None
    if embedded_type != parts[0]:
        raise ValueError(f"{message}; the key data does not match the type '{parts[0]}'")
    return value


SshPublicKey = Annotated[str, AfterValidator(_check_public_key)]


class Ssh(Section):
    password_authentication: bool = Field(
        default=False, description="ssh_pwauth: allow password login (off by default)."
    )
    disable_root: bool = Field(default=True, description="Disable root login (on by default).")
    delete_host_keys: bool = Field(
        default=True, description="ssh_deletekeys: remove host keys of the image."
    )
    host_key_types: list[Literal["rsa", "ecdsa", "ed25519"]] = Field(
        default_factory=lambda: list(HOST_KEY_TYPES),
        description="ssh_genkeytypes: host key types to generate.",
    )
    authorized_keys: UniqueList[SshPublicKey] = Field(
        default_factory=list,
        description="ssh_authorized_keys: keys for the distribution's default user.",
    )
