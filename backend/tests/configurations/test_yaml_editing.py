"""FR-014: editing YAML manually with round trip to the form; NFR-008 schema hints."""

import pytest
import yaml

from app.configurations.model import Configuration
from app.configurations.parsing import parse_file
from app.configurations.rendering import render_files
from app.configurations.yaml_input import YamlInputError, load_yaml
from tests.configurations.conftest import SSH_KEY

HASH = "$6$abcdefgh$" + "a" * 86

FULL = Configuration.model_validate(
    {
        "name": "full",
        "basics": {
            "instance_id": "iid-web-01",
            "hostname": "web-01",
            "fqdn": "web-01.example.com",
            "timezone": "Europe/Berlin",
            "locale": "en_US.UTF-8",
        },
        "network": {
            "ethernets": [
                {"name": "eth0"},
                {"name": "lan1", "match_mac": "52:54:00:12:34:56", "dhcp4": True, "mtu": 1500},
            ],
            "bridges": [
                {
                    "name": "br0",
                    "interfaces": ["eth0"],
                    "addresses": ["192.168.1.10/24", "fd00::10/64"],
                    "gateway4": "192.168.1.1",
                    "gateway6": "fd00::1",
                    "nameservers": ["192.168.1.1"],
                    "search": ["example.com"],
                    "stp": False,
                    "forward_delay": 4,
                }
            ],
        },
        "packages": {"update": True, "upgrade": True, "packages": ["git", "nginx"]},
        "write_files": [
            {
                "path": "/etc/motd",
                "content": "hello\nworld\n",
                "owner": "root:root",
                "permissions": "0644",
            },
            {
                "path": "/opt/blob",
                "content": "AAE=",
                "encoding": "b64",
                "append": True,
                "defer": True,
            },
        ],
        "commands": {"bootcmd": ["echo boot"], "runcmd": [["ls", "-l"], "set -e\necho x\n"]},
        "users": {
            "users": [
                {
                    "name": "alice",
                    "gecos": "Alice",
                    "groups": ["docker"],
                    "admin": True,
                    "sudo": "ALL=(ALL) NOPASSWD:ALL",
                    "password_hash": HASH,
                    "lock_passwd": False,
                    "ssh_authorized_keys": [SSH_KEY],
                },
                {"name": "svc", "system": True, "shell": "/usr/sbin/nologin"},
            ],
            "groups": [{"name": "docker"}, {"name": "dev", "members": ["alice"]}],
        },
        "ssh": {
            "delete_host_keys": False,
            "host_key_types": ["ed25519"],
            "authorized_keys": [SSH_KEY],
        },
        "disks": [
            {
                "device": "/dev/vdb",
                "table_type": "mbr",
                "partitions": [
                    {"size_percent": 60, "label": "data", "mount_point": "/srv/data"},
                    {
                        "size_percent": 40,
                        "filesystem": "xfs",
                        "label": "logs",
                        "mount_point": "/var/log/app",
                    },
                ],
            }
        ],
    }
)


def blank(config: Configuration) -> Configuration:
    """The configuration with only name and instance-id (as if the form was empty)."""
    return Configuration(name=config.name, basics={"instance_id": config.basics.instance_id})


@pytest.mark.parametrize("file_name", ["user-data", "meta-data", "network-config"])
def test_round_trip_is_lossless_and_fills_the_form(file_name):
    """FR-014: every form section survives YAML -> form unchanged (no additional settings)."""
    files = render_files(FULL)
    config = blank(FULL)
    for name in ("user-data", "meta-data", "network-config"):
        config = parse_file(config, name, files[name]).configuration
    assert config == FULL
    assert config.additional.is_empty()
    assert render_files(config) == files


def test_hostname_changed_in_yaml_shows_up_in_the_form():
    """FR-014: a hostname changed in the YAML editor is shown in the form."""
    text = render_files(FULL)["meta-data"].replace("web-01", "web-02")
    result = parse_file(FULL, "meta-data", text)
    assert result.configuration.basics.hostname == "web-02"


def test_unknown_key_is_kept_as_additional_setting():
    """FR-014: a key unknown to the form (ntp) is kept and rendered again."""
    text = render_files(FULL)["user-data"] + "ntp:\n  enabled: true\n  servers: [ntp.example.com]\n"
    config = parse_file(FULL, "user-data", text).configuration
    assert config.additional.user_data == {"ntp": {"enabled": True, "servers": ["ntp.example.com"]}}
    assert config.packages == FULL.packages
    assert yaml.safe_load(render_files(config)["user-data"])["ntp"]["servers"] == [
        "ntp.example.com"
    ]


