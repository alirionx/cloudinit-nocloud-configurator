"""FR-014: parse hand-edited YAML back into the configuration model.

Each file is parsed into the form sections where this is lossless; everything else
is kept as additional settings. A group of keys ("unit") is taken over by the form
only if rendering the resulting form section reproduces exactly the same YAML values.
Otherwise the keys are kept unchanged as additional settings, so nothing is lost.

Values the form understands but considers invalid (e.g. a hostname with '_') are
errors with their line number, like in the form.
"""

from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from app.configurations.keys import META_DATA_FIELDS, NETWORK_KEYS
from app.configurations.model import Configuration
from app.configurations.rendering import (
    META_DATA,
    NETWORK_CONFIG,
    USER_DATA,
    VENDOR_DATA,
    form_user_data,
    network_data,
)
from app.configurations.yaml_input import YamlDocument, YamlInputError, YamlIssue, load_yaml

CLOUD_CONFIG_HEADER = "#cloud-config"

type Json = dict[str, Any]
# Maps the YAML values of a unit to an update of the configuration (JSON form);
# returns None if the values cannot be represented by the form.
type Mapper = Callable[[dict[str, Any]], Json | None]

# Validation error types that mean "the form cannot represent this" (keep as YAML)
# rather than "invalid value" (report as error).
SHAPE_ERRORS = ("extra_forbidden", "missing", "literal_error", "union_tag_invalid")


class ParseResult:
    def __init__(self, configuration: Configuration, notices: list[str]) -> None:
        self.configuration = configuration
        self.notices = notices


def parse_file(config: Configuration, file_name: str, text: str) -> ParseResult:
    """Replace the parts of `config` that come from `file_name` with the parsed YAML."""
    parsers = {
        USER_DATA: _parse_user_data,
        META_DATA: _parse_meta_data,
        NETWORK_CONFIG: _parse_network_config,
        VENDOR_DATA: _parse_vendor_data,
    }
    if file_name not in parsers:
        raise ValueError(f"unknown file {file_name}")
    return parsers[file_name](config, text)


# --- helpers ---


def _is_shape_error(error: Any) -> bool:
    kind = error["type"]
    return kind in SHAPE_ERRORS or kind.endswith("_type") or kind.endswith("_parsing")


def _issue(doc: YamlDocument, path: tuple[str | int, ...], msg: str) -> YamlIssue:
    return YamlIssue(line=doc.line_of(path), path=list(path), msg=msg)


def _mapping(doc: YamlDocument, name: str) -> dict[str, Any]:
    if doc.data is None:
        return {}
    if not isinstance(doc.data, dict):
        raise YamlInputError([YamlIssue(line=1, path=[], msg=f"{name} must be a YAML mapping")])
    return doc.data


def _strings(value: Any) -> list[str] | None:
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    return None


def _comma_list(value: Any) -> list[str] | None:
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return _strings(value)


def _only_keys(entry: Any, allowed: set[str]) -> bool:
    return isinstance(entry, dict) and set(entry) <= allowed


def _require_header(text: str, name: str) -> None:
    if text.strip() and not text.lstrip().startswith(CLOUD_CONFIG_HEADER):
        raise YamlInputError(
            [YamlIssue(line=1, path=[], msg=f"{name} must start with '{CLOUD_CONFIG_HEADER}'")]
        )


# --- user-data units ---


def _scalar(section: str, field: str, kind: type) -> Mapper:
    def mapper(values: dict[str, Any]) -> Json | None:
        (value,) = values.values()
        if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
            return None
        return {section: {field: value}}

    return mapper


def _string_list(section: str, field: str) -> Mapper:
    def mapper(values: dict[str, Any]) -> Json | None:
        (value,) = values.values()
        items = _strings(value)
        return None if items is None else {section: {field: items}}

    return mapper


def _map_fqdn(values: dict[str, Any]) -> Json | None:
    """The FQDN comes with manage_etc_hosts: localhost (as rendered by the form)."""
    fqdn = values.get("fqdn")
    if not isinstance(fqdn, str) or values.get("manage_etc_hosts") != "localhost":
        return None
    return {"basics": {"fqdn": fqdn}}


