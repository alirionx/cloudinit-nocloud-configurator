import yaml

from app.configurations.model import Basics, Configuration
from app.configurations.rendering import render_files, to_yaml

SECURE_SSH = {"ssh_pwauth": False, "disable_root": True}

FULL = Configuration(
    name="Web server",
    basics=Basics(
        instance_id="iid-web-01-12345678",
        hostname="web-01",
        fqdn="web-01.example.com",
        timezone="Europe/Berlin",
        locale="de_DE.UTF-8",
    ),
)


def test_meta_data_contains_instance_id_and_hostname():
    """FR-001, FR-005: meta-data is valid YAML with instance-id and local-hostname."""
    meta_data = render_files(FULL)["meta-data"]
    assert yaml.safe_load(meta_data) == {
        "instance-id": "iid-web-01-12345678",
        "local-hostname": "web-01",
    }


def test_user_data_is_cloud_config_with_basics():
    """FR-001, FR-005: user-data starts with #cloud-config and holds fqdn, timezone, locale."""
    user_data = render_files(FULL)["user-data"]
    assert user_data.startswith("#cloud-config\n")
    assert yaml.safe_load(user_data) == {
        "fqdn": "web-01.example.com",
        "manage_etc_hosts": "localhost",
        "timezone": "Europe/Berlin",
        "locale": "de_DE.UTF-8",
        **SECURE_SSH,
    }


def test_exact_output():
    """FR-001: the rendered files have a stable, readable layout."""
    files = render_files(FULL)
    assert files["meta-data"] == "instance-id: iid-web-01-12345678\nlocal-hostname: web-01\n"
    assert files["user-data"] == (
        "#cloud-config\n"
        "fqdn: web-01.example.com\n"
        "manage_etc_hosts: localhost\n"
        "timezone: Europe/Berlin\n"
        "locale: de_DE.UTF-8\n"
        "ssh_pwauth: false\n"
        "disable_root: true\n"
    )


def test_empty_section_produces_no_keys():
    """FR-004: given empty sections, the YAML contains no keys for them.

    Only the SSH security settings are always written (FR-011 secure defaults).
    """
    files = render_files(Configuration(name="empty", basics=Basics(instance_id="iid-1")))
    assert yaml.safe_load(files["user-data"]) == SECURE_SSH
    assert yaml.safe_load(files["meta-data"]) == {"instance-id": "iid-1"}


def test_optional_files_are_absent():
    """FR-006: without a network section, no network-config is generated."""
    files = render_files(FULL)
    assert files["network-config"] is None
    assert files["vendor-data"] is None


def test_rendering_is_deterministic():
    """FR-004: the same model always produces identical YAML."""
    copy = Configuration.model_validate(FULL.model_dump(mode="json"))
    assert render_files(copy) == render_files(FULL)


def test_multiline_strings_are_block_literals():
    """FR-009: multi-line values are preserved as block literals."""
    text = to_yaml({"runcmd": ["echo one\necho two\n"]})
    assert "|" in text
    assert yaml.safe_load(text) == {"runcmd": ["echo one\necho two\n"]}


def test_ambiguous_strings_stay_strings():
    """FR-004: strings that look like other YAML types are quoted."""
    data = {"a": "yes", "b": "0644", "c": "null", "d": "1.0", "e": "äöü"}
    assert yaml.safe_load(to_yaml(data)) == data


def test_fqdn_is_added_to_etc_hosts():
    """FR-005: with an FQDN, cloud-init maintains the 127.0.1.1 line in /etc/hosts so that
    the FQDN resolves (verified by booting Debian 13); without FQDN /etc/hosts is untouched."""
    with_fqdn = yaml.safe_load(render_files(FULL)["user-data"])
    assert with_fqdn["manage_etc_hosts"] == "localhost"
    without = Configuration(name="x", basics=Basics(instance_id="iid-1", hostname="web-01"))
    assert "manage_etc_hosts" not in yaml.safe_load(render_files(without)["user-data"])
