"""FR-007 to FR-012: rendering, validation and checks of the form sections."""

import base64

import pytest

from app.configurations.rendering import render_files
from tests.configurations.conftest import SSH_KEY
from tests.configurations.helpers import checked, config, field_error, locs, user_data

# --- FR-007: packages ---


def test_packages_and_toggles():
    """FR-007: enabled toggles and a package list are rendered with exactly these values."""
    cfg = config(
        packages={
            "update": True,
            "upgrade": True,
            "reboot_if_required": True,
            "packages": ["git", "wget", "docker.io"],
        }
    )
    data = user_data(cfg)
    assert data["package_update"] is True
    assert data["package_upgrade"] is True
    assert data["package_reboot_if_required"] is True
    assert data["packages"] == ["git", "wget", "docker.io"]


def test_disabled_toggles_produce_no_keys():
    """FR-004, FR-007: an empty packages section produces no keys."""
    data = user_data(config(packages={}))
    assert not {"package_update", "package_upgrade", "packages"} & set(data)


def test_duplicate_packages_are_removed():
    """FR-007: a package already in the list is not added twice."""
    cfg = config(packages={"packages": ["git", "wget", "git", " wget ", ""]})
    assert cfg.packages.packages == ["git", "wget"]


@pytest.mark.parametrize("name", ["Git", "my package", "-x", "a", "pkg;rm"])
def test_invalid_package_names(name):
    """FR-007: package names follow Debian rules."""
    assert field_error(packages={"packages": [name]})[0][:2] == ("packages", "packages")


def test_version_pins_are_allowed():
    """FR-007: apt-style version pins are accepted."""
    assert config(packages={"packages": ["nginx=1.24.0-1"]}).packages.packages == ["nginx=1.24.0-1"]


# --- FR-008: write_files ---


def test_write_files_rendering():
    """FR-008: path, content, owner, permissions, append and defer."""
    cfg = config(
        write_files=[
            {
                "path": "/etc/motd",
                "content": "Hello\nWorld\n",
                "owner": "root:root",
                "permissions": "644",
                "append": True,
                "defer": True,
            }
        ]
    )
    [entry] = user_data(cfg)["write_files"]
    assert entry == {
        "path": "/etc/motd",
        "owner": "root:root",
        "permissions": "0644",
        "content": "Hello\nWorld\n",
        "append": True,
        "defer": True,
    }
    assert "content: |" in render_files(cfg)["user-data"]


def test_relative_path_is_an_error():
    """FR-008: a relative target path is marked as an error."""
    assert field_error(write_files=[{"path": "etc/motd"}])[0] == ("write_files", 0, "path")


def test_binary_file_is_base64_encoded():
    """FR-008: an uploaded binary file is included Base64-encoded with encoding: b64."""
    content = base64.b64encode(bytes(range(256))).decode()
    cfg = config(write_files=[{"path": "/opt/blob.bin", "content": content, "encoding": "b64"}])
    [entry] = user_data(cfg)["write_files"]
    assert entry["encoding"] == "b64"
    assert base64.b64decode(entry["content"]) == bytes(range(256))


def test_invalid_base64_is_an_error():
    """FR-008: content marked as Base64 must decode."""
    assert field_error(write_files=[{"path": "/x", "content": "not base64!", "encoding": "b64"}])


def test_defer_is_suggested_for_files_owned_by_created_users():
    """FR-008: a file owned by a user created via FR-010 gets the hint to enable defer."""
    sections = {
        "users": {"users": [{"name": "app"}]},
        "write_files": [{"path": "/home/app/.env", "owner": "app:app"}],
    }
    result = checked(**sections)
    assert ["write_files", 0, "defer"] in locs(result.warnings)
    sections["write_files"][0]["defer"] = True
    assert ["write_files", 0, "defer"] not in locs(checked(**sections).warnings)


