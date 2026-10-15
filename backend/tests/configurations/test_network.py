"""FR-006: network configuration (Netplan v2)."""

import pytest

from tests.configurations.helpers import checked, config, field_error, locs, network_config


def test_static_interface_renders_exact_netplan():
    """FR-006: static IP, gateway and DNS produce a Netplan v2 entry with exactly these values."""
    cfg = config(
        network={
            "ethernets": [
                {
                    "name": "eth0",
                    "addresses": ["192.168.1.10/24"],
                    "gateway4": "192.168.1.1",
                    "nameservers": ["192.168.1.1", "9.9.9.9"],
                    "search": ["example.com"],
                }
            ]
        }
    )
    assert network_config(cfg) == {
        "network": {
            "version": 2,
            "ethernets": {
                "eth0": {
                    "addresses": ["192.168.1.10/24"],
                    "routes": [{"to": "0.0.0.0/0", "via": "192.168.1.1"}],
                    "nameservers": {
                        "addresses": ["192.168.1.1", "9.9.9.9"],
                        "search": ["example.com"],
                    },
                }
            },
        }
    }


def test_no_network_section_means_no_network_config():
    """FR-006: without a network section, no network-config is generated."""
    assert network_config(config()) is None


def test_dhcp_and_static_address_at_the_same_time():
    """FR-006: DHCP and a static address together are allowed; both are set."""
    cfg = config(
        network={"ethernets": [{"name": "eth0", "dhcp4": True, "addresses": ["10.0.0.5/8"]}]}
    )
    assert checked(network=cfg.network.model_dump()).errors == []
    eth0 = network_config(cfg)["network"]["ethernets"]["eth0"]
    assert eth0["dhcp4"] is True
    assert eth0["addresses"] == ["10.0.0.5/8"]


def test_ipv6_and_mtu():
    """FR-006: IPv6 addresses, IPv6 gateway, DHCPv6 and MTU."""
    cfg = config(
        network={
            "ethernets": [
                {
                    "name": "ens3",
                    "dhcp6": True,
                    "addresses": ["fd00::10/64"],
                    "gateway6": "fd00::1",
                    "mtu": 9000,
                }
            ]
        }
    )
    ens3 = network_config(cfg)["network"]["ethernets"]["ens3"]
    assert ens3 == {
        "dhcp6": True,
        "addresses": ["fd00::10/64"],
        "routes": [{"to": "::/0", "via": "fd00::1"}],
        "mtu": 9000,
    }


def test_match_by_mac_address():
    """FR-006: matching by MAC address renders match.macaddress and set-name."""
    cfg = config(
        network={"ethernets": [{"name": "lan0", "match_mac": "52:54:00:AB:CD:EF", "dhcp4": True}]}
    )
    assert network_config(cfg)["network"]["ethernets"]["lan0"] == {
        "match": {"macaddress": "52:54:00:ab:cd:ef"},
        "set-name": "lan0",
        "dhcp4": True,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("addresses", ["192.168.1.300/24"]),
        ("addresses", ["192.168.1.10"]),
        ("gateway4", "fd00::1"),
        ("gateway6", "10.0.0.1"),
        ("nameservers", ["dns.example.com"]),
        ("match_mac", "52:54:00:12:34"),
        ("mtu", 100),
    ],
)
def test_invalid_values_are_errors(field, value):
    """FR-006: an invalid IP address (or similar) is marked as an error."""
    loc = field_error(network={"ethernets": [{"name": "eth0", field: value}]})
    assert loc[0][:4] == ("network", "ethernets", 0, field)


def test_gateway_outside_subnet_is_a_warning():
    """FR-006: a gateway outside the subnet is shown as a warning."""
    result = checked(
        network={
            "ethernets": [
                {"name": "eth0", "addresses": ["192.168.1.10/24"], "gateway4": "10.0.0.1"}
            ]
        }
    )
    assert result.errors == []
    warnings = [w for w in result.warnings if w.loc[0] == "network"]
    assert locs(warnings) == [["network", "ethernets", 0, "gateway4"]]
    assert "outside the configured subnet (192.168.1.0/24)" in warnings[0].msg


