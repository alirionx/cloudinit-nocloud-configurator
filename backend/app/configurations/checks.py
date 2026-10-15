"""Rules that span several fields (FR-005 to FR-012).

- Errors are invalid combinations; they block saving (HTTP 422), like field errors.
- Warnings point to likely mistakes; saving stays possible.

Each issue names the affected field (`loc`, the same path format as validation
errors) so the UI can show it at the field and link to it (FR-013).
"""

import ipaddress
from collections import Counter
from dataclasses import dataclass, field

from pydantic import BaseModel

from app.configurations.keys import (
    KNOWN_USER_DATA_KEYS,
    META_DATA_FIELDS,
    NETWORK_KEYS,
    SECTION_OF_KEY,
)
from app.configurations.model import Configuration
from app.configurations.sections.disks import LABEL_LIMITS
from app.configurations.sections.network import AddressSettings

# Groups that exist on a standard Debian system (base-passwd), so users may join them
# without defining them (FR-010).
DEBIAN_STANDARD_GROUPS = frozenset(
    [
        "root",
        "daemon",
        "bin",
        "sys",
        "adm",
        "tty",
        "disk",
        "lp",
        "mail",
        "news",
        "uucp",
        "man",
        "proxy",
        "kmem",
        "dialout",
        "fax",
        "voice",
        "cdrom",
        "floppy",
        "tape",
        "sudo",
        "audio",
        "dip",
        "www-data",
        "backup",
        "operator",
        "list",
        "irc",
        "src",
        "shadow",
        "utmp",
        "video",
        "sasl",
        "plugdev",
        "staff",
        "games",
        "users",
        "nogroup",
        "systemd-journal",
        "netdev",
        "input",
        "render",
        "kvm",
    ]
)


class Issue(BaseModel):
    loc: list[str | int]
    msg: str


@dataclass
class CheckResult:
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)

    def error(self, loc: list[str | int], msg: str) -> None:
        self.errors.append(Issue(loc=loc, msg=msg))

    def warn(self, loc: list[str | int], msg: str) -> None:
        self.warnings.append(Issue(loc=loc, msg=msg))


def check(config: Configuration) -> CheckResult:
    result = CheckResult()
    _check_basics(config, result)
    _check_network(config, result)
    _check_files(config, result)
    _check_users(config, result)
    _check_ssh(config, result)
    _check_disks(config, result)
    _check_additional(config, result)
    return result


def _check_basics(config: Configuration, result: CheckResult) -> None:
    basics = config.basics
    if basics.fqdn and basics.hostname and not basics.fqdn.startswith(f"{basics.hostname}."):
        result.warn(["basics", "fqdn"], f"does not start with the hostname '{basics.hostname}'")


# --- FR-006 ---


def _check_gateways(settings: AddressSettings, loc: list[str | int], result: CheckResult) -> None:
    networks = [ipaddress.ip_interface(address).network for address in settings.addresses]
    for name, gateway, version in (
        ("gateway4", settings.gateway4, 4),
        ("gateway6", settings.gateway6, 6),
    ):
        if not gateway:
            continue
        same_family = [network for network in networks if network.version == version]
        if not same_family:
            dhcp = settings.dhcp4 if version == 4 else settings.dhcp6
            if not dhcp:
                result.warn([*loc, name], f"no static IPv{version} address is configured")
            continue
        address = ipaddress.ip_address(gateway)
        if not any(address in network for network in same_family):
            subnets = ", ".join(str(network) for network in same_family)
            result.warn([*loc, name], f"is outside the configured subnet ({subnets})")