USER_FIELDS = {
    "name", "gecos", "primary_group", "groups", "sudo", "shell", "passwd", "hashed_passwd",
    "lock_passwd", "ssh_authorized_keys", "system",
}  # fmt: skip


def _map_user(entry: dict[str, Any]) -> Json | None:
    if not _only_keys(entry, USER_FIELDS) or ("passwd" in entry and "hashed_passwd" in entry):
        return None
    groups = _comma_list(entry.get("groups", []))
    keys = entry.get("ssh_authorized_keys", [])
    sudo = entry.get("sudo")
    if groups is None or _strings(keys) is None or not (sudo is None or isinstance(sudo, str)):
        return None
    # The admin checkbox stands for 'sudo' as the last group (as the form renders it).
    admin = bool(groups) and groups[-1] == "sudo" and "sudo" not in groups[:-1]
    return {
        "name": entry.get("name"),
        "gecos": entry.get("gecos"),
        "primary_group": entry.get("primary_group"),
        "groups": groups[:-1] if admin else groups,
        "admin": admin,
        "sudo": sudo,
        "shell": entry.get("shell"),
        "password_hash": entry.get("passwd", entry.get("hashed_passwd")),
        "lock_passwd": entry.get("lock_passwd", True),
        "ssh_authorized_keys": keys,
        "system": entry.get("system", False),
    }


def _map_users(values: dict[str, Any]) -> Json | None:
    users = values["users"]
    if not isinstance(users, list):
        return None
    mapped = []
    for entry in users:
        if entry == "default":
            continue
        user = _map_user(entry) if isinstance(entry, dict) else None
        if user is None:
            return None
        mapped.append(user)
    return {"users": {"keep_default_user": "default" in users, "users": mapped}}


def _map_groups(values: dict[str, Any]) -> Json | None:
    groups = values["groups"]
    if not isinstance(groups, list):
        return None
    mapped = []
    for entry in groups:
        if isinstance(entry, str):
            mapped.append({"name": entry, "members": []})
        elif isinstance(entry, dict) and len(entry) == 1:
            ((name, members),) = entry.items()
            members = _comma_list(members) if members is not None else []
            if members is None:
                return None
            mapped.append({"name": name, "members": members})
        else:
            return None
    return {"users": {"groups": mapped}}


def _map_host_key_types(values: dict[str, Any]) -> Json | None:
    types = _strings(values["ssh_genkeytypes"])
    if types is None or not set(types) <= {"rsa", "ecdsa", "ed25519"}:
        return None
    return {"ssh": {"host_key_types": types}}


FILE_FIELDS = {"path", "content", "encoding", "owner", "permissions", "append", "defer"}


def _map_write_files(values: dict[str, Any]) -> Json | None:
    files = values["write_files"]
    if not isinstance(files, list):
        return None
    mapped = []
    for entry in files:
        if not _only_keys(entry, FILE_FIELDS):
            return None
        encoding = entry.get("encoding", "text/plain")
        if encoding not in ("text/plain", "b64", "base64"):
            return None
        permissions = entry.get("permissions")
        if isinstance(permissions, int) and not isinstance(permissions, bool):
            return None  # an octal number parsed as integer: keep as written
        mapped.append(
            {
                "path": entry.get("path"),
                "content": entry.get("content", ""),
                "encoding": "b64" if encoding in ("b64", "base64") else "text",
                "owner": entry.get("owner"),
                "permissions": permissions,
                "append": entry.get("append", False),
                "defer": entry.get("defer", False),
            }
        )
    return {"write_files": mapped}


def _map_commands(field: str) -> Mapper:
    def mapper(values: dict[str, Any]) -> Json | None:
        commands = values[field]
        if not isinstance(commands, list) or not all(
            isinstance(c, str) or _strings(c) is not None for c in commands
        ):
            return None
        return {"commands": {field: commands}}

    return mapper