def test_duplicate_path_without_append_is_a_warning():
    """FR-008: two files with the same target path without append give a warning."""
    files = [{"path": "/etc/motd", "content": "a"}, {"path": "/etc/motd", "content": "b"}]
    assert locs(checked(write_files=files).warnings) == [["write_files", 1, "path"]] + [
        ["ssh", "password_authentication"]
    ]
    files[1]["append"] = True
    assert ["write_files", 1, "path"] not in locs(checked(write_files=files).warnings)


@pytest.mark.parametrize(("field", "value"), [("permissions", "999"), ("owner", "Root User")])
def test_invalid_owner_and_permissions(field, value):
    """FR-008: owner and permissions are validated."""
    assert field_error(write_files=[{"path": "/x", field: value}])[0] == ("write_files", 0, field)


def test_file_content_keeps_whitespace():
    """FR-008: file content is stored exactly (no trimming)."""
    cfg = config(write_files=[{"path": "/x", "content": "  indented\n\n"}])
    assert cfg.write_files[0].content == "  indented\n\n"


# --- FR-009: bootcmd / runcmd ---


def test_runcmd_order_is_preserved():
    """FR-009: runcmd entries appear in the YAML in exactly the given order."""
    commands = ["echo three", "echo one", ["systemctl", "enable", "--now", "nginx"]]
    assert user_data(config(commands={"runcmd": commands}))["runcmd"] == commands


def test_multiline_command_is_a_block_literal():
    """FR-009: a multi-line entry is preserved as a block literal."""
    script = "set -e\nif true; then\n  echo ok\nfi\n"
    cfg = config(commands={"bootcmd": [script]})
    assert user_data(cfg)["bootcmd"] == [script]
    assert "- |" in render_files(cfg)["user-data"]


@pytest.mark.parametrize("command", ["", "   ", []])
def test_empty_commands_are_errors(command):
    """FR-009: empty entries are rejected."""
    assert field_error(commands={"runcmd": [command]})[0][:3] == ("commands", "runcmd", 0)


# --- FR-010: users and groups ---


def test_user_rendering():
    """FR-010: user fields are rendered as cloud-init users entries."""
    cfg = config(
        users={
            "users": [
                {
                    "name": "admin",
                    "gecos": "Admin User",
                    "groups": ["docker"],
                    "admin": True,
                    "sudo": "ALL=(ALL) NOPASSWD:ALL",
                    "ssh_authorized_keys": [SSH_KEY],
                    "lock_passwd": False,
                }
            ],
            "groups": [{"name": "docker"}, {"name": "dev", "members": ["admin"]}],
        }
    )
    data = user_data(cfg)
    assert data["users"] == [
        "default",
        {
            "name": "admin",
            "gecos": "Admin User",
            "groups": ["docker", "sudo"],
            "sudo": "ALL=(ALL) NOPASSWD:ALL",
            "shell": "/bin/bash",
            "lock_passwd": False,
            "ssh_authorized_keys": [SSH_KEY],
        },
    ]
    assert data["groups"] == ["docker", {"dev": ["admin"]}]


def test_admin_uses_debian_sudo_group():
    """FR-010: marking a user as administrator adds the Debian group sudo (not wheel)."""
    data = user_data(config(users={"users": [{"name": "ops", "admin": True}]}))
    assert data["users"][1]["groups"] == ["sudo"]
    assert "wheel" not in str(data)


def test_default_user_handling():
    """FR-010: the distribution's default user is kept by default and can be dropped."""
    assert "users" not in user_data(config())
    assert user_data(config(users={"keep_default_user": False}))["users"] == []
    data = user_data(config(users={"keep_default_user": False, "users": [{"name": "ops"}]}))
    assert data["users"] == [{"name": "ops", "shell": "/bin/bash"}]