def test_unsupported_details_keep_the_key_unchanged():
    """FR-014: a known key with settings the form cannot show is kept losslessly as YAML."""
    text = "#cloud-config\nusers:\n- default\n- name: bob\n  homedir: /srv/bob\n"
    result = parse_file(blank(FULL), "user-data", text)
    config = result.configuration
    assert config.users.users == []
    assert config.additional.user_data["users"] == [
        "default",
        {"name": "bob", "homedir": "/srv/bob"},
    ]
    assert "'users' contains settings the form does not support" in result.notices[0]
    assert yaml.safe_load(render_files(config)["user-data"])["users"] == [
        "default",
        {"name": "bob", "homedir": "/srv/bob"},
    ]


def test_syntax_error_has_line_number():
    """FR-014: YAML with a syntax error is rejected with its line number."""
    text = "#cloud-config\npackages:\n  - git\n bad: [unclosed\n"
    with pytest.raises(YamlInputError) as excinfo:
        parse_file(FULL, "user-data", text)
    issue = excinfo.value.issues[0]
    assert issue.msg.startswith("YAML syntax error")
    assert issue.line == 4


def test_invalid_value_is_an_error_with_line_number():
    """FR-014: a value the form rejects is reported at its line."""
    text = "instance-id: iid-1\nlocal-hostname: web_01\n"
    with pytest.raises(YamlInputError) as excinfo:
        parse_file(FULL, "meta-data", text)
    assert excinfo.value.issues[0].line == 2
    assert "host name" in excinfo.value.issues[0].msg


def test_invalid_list_entry_points_to_its_line():
    """FR-014: errors inside lists point to the affected entry."""
    text = "#cloud-config\npackages:\n- git\n- Not Valid\n"
    with pytest.raises(YamlInputError) as excinfo:
        parse_file(FULL, "user-data", text)
    assert excinfo.value.issues[0].line == 4


def test_user_data_needs_the_cloud_config_header():
    """FR-014: user-data must remain a #cloud-config document."""
    with pytest.raises(YamlInputError) as excinfo:
        parse_file(FULL, "user-data", "packages: [git]\n")
    assert excinfo.value.issues[0].line == 1


def test_bonds_and_vlans_are_kept_and_usable_as_bridge_members():
    """FR-006, FR-014: bonds/VLANs are added via YAML and may be bridge members."""
    text = """network:
  version: 2
  ethernets:
    eth0: {}
    eth1: {}
  bonds:
    bond0:
      interfaces: [eth0, eth1]
      parameters: {mode: active-backup}
  bridges:
    br0:
      interfaces: [bond0]
      dhcp4: true
"""
    config = parse_file(blank(FULL), "network-config", text).configuration
    assert [b.name for b in config.network.bridges] == ["br0"]
    assert "bonds" in config.additional.network
    from app.configurations.checks import check

    assert check(config).errors == []
    assert yaml.safe_load(render_files(config)["network-config"]) == yaml.safe_load(text)


def test_netplan_v1_is_kept_as_yaml():
    """FR-014: other network-config versions are kept unchanged."""
    text = "version: 1\nconfig:\n- type: physical\n  name: eth0\n  subnets: [{type: dhcp}]\n"
    result = parse_file(blank(FULL), "network-config", text)
    assert result.configuration.network.is_empty()
    assert result.notices
    assert yaml.safe_load(render_files(result.configuration)["network-config"])["network"] == (
        yaml.safe_load(text)
    )


def test_vendor_data_round_trip():
    """FR-001, FR-014: vendor-data can be added as YAML and removed again."""
    config = parse_file(blank(FULL), "vendor-data", "#cloud-config\nruncmd: [true]\n").configuration
    assert render_files(config)["vendor-data"] == "#cloud-config\nruncmd:\n- true\n"
    config = parse_file(config, "vendor-data", "").configuration
    assert render_files(config)["vendor-data"] is None


def test_alias_bomb_is_rejected():
    """FR-014: alias expansion attacks are rejected before objects are built."""
    lines = ["a: &a [x, x, x, x, x, x, x, x, x, x]"]
    for i in range(1, 9):
        lines.append(f"{chr(97 + i)}: &{chr(97 + i)} [{', '.join([f'*{chr(96 + i)}'] * 10)}]")
    with pytest.raises(YamlInputError) as excinfo:
        load_yaml("\n".join(lines))
    assert "too many nodes" in excinfo.value.issues[0].msg