def _check_network(config: Configuration, result: CheckResult) -> None:
    network = config.network
    names = Counter(
        [nic.name for nic in network.ethernets] + [bridge.name for bridge in network.bridges]
    )
    nic_index = {nic.name: index for index, nic in enumerate(network.ethernets)}
    # Interfaces defined as additional settings (e.g. bonds, VLANs) may be bridge members.
    extra_interfaces = {
        name
        for kind in ("bonds", "vlans", "ethernets", "wifis")
        if isinstance(devices := config.additional.network.get(kind), dict)
        for name in devices
    }
    macs = Counter(nic.match_mac for nic in network.ethernets if nic.match_mac)

    for index, nic in enumerate(network.ethernets):
        loc: list[str | int] = ["network", "ethernets", index]
        if names[nic.name] > 1:
            result.error([*loc, "name"], f"interface name '{nic.name}' is used more than once")
        if nic.match_mac and macs[nic.match_mac] > 1:
            result.warn([*loc, "match_mac"], "the same MAC address is matched more than once")
        _check_gateways(nic, loc, result)

    members: dict[str, str] = {}
    for index, bridge in enumerate(network.bridges):
        loc = ["network", "bridges", index]
        if names[bridge.name] > 1 and bridge.name not in nic_index:
            result.error([*loc, "name"], f"interface name '{bridge.name}' is used more than once")
        if not bridge.interfaces:
            result.warn([*loc, "interfaces"], "the bridge has no member interfaces")
        for member in bridge.interfaces:
            if member in extra_interfaces and member not in nic_index:
                continue
            if member not in nic_index:
                result.error([*loc, "interfaces"], f"'{member}' is not a defined NIC")
                continue
            if member in members:
                result.error(
                    [*loc, "interfaces"],
                    f"'{member}' is already a member of bridge '{members[member]}'",
                )
            members[member] = bridge.name
            nic = network.ethernets[nic_index[member]]
            if nic.has_address_settings():
                result.error(
                    ["network", "ethernets", nic_index[member], "addresses"],
                    f"is a member of bridge '{bridge.name}' and must not have an address, "
                    "gateway or DHCP of its own; configure them on the bridge",
                )
        _check_gateways(bridge, loc, result)


# --- FR-008 ---


def _check_files(config: Configuration, result: CheckResult) -> None:
    created_users = {user.name for user in config.users.users}
    seen: dict[str, int] = {}
    for index, file in enumerate(config.write_files):
        loc: list[str | int] = ["write_files", index]
        if file.path in seen and not file.append:
            result.warn(
                [*loc, "path"],
                f"the same path is already written by file #{seen[file.path] + 1}; "
                "enable 'append' or the later file overwrites it",
            )
        seen.setdefault(file.path, index)
        owner = file.owner_user()
        if owner in created_users and not file.defer:
            result.warn(
                [*loc, "defer"],
                f"user '{owner}' is created by cloud-init; enable 'defer' so the file is "
                "written after the user exists",
            )


# --- FR-010 ---


def _check_users(config: Configuration, result: CheckResult) -> None:
    users = config.users
    user_names = Counter(user.name for user in users.users)
    group_names = Counter(group.name for group in users.groups)
    known_groups = set(group_names) | DEBIAN_STANDARD_GROUPS

    for index, group in enumerate(users.groups):
        if group_names[group.name] > 1:
            result.error(
                ["users", "groups", index, "name"], f"group '{group.name}' is defined twice"
            )

    for index, user in enumerate(users.users):
        loc: list[str | int] = ["users", "users", index]
        if user_names[user.name] > 1:
            result.error([*loc, "name"], f"user '{user.name}' is defined twice")
        unknown = [group for group in user.groups if group not in known_groups]
        if unknown:
            result.warn(
                [*loc, "groups"],
                f"group(s) {', '.join(repr(g) for g in unknown)} are neither defined in the "
                "groups section nor standard Debian groups",
            )
        if user.primary_group and user.primary_group not in known_groups:
            result.warn(
                [*loc, "primary_group"],
                f"group '{user.primary_group}' is neither defined in the groups section nor "
                "a standard Debian group",
            )
        if user.password_hash and user.lock_passwd:
            result.warn(
                [*loc, "lock_passwd"],
                "a password is set but locked; disable 'lock password' to allow password login",
            )


# --- FR-011 ---


def _check_ssh(config: Configuration, result: CheckResult) -> None:
    ssh = config.ssh
    has_key = bool(ssh.authorized_keys) or any(
        user.ssh_authorized_keys for user in config.users.users
    )
    if not ssh.password_authentication and not has_key:
        result.warn(
            ["ssh", "password_authentication"],
            "password login is disabled and no user has an SSH key: "
            "the VM will not be reachable via SSH",
        )
    if not ssh.host_key_types:
        result.error(["ssh", "host_key_types"], "select at least one host key type")


# --- FR-012 ---