def test_invalid_ssh_key_is_an_error():
    """FR-010: an invalid SSH public key is marked as an error."""
    bad_keys = [
        "ssh-ed25519 notbase64!",
        "ssh-rsa AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl",
        "hello world",
    ]
    for key in bad_keys:
        loc = field_error(users={"users": [{"name": "a", "ssh_authorized_keys": [key]}]})
        assert loc[0][:5] == ("users", "users", 0, "ssh_authorized_keys", 0)


def test_valid_ssh_key_is_normalized():
    """FR-010: surrounding and repeated whitespace in keys is normalized."""
    cfg = config(ssh={"authorized_keys": ["  " + SSH_KEY.replace(" ", "   ") + "  "]})
    assert cfg.ssh.authorized_keys == [SSH_KEY]


def test_invalid_password_hash_is_an_error():
    """FR-010: a directly entered hash in an invalid format is an error."""
    for value in ["secret", "$1$abc$def", "$6$salt$tooshort"]:
        loc = field_error(users={"users": [{"name": "a", "password_hash": value}]})
        assert loc[0] == ("users", "users", 0, "password_hash")


def test_precomputed_hash_is_accepted():
    """FR-010: a hash from mkpasswd -m sha-512 is accepted as is."""
    hashed = "$6$Fx7FcMLz3Ag/s4lb$" + "a" * 86
    data = user_data(config(users={"users": [{"name": "a", "password_hash": hashed}]}))
    assert data["users"][1]["passwd"] == hashed


def test_unknown_group_is_a_warning():
    """FR-010: a user in a group that does not exist and is not a standard group gets a warning."""
    result = checked(users={"users": [{"name": "a", "groups": ["docker", "sudo", "adm"]}]})
    assert ["users", "users", 0, "groups"] in locs(result.warnings)
    assert "'docker'" in next(w.msg for w in result.warnings if w.loc[1] == "users")
    result = checked(
        users={"users": [{"name": "a", "groups": ["docker"]}], "groups": [{"name": "docker"}]}
    )
    assert ["users", "users", 0, "groups"] not in locs(result.warnings)


def test_duplicate_users_are_errors():
    """FR-010: user names are unique."""
    result = checked(users={"users": [{"name": "a"}, {"name": "a"}]})
    assert locs(result.errors) == [["users", "users", 0, "name"], ["users", "users", 1, "name"]]


# --- FR-011: SSH ---


def test_secure_ssh_defaults():
    """FR-011: without changes, password login and root login are disabled."""
    data = user_data(config())
    assert data["ssh_pwauth"] is False
    assert data["disable_root"] is True
    assert "ssh_deletekeys" not in data
    assert "ssh_genkeytypes" not in data


def test_ssh_settings_rendering():
    """FR-011: all SSH settings are rendered."""
    cfg = config(
        ssh={
            "password_authentication": True,
            "disable_root": False,
            "delete_host_keys": False,
            "host_key_types": ["ed25519"],
            "authorized_keys": [SSH_KEY],
        }
    )
    data = user_data(cfg)
    assert data["ssh_pwauth"] is True
    assert data["disable_root"] is False
    assert data["ssh_deletekeys"] is False
    assert data["ssh_genkeytypes"] == ["ed25519"]
    assert data["ssh_authorized_keys"] == [SSH_KEY]


def test_warning_when_vm_is_not_reachable_via_ssh():
    """FR-011: password login disabled and no SSH key -> warning."""
    assert ["ssh", "password_authentication"] in locs(checked().warnings)
    assert ["ssh", "password_authentication"] not in locs(
        checked(ssh={"authorized_keys": [SSH_KEY]}).warnings
    )
    assert ["ssh", "password_authentication"] not in locs(
        checked(users={"users": [{"name": "a", "ssh_authorized_keys": [SSH_KEY]}]}).warnings
    )
    assert ["ssh", "password_authentication"] not in locs(
        checked(ssh={"password_authentication": True}).warnings
    )