def test_dates_are_stored_as_strings():
    """FR-014: YAML-specific types are stored as JSON-compatible values."""
    config = parse_file(
        blank(FULL), "user-data", "#cloud-config\nmy_date: 2026-10-15\n"
    ).configuration
    assert config.additional.user_data == {"my_date": "2026-10-15"}


# --- via the API ---


def test_parse_endpoint(client):
    """FR-014: the parse endpoint applies YAML to the posted form state without saving."""
    form = {"name": "x", "basics": {"instance_id": "iid-1", "hostname": "a"}}
    response = client.post(
        "/api/parse",
        json={
            "configuration": form,
            "file": "meta-data",
            "content": "instance-id: iid-1\nlocal-hostname: b\n",
        },
    )
    assert response.status_code == 200
    assert response.json()["configuration"]["basics"]["hostname"] == "b"
    assert client.get("/api/configurations").json() == []


def test_parse_endpoint_returns_line_numbers(client):
    """FR-014: syntax errors are returned with their line number."""
    response = client.post(
        "/api/parse",
        json={
            "configuration": {"name": "x"},
            "file": "user-data",
            "content": "#cloud-config\na: [\n",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["line"] == 3


def test_added_key_survives_save_and_reload(client):
    """FR-014: an added unknown key (ntp) is still present after saving and reloading."""
    form = {"name": "ntp", "basics": {"instance_id": "iid-1"}}
    content = "#cloud-config\nntp:\n  enabled: true\n"
    parsed = client.post(
        "/api/parse", json={"configuration": form, "file": "user-data", "content": content}
    ).json()["configuration"]
    created = client.post("/api/configurations", json=parsed).json()
    reloaded = client.get(f"/api/configurations/{created['id']}").json()
    files = client.get(f"/api/configurations/{created['id']}/files").json()
    assert reloaded["additional"]["user_data"] == {"ntp": {"enabled": True}}
    assert "ntp:\n  enabled: true" in files["user-data"]


def test_schema_violation_is_a_hint_and_saving_is_allowed(client):
    """FR-014, NFR-008: a schema violation gives a located hint; saving is still possible."""
    body = {
        "name": "schema",
        "basics": {"instance_id": "iid-1"},
        "additional": {"user_data": {"ntp": {"enabled": "yes please"}}},
    }
    preview = client.post("/api/preview", json=body).json()
    [issue] = preview["schema_issues"]
    assert issue["file"] == "user-data"
    assert issue["path"] == ["ntp", "enabled"]
    assert issue["line"] == 5
    assert client.post("/api/configurations", json=body).status_code == 201


def test_generated_configuration_has_no_schema_issues(client):
    """NFR-008: everything the form generates matches the cloud-init schema."""
    body = FULL.model_dump(mode="json")
    assert client.post("/api/preview", json=body).json()["schema_issues"] == []


def test_plain_text_password_in_yaml_is_a_warning(client):
    """FR-014, NFR-007: plain-text passwords in YAML give a warning."""
    for additional in (
        {"chpasswd": {"users": [{"name": "root", "password": "secret", "type": "text"}]}},
        {"chpasswd": {"list": "root:secret"}},
        {"users": ["default", {"name": "bob", "plain_text_passwd": "secret"}]},
        {"password": "secret"},
    ):
        body = {
            "name": "pw",
            "basics": {"instance_id": "iid-1"},
            "additional": {"user_data": additional},
        }
        warnings = client.post("/api/preview", json=body).json()["warnings"]
        key = next(iter(additional))
        [warning] = [w for w in warnings if w["loc"] == ["additional", "user_data", key]]
        assert "plain-text password" in warning["msg"], additional


def test_hashed_chpasswd_is_fine(client):
    """FR-014: hashed passwords in chpasswd give no warning."""
    additional = {"chpasswd": {"users": [{"name": "root", "password": HASH}]}}
    body = {
        "name": "pw",
        "basics": {"instance_id": "iid-1"},
        "additional": {"user_data": additional},
    }
    warnings = client.post("/api/preview", json=body).json()["warnings"]
    assert not [w for w in warnings if w["loc"][0] == "additional"]


def test_key_in_form_and_additional_settings_is_an_error(client):
    """FR-014: a key cannot be set in the form and as additional setting at the same time."""
    body = {
        "name": "conflict",
        "packages": {"packages": ["git"]},
        "additional": {"user_data": {"packages": ["vim"]}},
    }
    response = client.post("/api/configurations", json=body)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "additional", "user_data", "packages"]
