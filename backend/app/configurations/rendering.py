"""Render the NoCloud files from the configuration model (FR-001, FR-004).

YAML is produced only here, in the backend. Output is deterministic: the same
model always yields byte-identical files. Empty sections produce no keys; the SSH
security settings are always written so that the secure defaults apply regardless
of the image's own defaults (FR-011).
"""

from typing import Any

import yaml

from app.configurations.model import Configuration
from app.configurations.sections.disks import Disk
from app.configurations.sections.network import AddressSettings, Network
from app.configurations.sections.ssh import HOST_KEY_TYPES, Ssh
from app.configurations.sections.users import Users

USER_DATA = "user-data"
META_DATA = "meta-data"
NETWORK_CONFIG = "network-config"
VENDOR_DATA = "vendor-data"

# Order of the files in previews and seed images.
FILE_NAMES = (USER_DATA, META_DATA, NETWORK_CONFIG, VENDOR_DATA)


class _Dumper(yaml.SafeDumper):
    """Safe dumper that writes multi-line strings as block literals (`|`)."""

    def ignore_aliases(self, data: Any) -> bool:
        return True


def _represent_str(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_Dumper.add_representer(str, _represent_str)


def to_yaml(data: dict[str, Any]) -> str:
    if not data:
        return ""
    return yaml.dump(
        data,
        Dumper=_Dumper,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=120,
    )


def _without_empty(data: dict[str, Any]) -> dict[str, Any]:
    """FR-004: empty values produce no keys."""
    return {key: value for key, value in data.items() if value not in (None, "", [], {})}


# --- meta-data (FR-005) ---


def meta_data(config: Configuration) -> dict[str, Any]:
    basics = config.basics
    form = _without_empty({"instance-id": basics.instance_id, "local-hostname": basics.hostname})
    return _merge(form, config.additional.meta_data)


def render_meta_data(config: Configuration) -> str:
    return to_yaml(meta_data(config))


def _merge(form: dict[str, Any], additional: dict[str, Any]) -> dict[str, Any]:
    """FR-014: additional settings are added; for a key in both, the additional value is
    used (conflicts with non-default form values are reported by `checks`)."""
    return form | additional


# --- network-config (FR-006) ---


def _address_settings(settings: AddressSettings) -> dict[str, Any]:
    routes = []
    if settings.gateway4:
        routes.append({"to": "0.0.0.0/0", "via": settings.gateway4})
    if settings.gateway6:
        routes.append({"to": "::/0", "via": settings.gateway6})
    return _without_empty(
        {
            "dhcp4": settings.dhcp4 or None,
            "dhcp6": settings.dhcp6 or None,
            "addresses": settings.addresses,
            "routes": routes,
            "nameservers": _without_empty(
                {"addresses": settings.nameservers, "search": settings.search}
            ),
            "mtu": settings.mtu,
        }
    )


def network_data(
    network: Network, additional: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    additional = additional or {}
    if network.is_empty() and not additional:
        return None
    ethernets = {}
    for nic in network.ethernets:
        entry: dict[str, Any] = {}
        if nic.match_mac:
            entry = {"match": {"macaddress": nic.match_mac}, "set-name": nic.name}
        ethernets[nic.name] = entry | _address_settings(nic)
    bridges = {}
    for bridge in network.bridges:
        parameters = _without_empty({"stp": bridge.stp, "forward-delay": bridge.forward_delay})
        bridges[bridge.name] = _without_empty(
            {"interfaces": bridge.interfaces} | _address_settings(bridge)
            | {"parameters": parameters}
        )  # fmt: skip
    devices = _without_empty({"ethernets": ethernets, "bridges": bridges})
    return {"network": _merge({"version": 2} | devices, additional)}


def render_network_config(config: Configuration) -> str | None:
    data = network_data(config.network, config.additional.network)
    return to_yaml(data) if data else None


# --- user-data ---


def _users_data(users: Users) -> dict[str, Any]:
    entries: list[Any] = ["default"] if users.keep_default_user else []
    for user in users.users:
        entries.append(
            _without_empty(
                {
                    "name": user.name,
                    "gecos": user.gecos,
                    "primary_group": user.primary_group,
                    "groups": user.all_groups(),
                    "sudo": user.sudo,
                    "shell": user.shell,
                    "passwd": user.password_hash,
                    "lock_passwd": False if not user.lock_passwd else None,
                    "ssh_authorized_keys": user.ssh_authorized_keys,
                    "system": user.system or None,
                }
            )
        )
    data: dict[str, Any] = {}
    if users.groups:
        data["groups"] = [
            {group.name: group.members} if group.members else group.name for group in users.groups
        ]
    # Without own users and with the default user kept, cloud-init's default applies.
    if users.users or not users.keep_default_user:
        data["users"] = entries
    return data


def _ssh_data(ssh: Ssh) -> dict[str, Any]:
    data: dict[str, Any] = {
        "ssh_pwauth": ssh.password_authentication,
        "disable_root": ssh.disable_root,
    }
    if not ssh.delete_host_keys:
        data["ssh_deletekeys"] = False
    if sorted(ssh.host_key_types) != sorted(HOST_KEY_TYPES):
        data["ssh_genkeytypes"] = list(ssh.host_key_types)
    if ssh.authorized_keys:
        data["ssh_authorized_keys"] = ssh.authorized_keys
    return data


def _disks_data(disks: list[Disk]) -> dict[str, Any]:
    if not disks:
        return {}
    disk_setup: dict[str, Any] = {}
    fs_setup: list[dict[str, Any]] = []
    mounts: list[list[str]] = []
    for disk in disks:
        disk_setup[disk.device] = {
            "table_type": disk.table_type,
            "layout": [partition.size_percent for partition in disk.partitions],
            "overwrite": disk.overwrite,
        }
        for number, partition in enumerate(disk.partitions, start=1):
            if not partition.filesystem:
                continue
            fs_setup.append(
                _without_empty(
                    {
                        "label": partition.label,
                        "filesystem": partition.filesystem,
                        "device": disk.device,
                        "partition": number,
                        "overwrite": disk.overwrite or None,
                    }
                )
            )
            if partition.mount_point and partition.label:
                mounts.append(
                    [
                        f"LABEL={partition.label}",
                        partition.mount_point,
                        partition.filesystem,
                        partition.mount_options or "defaults",
                        "0",
                        "2",
                    ]
                )
    return _without_empty({"disk_setup": disk_setup, "fs_setup": fs_setup, "mounts": mounts})


def user_data(config: Configuration) -> dict[str, Any]:
    return _merge(form_user_data(config), config.additional.user_data)


def form_user_data(config: Configuration) -> dict[str, Any]:
    """The user-data keys produced by the form sections alone."""
    basics = config.basics
    packages = config.packages
    write_files = [
        _without_empty(
            {
                "path": file.path,
                "owner": file.owner,
                "permissions": file.permissions,
                "encoding": "b64" if file.encoding == "b64" else None,
                "content": file.content,
                "append": file.append or None,
                "defer": file.defer or None,
            }
        )
        for file in config.write_files
    ]
    return (
        _without_empty(
            {
                "fqdn": basics.fqdn,
                # Without an /etc/hosts entry the FQDN does not resolve ('hostname -f');
                # 'localhost' only maintains the 127.0.1.1 line and leaves the rest alone.
                "manage_etc_hosts": "localhost" if basics.fqdn else None,
                "timezone": basics.timezone,
                "locale": basics.locale,
            }
        )
        | _users_data(config.users)
        | _ssh_data(config.ssh)
        | _without_empty(
            {
                "package_update": packages.update or None,
                "package_upgrade": packages.upgrade or None,
                "package_reboot_if_required": packages.reboot_if_required or None,
                "packages": packages.packages,
                "write_files": write_files,
                "bootcmd": config.commands.bootcmd,
                "runcmd": config.commands.runcmd,
            }
        )
        | _disks_data(config.disks)
    )


def render_user_data(config: Configuration) -> str:
    # cloud-init requires a mapping; a bare header is rejected as "not a YAML dict" (FR-001).
    return "#cloud-config\n" + (to_yaml(user_data(config)) or "{}\n")


def render_vendor_data(config: Configuration) -> str | None:
    vendor_data = config.additional.vendor_data
    if vendor_data is None:
        return None
    return "#cloud-config\n" + (to_yaml(vendor_data) or "{}\n")


def render_files(config: Configuration) -> dict[str, str | None]:
    """All NoCloud files; `None` for optional files that have no content."""
    return {
        USER_DATA: render_user_data(config),
        META_DATA: render_meta_data(config),
        NETWORK_CONFIG: render_network_config(config),
        VENDOR_DATA: render_vendor_data(config),
    }