def test_no_host_key_type_is_an_error():
    """FR-011: at least one host key type is generated."""
    assert locs(checked(ssh={"host_key_types": []}).errors) == [["ssh", "host_key_types"]]


# --- FR-012: disks ---

DATA_DISK = {
    "device": "/dev/vdb",
    "partitions": [
        {"size_percent": 70, "filesystem": "ext4", "label": "data", "mount_point": "/srv/data"},
        {"size_percent": 30, "filesystem": "xfs", "label": "logs", "mount_point": "/var/log/app"},
    ],
}


def test_disk_setup_fs_setup_and_mounts_are_consistent():
    """FR-012: disk_setup, fs_setup and mounts are filled consistently."""
    data = user_data(config(disks=[DATA_DISK]))
    assert data["disk_setup"] == {
        "/dev/vdb": {"table_type": "gpt", "layout": [70, 30], "overwrite": False}
    }
    assert data["fs_setup"] == [
        {"label": "data", "filesystem": "ext4", "device": "/dev/vdb", "partition": 1},
        {"label": "logs", "filesystem": "xfs", "device": "/dev/vdb", "partition": 2},
    ]
    assert data["mounts"] == [
        ["LABEL=data", "/srv/data", "ext4", "defaults,nofail", "0", "2"],
        ["LABEL=logs", "/var/log/app", "xfs", "defaults,nofail", "0", "2"],
    ]


def test_overwrite_defaults_to_false_and_warns_when_enabled():
    """FR-012: default is overwrite: false; enabling it gives a data-loss warning."""
    assert config(disks=[DATA_DISK]).disks[0].overwrite is False
    disk = {**DATA_DISK, "overwrite": True}
    data = user_data(config(disks=[disk]))
    assert data["disk_setup"]["/dev/vdb"]["overwrite"] is True
    assert all(fs["overwrite"] is True for fs in data["fs_setup"])
    assert ["disks", 0, "overwrite"] in locs(checked(disks=[disk]).warnings)


def test_mount_point_used_twice_is_an_error():
    """FR-012: a mount point used twice is an error."""
    second = {
        "device": "/dev/vdc",
        "partitions": [{"filesystem": "ext4", "label": "more", "mount_point": "/srv/data"}],
    }
    errors = locs(checked(disks=[DATA_DISK, second]).errors)
    assert ["disks", 0, "partitions", 0, "mount_point"] in errors
    assert ["disks", 1, "partitions", 0, "mount_point"] in errors


@pytest.mark.parametrize(
    ("partitions", "loc"),
    [
        ([{"size_percent": 80}, {"size_percent": 30}], ["disks", 0, "partitions"]),
        ([{"filesystem": "ext4", "mount_point": "/srv"}], ["disks", 0, "partitions", 0, "label"]),
        (
            [{"filesystem": None, "label": "x", "mount_point": "/srv"}],
            ["disks", 0, "partitions", 0, "mount_point"],
        ),
        ([{"filesystem": "xfs", "label": "x" * 13}], ["disks", 0, "partitions", 0, "label"]),
    ],
)
def test_disk_errors(partitions, loc):
    """FR-012: inconsistent partitioning is reported at the affected field."""
    assert loc in locs(checked(disks=[{"device": "/dev/vdb", "partitions": partitions}]).errors)


@pytest.mark.parametrize("device", ["vdb", "/dev/vd b", "/etc/passwd"])
def test_invalid_device(device):
    """FR-012: devices are /dev paths."""
    assert field_error(disks=[{"device": device}])[0] == ("disks", 0, "device")


def test_partition_without_filesystem_is_not_formatted():
    """FR-012: a partition without filesystem is created but not formatted or mounted."""
    data = user_data(config(disks=[{"device": "/dev/vdb", "partitions": [{"filesystem": None}]}]))
    assert data["disk_setup"]["/dev/vdb"]["layout"] == [100]
    assert "fs_setup" not in data
    assert "mounts" not in data
