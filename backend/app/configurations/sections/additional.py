"""FR-014: additional settings the form does not cover, edited as YAML only.

Keys that the form does not know (e.g. `ntp`, bonds and VLANs in network-config),
and known keys whose content the form cannot represent losslessly, are kept here
unchanged and rendered again on output. They override nothing silently: a key set
both here and in the form is an error (see `checks`).
"""

from typing import Any

from pydantic import Field

from app.configurations.sections.common import Section


class Additional(Section):
    user_data: dict[str, Any] = Field(
        default_factory=dict, description="Additional top-level keys of user-data."
    )
    meta_data: dict[str, Any] = Field(
        default_factory=dict, description="Additional keys of meta-data."
    )
    network: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional keys of the Netplan v2 network section (e.g. bonds, vlans).",
    )
    vendor_data: dict[str, Any] | None = Field(
        default=None, description="vendor-data as cloud-config mapping; null = no file."
    )

    def is_empty(self) -> bool:
        return not (self.user_data or self.meta_data or self.network) and self.vendor_data is None
