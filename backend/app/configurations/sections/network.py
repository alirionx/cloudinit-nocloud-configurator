"""FR-006: network configuration (Netplan version 2) with NICs and bridges."""

import ipaddress
from typing import Annotated

from pydantic import AfterValidator, Field

from app.configurations.sections.common import LABEL, EmptyAsNone, Section, UniqueList, matches


def _interface(value: str) -> str:
    try:
        interface = ipaddress.ip_interface(value)
    except ValueError:
        raise ValueError(
            "must be an IP address with prefix length (CIDR), e.g. '192.168.1.10/24'"
        ) from None
    if "/" not in value:
        raise ValueError(f"needs a prefix length, e.g. '{value}/24'")
    return interface.with_prefixlen


def _ip(value: str) -> str:
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        raise ValueError("must be an IPv4 or IPv6 address") from None


def _ipv4(value: str) -> str:
    try:
        return str(ipaddress.IPv4Address(value))
    except ValueError:
        raise ValueError("must be an IPv4 address, e.g. '192.168.1.1'") from None


def _ipv6(value: str) -> str:
    try:
        return str(ipaddress.IPv6Address(value))
    except ValueError:
        raise ValueError("must be an IPv6 address, e.g. 'fd00::1'") from None


def _mac(value: str) -> str:
    return value.lower()


IpInterface = Annotated[str, AfterValidator(_interface)]
IpAddress = Annotated[str, AfterValidator(_ip)]
Ipv4Address = Annotated[str, AfterValidator(_ipv4)]
Ipv6Address = Annotated[str, AfterValidator(_ipv6)]
MacAddress = Annotated[
    str,
    matches(
        r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", "must be a MAC address like 52:54:00:12:34:56"
    ),
    AfterValidator(_mac),
]
# Linux interface names: max. 15 characters, no slash or whitespace.
InterfaceName = Annotated[
    str,
    matches(
        r"[A-Za-z0-9_.:-]{1,15}",
        "must be an interface name like 'eth0' or 'br0' (max. 15 characters, no spaces)",
    ),
]
SearchDomain = Annotated[
    str, matches(rf"{LABEL}(?:\.{LABEL})*", "must be a domain name like 'example.com'")
]


class AddressSettings(Section):
    """Address settings shared by NICs and bridges."""

    dhcp4: bool = False
    dhcp6: bool = False
    addresses: UniqueList[IpInterface] = Field(
        default_factory=list, description="Static addresses in CIDR notation."
    )
    gateway4: EmptyAsNone[Ipv4Address] = None
    gateway6: EmptyAsNone[Ipv6Address] = None
    nameservers: UniqueList[IpAddress] = Field(default_factory=list)
    search: UniqueList[SearchDomain] = Field(default_factory=list)
    mtu: EmptyAsNone[Annotated[int, Field(ge=576, le=9216)]] = None

    def has_address_settings(self) -> bool:
        return bool(self.dhcp4 or self.dhcp6 or self.addresses or self.gateway4 or self.gateway6)


class Ethernet(AddressSettings):
    """A network interface card, matched by name or by MAC address."""

    name: InterfaceName = Field(description="Interface name, e.g. 'eth0' or 'ens3'.")
    match_mac: EmptyAsNone[MacAddress] = Field(
        default=None,
        description="Match the NIC by MAC address and rename it to `name` (set-name).",
    )


class Bridge(AddressSettings):
    name: InterfaceName = Field(description="Bridge name, e.g. 'br0'.")
    interfaces: UniqueList[InterfaceName] = Field(
        default_factory=list, description="Member NICs (names of defined NICs)."
    )
    stp: bool | None = Field(default=None, description="Spanning tree protocol; unset = default.")
    forward_delay: EmptyAsNone[Annotated[int, Field(ge=0, le=30)]] = Field(
        default=None, description="Forward delay in seconds."
    )


class Network(Section):
    ethernets: list[Ethernet] = Field(default_factory=list)
    bridges: list[Bridge] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.ethernets and not self.bridges