def _map_disks(values: dict[str, Any]) -> Json | None:
    setup = values.get("disk_setup", {})
    fs_setup = values.get("fs_setup", [])
    mounts = values.get("mounts", [])
    if (
        not isinstance(setup, dict)
        or not isinstance(fs_setup, list)
        or not isinstance(mounts, list)
    ):
        return None
    disks: list[Json] = []
    partitions: dict[tuple[str, int], Json] = {}
    for device, spec in setup.items():
        if not _only_keys(spec, {"table_type", "layout", "overwrite"}):
            return None
        layout = spec.get("layout")
        if not isinstance(layout, list) or not all(
            isinstance(size, int) and not isinstance(size, bool) for size in layout
        ):
            return None
        disk_partitions = []
        for number, size in enumerate(layout, start=1):
            partition = {
                "size_percent": size,
                "filesystem": None,
                "label": None,
                "mount_point": None,
                "mount_options": None,
            }
            partitions[(device, number)] = partition
            disk_partitions.append(partition)
        disks.append(
            {
                "device": device,
                "table_type": spec.get("table_type", "mbr"),
                "overwrite": spec.get("overwrite", False),
                "partitions": disk_partitions,
            }
        )
    by_label: dict[str, Json] = {}
    for entry in fs_setup:
        if not _only_keys(entry, {"label", "filesystem", "device", "partition", "overwrite"}):
            return None
        partition = partitions.get((entry.get("device"), entry.get("partition")))
        if partition is None or partition["filesystem"] is not None:
            return None
        partition["filesystem"] = entry.get("filesystem")
        partition["label"] = entry.get("label")
        if partition["label"]:
            by_label[partition["label"]] = partition
    for entry in mounts:
        if not (isinstance(entry, list) and len(entry) == 6 and isinstance(entry[0], str)):
            return None
        partition = by_label.get(entry[0].removeprefix("LABEL="))
        if partition is None or not entry[0].startswith("LABEL=") or partition["mount_point"]:
            return None
        partition["mount_point"] = entry[1]
        partition["mount_options"] = entry[3]
    return {"disks": disks}


# Units of user-data keys, each taken over by the form only as a whole.
USER_DATA_UNITS: list[tuple[tuple[str, ...], Mapper]] = [
    (("fqdn", "manage_etc_hosts"), _map_fqdn),
    (("timezone",), _scalar("basics", "timezone", str)),
    (("locale",), _scalar("basics", "locale", str)),
    (("users",), _map_users),
    (("groups",), _map_groups),
    (("ssh_pwauth",), _scalar("ssh", "password_authentication", bool)),
    (("disable_root",), _scalar("ssh", "disable_root", bool)),
    (("ssh_deletekeys",), _scalar("ssh", "delete_host_keys", bool)),
    (("ssh_genkeytypes",), _map_host_key_types),
    (("ssh_authorized_keys",), _string_list("ssh", "authorized_keys")),
    (("package_update",), _scalar("packages", "update", bool)),
    (("package_upgrade",), _scalar("packages", "upgrade", bool)),
    (("package_reboot_if_required",), _scalar("packages", "reboot_if_required", bool)),
    (("packages",), _string_list("packages", "packages")),
    (("write_files",), _map_write_files),
    (("bootcmd",), _map_commands("bootcmd")),
    (("runcmd",), _map_commands("runcmd")),
    (("disk_setup", "fs_setup", "mounts"), _map_disks),
]


