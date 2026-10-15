"""FR-012: partition, format and mount additional disks (disk_setup, fs_setup, mounts)."""

from typing import Annotated, Literal

from pydantic import AfterValidator, Field

from app.configurations.sections.common import EmptyAsNone, Section, matches

# Maximum label lengths per filesystem.
LABEL_LIMITS = {"ext4": 16, "xfs": 12, "btrfs": 255}
DEFAULT_MOUNT_OPTIONS = "defaults,nofail"


def _check_mount_point(value: str) -> str:
    if not value.startswith("/") or any(c.isspace() for c in value):
        raise ValueError("must be an absolute path like '/srv/data'")
    if value == "/":
        raise ValueError("must not be the root filesystem")
    return value.rstrip("/")


Device = Annotated[
    str,
    matches(
        r"/dev/[A-Za-z0-9._:/-]+",
        "must be a device path like '/dev/vdb' or '/dev/disk/by-id/...'",
    ),
]
FsLabel = Annotated[
    str, matches(r"[A-Za-z0-9_.-]{1,255}", "must contain only letters, digits, _ . and -")
]
MountPoint = Annotated[str, AfterValidator(_check_mount_point)]
MountOptions = Annotated[
    str, matches(r"[A-Za-z0-9_=,.:/-]+", "must be mount options like 'defaults,nofail'")
]


class Partition(Section):
    size_percent: Annotated[int, Field(ge=1, le=100)] = Field(
        default=100, description="Share of the disk in percent."
    )
    filesystem: Literal["ext4", "xfs", "btrfs"] | None = "ext4"
    label: EmptyAsNone[FsLabel] = None
    mount_point: EmptyAsNone[MountPoint] = None
    mount_options: EmptyAsNone[MountOptions] = DEFAULT_MOUNT_OPTIONS


class Disk(Section):
    device: Device
    table_type: Literal["gpt", "mbr"] = "gpt"
    overwrite: bool = Field(
        default=False,
        description="Force overwriting existing partitions and filesystems (data loss!).",
    )
    partitions: Annotated[list[Partition], Field(min_length=1)] = Field(
        default_factory=lambda: [Partition()]
    )