def test_gateway_inside_subnet_is_fine():
    """FR-006: a gateway inside the subnet gives no warning."""
    result = checked(
        network={
            "ethernets": [
                {"name": "eth0", "addresses": ["192.168.1.10/24"], "gateway4": "192.168.1.1"}
            ]
        }
    )
    assert [w for w in result.warnings if w.loc[0] == "network"] == []


BRIDGE = {
    "ethernets": [{"name": "eth0"}],
    "bridges": [
        {
            "name": "br0",
            "interfaces": ["eth0"],
            "addresses": ["192.168.1.10/24"],
            "gateway4": "192.168.1.1",
            "stp": False,
            "forward_delay": 4,
        }
    ],
}


def test_bridge_renders_member_without_address():
    """FR-006: eth0 under ethernets without address, br0 with interfaces [eth0] and the IP."""
    cfg = config(network=BRIDGE)
    assert checked(network=BRIDGE).errors == []
    network = network_config(cfg)["network"]
    assert network["ethernets"] == {"eth0": {}}
    assert network["bridges"]["br0"] == {
        "interfaces": ["eth0"],
        "addresses": ["192.168.1.10/24"],
        "routes": [{"to": "0.0.0.0/0", "via": "192.168.1.1"}],
        "parameters": {"stp": False, "forward-delay": 4},
    }


@pytest.mark.parametrize(
    "own",
    [{"addresses": ["192.168.1.20/24"]}, {"dhcp4": True}, {"gateway4": "192.168.1.1"}],
)
def test_bridge_member_with_own_address_is_an_error(own):
    """FR-006: a NIC that is a bridge member and has an address of its own is an error."""
    network = {**BRIDGE, "ethernets": [{"name": "eth0", **own}]}
    result = checked(network=network)
    assert locs(result.errors) == [["network", "ethernets", 0, "addresses"]]
    assert "member of bridge 'br0'" in result.errors[0].msg


def test_bridge_referencing_undefined_nic_is_an_error():
    """FR-006: a bridge referencing an undefined NIC is an error."""
    network = {**BRIDGE, "bridges": [{"name": "br0", "interfaces": ["eth9"], "dhcp4": True}]}
    result = checked(network=network)
    assert locs(result.errors) == [["network", "bridges", 0, "interfaces"]]
    assert "'eth9' is not a defined NIC" in result.errors[0].msg


def test_nic_in_two_bridges_is_an_error():
    """FR-006: a NIC can be a member of one bridge only."""
    network = {
        "ethernets": [{"name": "eth0"}],
        "bridges": [
            {"name": "br0", "interfaces": ["eth0"]},
            {"name": "br1", "interfaces": ["eth0"]},
        ],
    }
    assert locs(checked(network=network).errors) == [["network", "bridges", 1, "interfaces"]]


def test_duplicate_interface_names_are_errors():
    """FR-006: interface names must be unique across NICs and bridges."""
    network = {"ethernets": [{"name": "eth0"}, {"name": "eth0"}], "bridges": [{"name": "eth0"}]}
    errors = locs(checked(network=network).errors)
    assert ["network", "ethernets", 0, "name"] in errors
    assert ["network", "ethernets", 1, "name"] in errors


def test_dhcp_bridge_with_stp_default():
    """FR-006: STP and forward delay are optional."""
    network = {
        "ethernets": [{"name": "eth0"}],
        "bridges": [{"name": "br0", "interfaces": ["eth0"], "dhcp4": True}],
    }
    bridge = network_config(config(network=network))["network"]["bridges"]["br0"]
    assert bridge == {"interfaces": ["eth0"], "dhcp4": True}
