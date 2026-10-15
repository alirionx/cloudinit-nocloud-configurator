# cloud-init JSON schemas

`schema-cloud-config-v1.json` and `schema-network-config-v2.json` are taken unchanged from
cloud-init 25.1.4 as shipped in Debian 13 (`cloud-init 25.1.4-1+deb13u1`), the target OS of
the generated seed drives (OQ-09). They are used to validate generated and hand-edited YAML
(NFR-008, FR-014).

cloud-init is Copyright Canonical Ltd. and contributors and dual-licensed under GPL-3 or
Apache-2.0. These files are used under the Apache License, Version 2.0:
https://www.apache.org/licenses/LICENSE-2.0

Update them together with the targeted Debian release.