def _deep_merge(base: Json, update: Json) -> Json:
    result = dict(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _model_path_to_yaml(loc: tuple[Any, ...], keys: tuple[str, ...], data: dict) -> tuple:
    """Best-effort YAML location of a model error inside a unit (for line numbers)."""
    key = keys[0]
    indexes = [part for part in loc if isinstance(part, int)]
    if key == "users" and indexes:
        entries = [i for i, entry in enumerate(data.get("users", [])) if entry != "default"]
        if indexes[0] < len(entries):
            return ("users", entries[indexes[0]], *[p for p in loc[3:] if isinstance(p, str)])
    if indexes and key in ("write_files", "bootcmd", "runcmd", "packages", "groups"):
        return (key, indexes[0])
    return (key,)


def _parse_user_data(config: Configuration, text: str) -> ParseResult:
    _require_header(text, "user-data")
    doc = load_yaml(text)
    data = _mapping(doc, "user-data")

    # Start from the configuration without anything that comes from user-data.
    defaults = Configuration(name=config.name).model_dump(mode="json")
    current = config.model_dump(mode="json")
    base = current | {
        key: defaults[key]
        for key in ("users", "ssh", "packages", "write_files", "commands", "disks")
    }
    base["basics"] = current["basics"] | {"fqdn": None, "timezone": None, "locale": None}
    base["additional"] = current["additional"] | {"user_data": {}}

    issues: list[YamlIssue] = []
    additional: dict[str, Any] = {}
    notices: list[str] = []
    handled: set[str] = set()

    for keys, mapper in USER_DATA_UNITS:
        present = {key: data[key] for key in keys if key in data}
        handled.update(keys)
        if not present:
            continue
        update = mapper(present)
        candidate_config = None
        if update is not None:
            try:
                candidate_config = Configuration.model_validate(_deep_merge(base, update))
            except ValidationError as exc:
                value_errors = [e for e in exc.errors() if not _is_shape_error(e)]
                if value_errors and not any(_is_shape_error(e) for e in exc.errors()):
                    for error in value_errors:
                        path = _model_path_to_yaml(tuple(error["loc"]), keys, data)
                        message = str(error["msg"]).removeprefix("Value error, ")
                        issues.append(_issue(doc, path, message))
                    continue
        if candidate_config is not None:
            rendered = form_user_data(candidate_config)
            if all(rendered.get(key) == value for key, value in present.items()):
                base = _deep_merge(base, update)
                continue
        additional.update(present)
        notices.append(
            f"'{', '.join(present)}' contains settings the form does not support; "
            "kept unchanged as additional settings (YAML only)"
        )

    if issues:
        raise YamlInputError(issues)
    additional.update({key: value for key, value in data.items() if key not in handled})
    base["additional"]["user_data"] = additional
    return ParseResult(Configuration.model_validate(base), notices)


# --- meta-data ---


def _parse_meta_data(config: Configuration, text: str) -> ParseResult:
    doc = load_yaml(text)
    data = _mapping(doc, "meta-data")
    basics = config.basics.model_dump(mode="json")
    issues = []
    for key, field in META_DATA_FIELDS.items():
        value = data.get(key)
        if value is not None and not isinstance(value, str):
            value = str(value)
        basics[field] = value
    try:
        updated = config.model_copy(
            update={
                "basics": type(config.basics).model_validate(basics),
                "additional": config.additional.model_copy(
                    update={
                        "meta_data": {k: v for k, v in data.items() if k not in META_DATA_FIELDS}
                    }
                ),
            }
        )
    except ValidationError as exc:
        reverse = {field: key for key, field in META_DATA_FIELDS.items()}
        for error in exc.errors():
            key = reverse.get(str(error["loc"][0]), str(error["loc"][0]))
            issues.append(_issue(doc, (key,), str(error["msg"]).removeprefix("Value error, ")))
        raise YamlInputError(issues) from None
    return ParseResult(updated, [])


# --- network-config ---

NIC_FIELDS = {"match", "set-name", "dhcp4", "dhcp6", "addresses", "routes", "nameservers", "mtu"}
BRIDGE_FIELDS = (NIC_FIELDS - {"match", "set-name"}) | {"interfaces", "parameters"}
DEFAULT_ROUTES = {"0.0.0.0/0": "gateway4", "::/0": "gateway6"}


def _map_address_settings(entry: dict[str, Any]) -> Json | None:
    settings: Json = {
        "dhcp4": entry.get("dhcp4", False),
        "dhcp6": entry.get("dhcp6", False),
        "addresses": entry.get("addresses", []),
        "gateway4": None,
        "gateway6": None,
        "nameservers": [],
        "search": [],
        "mtu": entry.get("mtu"),
    }
    for route in entry.get("routes", []):
        if not _only_keys(route, {"to", "via"}) or route.get("to") not in DEFAULT_ROUTES:
            return None
        field = DEFAULT_ROUTES[route["to"]]
        if settings[field] is not None:
            return None
        settings[field] = route.get("via")
    nameservers = entry.get("nameservers", {})
    if not _only_keys(nameservers, {"addresses", "search"}):
        return None
    settings["nameservers"] = nameservers.get("addresses", [])
    settings["search"] = nameservers.get("search", [])
    return settings


def _map_network(devices: dict[str, Any]) -> Json | None:
    ethernets, bridges = devices.get("ethernets", {}), devices.get("bridges", {})
    if not isinstance(ethernets, dict) or not isinstance(bridges, dict):
        return None
    mapped: Json = {"ethernets": [], "bridges": []}
    for name, entry in ethernets.items():
        entry = entry or {}
        if not _only_keys(entry, NIC_FIELDS):
            return None
        match = entry.get("match")
        mac = None
        if match is not None:
            if not _only_keys(match, {"macaddress"}) or entry.get("set-name") != name:
                return None
            mac = match.get("macaddress")
        elif "set-name" in entry:
            return None
        settings = _map_address_settings(entry)
        if settings is None:
            return None
        mapped["ethernets"].append({"name": name, "match_mac": mac, **settings})
    for name, entry in bridges.items():
        entry = entry or {}
        if not _only_keys(entry, BRIDGE_FIELDS):
            return None
        parameters = entry.get("parameters", {})
        if not _only_keys(parameters, {"stp", "forward-delay"}):
            return None
        settings = _map_address_settings(entry)
        if settings is None:
            return None
        mapped["bridges"].append(
            {
                "name": name,
                "interfaces": entry.get("interfaces", []),
                "stp": parameters.get("stp"),
                "forward_delay": parameters.get("forward-delay"),
                **settings,
            }
        )
    return mapped


def _parse_network_config(config: Configuration, text: str) -> ParseResult:
    doc = load_yaml(text)
    data = _mapping(doc, "network-config")
    wrapped = set(data) == {"network"}
    inner = data["network"] if wrapped else data
    prefix: tuple[str, ...] = ("network",) if wrapped else ()
    if not isinstance(inner, dict):
        raise YamlInputError([_issue(doc, prefix, "network must be a YAML mapping")])

    empty_network = {"ethernets": [], "bridges": []}
    notices: list[str] = []
    network: Json = empty_network
    additional: dict[str, Any] = {}
    if inner and inner.get("version") != 2:
        additional = inner
        notices.append("only Netplan version 2 is supported by the form; kept as YAML")
    elif inner:
        devices = {key: inner[key] for key in ("ethernets", "bridges") if key in inner}
        additional = {key: value for key, value in inner.items() if key not in NETWORK_KEYS}
        mapped = _map_network(devices) if devices else empty_network
        accepted = False
        if mapped is not None:
            try:
                candidate = config.model_copy(
                    update={"network": type(config.network).model_validate(mapped)}
                )
            except ValidationError as exc:
                if not any(_is_shape_error(e) for e in exc.errors()):
                    issues = []
                    for error in exc.errors():
                        loc = error["loc"]
                        kind, index = loc[0], loc[1] if len(loc) > 1 else None
                        names = list(devices.get(str(kind), {}))
                        path = (*prefix, str(kind))
                        if isinstance(index, int) and index < len(names):
                            path = (*path, names[index], *[str(p) for p in loc[2:3]])
                        message = str(error["msg"]).removeprefix("Value error, ")
                        issues.append(_issue(doc, path, message))
                    raise YamlInputError(issues) from None
            else:
                rendered = network_data(candidate.network) or {"network": {}}
                accepted = all(
                    rendered["network"].get(key) == value for key, value in devices.items()
                )
                if accepted:
                    network = mapped
        if not accepted:
            additional = {**devices, **additional}
            notices.append(
                "the interfaces contain settings the form does not support; "
                "kept unchanged as additional settings (YAML only)"
            )

    updated = config.model_copy(
        update={
            "network": type(config.network).model_validate(network),
            "additional": config.additional.model_copy(update={"network": additional}),
        }
    )
    return ParseResult(updated, notices)


# --- vendor-data ---


def _parse_vendor_data(config: Configuration, text: str) -> ParseResult:
    if not text.strip():
        vendor_data = None
    else:
        _require_header(text, "vendor-data")
        vendor_data = _mapping(load_yaml(text), "vendor-data")
    return ParseResult(
        config.model_copy(
            update={"additional": config.additional.model_copy(update={"vendor_data": vendor_data})}
        ),
        [],
    )
