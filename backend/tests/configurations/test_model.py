import re

import pytest
from pydantic import ValidationError

from app.configurations.model import Basics, Configuration, suggest_instance_id


@pytest.mark.parametrize("hostname", ["web-01", "a", "WEB01", "x" * 63, "1host", "db-2-replica"])
def test_valid_hostnames(hostname):
    """FR-005: RFC 1123 hostnames are accepted."""
    assert Basics(hostname=hostname).hostname == hostname


@pytest.mark.parametrize(
    "hostname",
    ["-web", "web-", "web_01", "web 01", "web.example.com", "x" * 64, "wéb", "web!"],
)
def test_invalid_hostnames_are_rejected_at_the_field(hostname):
    """FR-005: a hostname with invalid characters is marked as an error (RFC 1123)."""
    with pytest.raises(ValidationError) as excinfo:
        Basics(hostname=hostname)
    assert excinfo.value.errors()[0]["loc"] == ("hostname",)


@pytest.mark.parametrize("fqdn", ["web-01.example.com", "a.b", "host.sub.example.org"])
def test_valid_fqdns(fqdn):
    """FR-005: fully qualified domain names are accepted."""
    assert Basics(fqdn=fqdn).fqdn == fqdn


@pytest.mark.parametrize(
    "fqdn", ["web-01", "-a.example.com", "a..b", "a.b.", "a_b.example.com", "a." + "b" * 64]
)
def test_invalid_fqdns_are_rejected(fqdn):
    """FR-005: an invalid FQDN is marked as an error at the field."""
    with pytest.raises(ValidationError) as excinfo:
        Basics(fqdn=fqdn)
    assert excinfo.value.errors()[0]["loc"] == ("fqdn",)


def test_fqdn_longer_than_253_characters_is_rejected():
    """FR-005: FQDNs are limited to 253 characters (RFC 1123)."""
    with pytest.raises(ValidationError):
        Basics(fqdn=".".join(["a" * 63] * 4) + ".com")


@pytest.mark.parametrize("timezone", ["UTC", "Europe/Berlin", "America/New_York"])
def test_valid_timezones(timezone):
    """FR-005: IANA time zones are accepted."""
    assert Basics(timezone=timezone).timezone == timezone


@pytest.mark.parametrize("timezone", ["Mars/Olympus", "CEST+2", "europe/berlin"])
def test_invalid_timezones_are_rejected(timezone):
    """FR-005: unknown time zones are marked as an error."""
    with pytest.raises(ValidationError):
        Basics(timezone=timezone)


@pytest.mark.parametrize("locale", ["en_US.UTF-8", "de_DE.UTF-8", "C.UTF-8", "C", "de_DE@euro"])
def test_valid_locales(locale):
    """FR-005: POSIX locale names are accepted."""
    assert Basics(locale=locale).locale == locale


@pytest.mark.parametrize("locale", ["english", "en-US", "EN_us.UTF-8", "en_US UTF-8"])
def test_invalid_locales_are_rejected(locale):
    """FR-005: malformed locale names are marked as an error."""
    with pytest.raises(ValidationError):
        Basics(locale=locale)


@pytest.mark.parametrize("instance_id", ["has space", "-leading", "a" * 129, "ä"])
def test_invalid_instance_ids_are_rejected(instance_id):
    """FR-005: instance-ids must be safe single tokens."""
    with pytest.raises(ValidationError):
        Basics(instance_id=instance_id)


def test_empty_strings_mean_not_set():
    """FR-004: empty form fields are treated as not set."""
    basics = Basics(instance_id="", hostname="  ", fqdn="", timezone="", locale="")
    assert basics == Basics()


def test_whitespace_is_trimmed():
    """FR-004: surrounding whitespace from form input is ignored."""
    assert Basics(hostname=" web-01 ").hostname == "web-01"


def test_unknown_fields_are_rejected():
    """FR-004: typos in field names are reported instead of silently ignored."""
    with pytest.raises(ValidationError):
        Basics(hostnme="web-01")


@pytest.mark.parametrize("name", ["", "   ", "x" * 101])
def test_invalid_names_are_rejected(name):
    """FR-005: the configuration name is required and at most 100 characters."""
    with pytest.raises(ValidationError):
        Configuration(name=name)


def test_suggested_instance_id_contains_hostname_and_is_unique():
    """FR-005: the suggestion has the form iid-<hostname>-<short-uuid>."""
    first, second = suggest_instance_id("web-01"), suggest_instance_id("web-01")
    assert re.fullmatch(r"iid-web-01-[0-9a-f]{8}", first)
    assert first != second
    assert Basics(instance_id=first).instance_id == first


def test_suggested_instance_id_without_hostname():
    """FR-005: without a hostname, the suggestion is iid-<short-uuid>."""
    assert re.fullmatch(r"iid-[0-9a-f]{8}", suggest_instance_id(None))
