"""Which YAML keys belong to which form section (FR-004, FR-014)."""

# user-data keys produced by each form section.
USER_DATA_KEYS: dict[str, tuple[str, ...]] = {
    "basics": ("fqdn", "manage_etc_hosts", "timezone", "locale"),
    "users": ("users", "groups"),
    "ssh": (
        "ssh_pwauth",
        "disable_root",
        "ssh_deletekeys",
        "ssh_genkeytypes",
        "ssh_authorized_keys",
    ),
    "packages": ("package_update", "package_upgrade", "package_reboot_if_required", "packages"),
    "write_files": ("write_files",),
    "commands": ("bootcmd", "runcmd"),
    "disks": ("disk_setup", "fs_setup", "mounts"),
}
KNOWN_USER_DATA_KEYS = frozenset(key for keys in USER_DATA_KEYS.values() for key in keys)
SECTION_OF_KEY = {key: section for section, keys in USER_DATA_KEYS.items() for key in keys}

# meta-data keys and their form fields.
META_DATA_FIELDS = {"instance-id": "instance_id", "local-hostname": "hostname"}

# Netplan v2 keys handled by the network section.
NETWORK_KEYS = ("version", "ethernets", "bridges")