def _check_disks(config: Configuration, result: CheckResult) -> None:
    devices = Counter(disk.device for disk in config.disks)
    mount_points = Counter(
        p.mount_point for disk in config.disks for p in disk.partitions if p.mount_point
    )
    labels = Counter(p.label for disk in config.disks for p in disk.partitions if p.label)

    for d, disk in enumerate(config.disks):
        loc: list[str | int] = ["disks", d]
        if devices[disk.device] > 1:
            result.error([*loc, "device"], f"device '{disk.device}' is configured twice")
        total = sum(p.size_percent for p in disk.partitions)
        if total > 100:
            result.error([*loc, "partitions"], f"partitions use {total}% of the disk (max. 100%)")
        if disk.overwrite:
            result.warn(
                [*loc, "overwrite"],
                "existing partitions and filesystems on this disk will be destroyed",
            )
        for p, partition in enumerate(disk.partitions):
            ploc: list[str | int] = [*loc, "partitions", p]
            fs = partition.filesystem
            if partition.mount_point:
                if mount_points[partition.mount_point] > 1:
                    result.error(
                        [*ploc, "mount_point"],
                        f"mount point '{partition.mount_point}' is used more than once",
                    )
                if not fs:
                    result.error([*ploc, "mount_point"], "needs a filesystem to be mounted")
                if not partition.label:
                    result.error([*ploc, "label"], "is required to mount the filesystem")
            if partition.label:
                if labels[partition.label] > 1:
                    result.error(
                        [*ploc, "label"], f"label '{partition.label}' is used more than once"
                    )
                if fs and len(partition.label) > LABEL_LIMITS[fs]:
                    result.error(
                        [*ploc, "label"],
                        f"{fs} labels are limited to {LABEL_LIMITS[fs]} characters",
                    )
            if fs in ("xfs", "btrfs"):
                tool = "xfsprogs" if fs == "xfs" else "btrfs-progs"
                result.warn(
                    [*ploc, "filesystem"],
                    f"requires '{tool}' in the VM image (disks are set up before packages "
                    "are installed)",
                )


# --- FR-014 ---

CRYPT_PREFIXES = ("$1$", "$5$", "$6$", "$y$", "$2a$", "$2b$", "$2y$", "$gy$", "$7$")


def _is_hashed(value: object) -> bool:
    return isinstance(value, str) and value.startswith(CRYPT_PREFIXES)


def _chpasswd_has_plain_text(chpasswd: object) -> bool:
    """chpasswd: `users` entries with `type: text`, or legacy `list` lines 'user:password'."""
    if not isinstance(chpasswd, dict):
        return False
    users = chpasswd.get("users")
    if isinstance(users, list) and any(
        isinstance(entry, dict) and entry.get("type") == "text" for entry in users
    ):
        return True
    legacy = chpasswd.get("list")
    lines = legacy.splitlines() if isinstance(legacy, str) else legacy
    if isinstance(lines, list):
        for line in lines:
            password = str(line).partition(":")[2]
            if password and password != "RANDOM" and not _is_hashed(password):
                return True
    return False


def _plain_password_keys(user_data: dict) -> list[str]:
    """Keys of additional user-data that contain plain-text passwords (NFR-007)."""
    found = []
    if "password" in user_data:  # cloud-init: plain password of the default user
        found.append("password")
    users = user_data.get("users")
    if isinstance(users, list) and any(
        isinstance(user, dict)
        and ("plain_text_passwd" in user or ("passwd" in user and not _is_hashed(user["passwd"])))
        for user in users
    ):
        found.append("users")
    if _chpasswd_has_plain_text(user_data.get("chpasswd")):
        found.append("chpasswd")
    return found


def _check_additional(config: Configuration, result: CheckResult) -> None:
    from app.configurations.rendering import form_user_data  # avoid import cycle

    additional = config.additional
    known = KNOWN_USER_DATA_KEYS & set(additional.user_data)
    if known:
        form = form_user_data(config)
        default = form_user_data(Configuration(name="default"))
        for key in sorted(known):
            if form.get(key) != default.get(key):
                result.error(
                    ["additional", "user_data", key],
                    f"'{key}' is set both in the form ({SECTION_OF_KEY[key]}) and in the "
                    "additional settings; remove one of them",
                )
    for key in META_DATA_FIELDS.keys() & set(additional.meta_data):
        result.error(["additional", "meta_data", key], f"'{key}' is managed by the basics section")
    if not config.network.is_empty():
        for key in set(NETWORK_KEYS) & set(additional.network):
            if key != "version" or additional.network[key] != 2:
                result.error(
                    ["additional", "network", key], f"'{key}' is managed by the network section"
                )
    for key in _plain_password_keys(additional.user_data):
        result.warn(
            ["additional", "user_data", key],
            "contains a plain-text password; use a password hash instead (e.g. "
            "'mkpasswd -m sha-512')",
        )
