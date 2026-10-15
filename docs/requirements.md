# Requirements Specification: cloudinit-nocloud-configurator

> **Status:** MVP implemented (steps 1–7), Helm chart pending
> **Version:** 0.19
> **Last updated:** 2026-10-15
> **Owner:** Daniel Quilitzsch

---

## Change History

| Version | Date       | Change | Author |
|---------|------------|--------|--------|
| 0.1     | 2026-10-15 | Initial structure | Claude |
| 0.2     | 2026-10-15 | Basic purpose, core functions (coarse) and technical constraints added | Claude |
| 0.3     | 2026-10-15 | OQ-02 and OQ-03 decided: seed drive instead of OS image; swappable datastore (TinyDB/CouchDB) | Claude |
| 0.4     | 2026-10-15 | OQ-04 decided: images are not stored but generated on every download; FR-003, NFR-005, data model and R-04 updated | Claude |
| 0.5     | 2026-10-15 | Configuration scope added: form/REST (FR-004), basics (FR-005), network (FR-006), packages (FR-007), files (FR-008), bootcmd/runcmd (FR-009), users/groups (FR-010), SSH (FR-011), disks (FR-012), live YAML preview (FR-013); UI-01, data model, R-06, OQ-07 to OQ-10 added | Claude |
| 0.6     | 2026-10-15 | Manual YAML editing with round trip to the form added (FR-014, modeled on Rancher); FR-013, UI-01, OQ-07 and release plan updated | Claude |
| 0.7     | 2026-10-15 | OQ-01 decided: NoCloud only; out of scope updated | Claude |
| 0.8     | 2026-10-15 | OQ-05 decided: manifests for the default setup, Helm chart for customization; section 8.4 (DEP-001 to DEP-008) and R-07 added | Claude |
| 0.9     | 2026-10-15 | OQ-06 decided: no user management for now; out of scope, assumptions, R-03 and DEP-006 updated | Claude |
| 0.10    | 2026-10-15 | OQ-08 decided: network with NICs and bridges; FR-006 extended | Claude |
| 0.11    | 2026-10-15 | App container base image set: Alpine, fallback Debian slim; OQ-09 clarified (concerns target VMs, not the app container) | Claude |
| 0.12    | 2026-10-15 | OQ-10 decided: password hashing in the backend, alternatively a pre-computed hash; FR-010 refined | Claude |
| 0.13    | 2026-10-15 | App name set: cloudinit-nocloud-configurator | Claude |
| 0.14    | 2026-10-15 | OQ-09 decided: Debian as target OS of the VMs; FR-007, FR-010, assumptions and R-06 updated | Claude |
| 0.15    | 2026-10-15 | Problem statement (1.2) refined; NFR-015/NFR-016 on established, actively maintained open-source libraries added (criteria in 8.5); R-08 added; `genisoimage` removed | Claude |
| 0.19    | 2026-10-15 | DS-008 implemented: `compose.yaml` (CouchDB + app built on start, hardened like in Kubernetes) | Claude |
| 0.18    | 2026-10-15 | Clarifications of v0.17 confirmed by the product owner: FQDN with `manage_etc_hosts: localhost` (FR-005), numeric `fs_setup` partitions with filtered schema false positive (FR-012, R-09), SSH defaults always rendered (FR-011), hostname optional single label (FR-005), `lock_passwd` default on (FR-010), Vuetify (7.2), app starts while CouchDB is unreachable (DS-005/DS-006), additional API endpoints (FR-015) | Daniel Quilitzsch |
| 0.17    | 2026-10-15 | Implementation clarifications from steps 1–7 recorded (FR-005, FR-006, FR-008, FR-010 to FR-015, NFR-008, section 7.2, R-09); FR-001 to FR-016 marked as implemented; DS-003 and NFR-008 implemented in the MVP | Claude |
| 0.16    | 2026-10-15 | **Document translated to English** (German no longer required). ID prefixes changed: FA→FR, NFA→NFR, OF→OQ, Z→G (numbers unchanged). Added: managing configurations (FR-015, UI-02), light/dark theme switch (FR-016), English-only UI (NFR-014), MIT license (NFR-017), Python 3.13, NFR-011 to NFR-013, TinyDB exception (8.5). MVP scope = all "Must" requirements | Claude |

---

## 1. Introduction

### 1.1 Purpose of this Document
This document describes the functional and technical requirements for the app "cloudinit-nocloud-configurator". It is the binding basis for implementation (including by Claude Code) and is updated whenever new features are added.

### 1.2 Background / Problem Statement
Writing cloud-init configurations for the **NoCloud** datasource by hand is **complex, time-consuming and only reliably possible with expert knowledge**:

- **Extensive configuration schema:** cloud-init consists of many modules (e.g. `users`, `groups`, `write_files`, `packages`, `bootcmd`, `runcmd`, `disk_setup`, `fs_setup`, `mounts`), each with its own keys, data types, defaults and interactions. On top of that come separate files (`user-data`, `meta-data`, `network-config`) in different formats, such as Netplan v2 for networking.
- **Expert knowledge required:** Many details are not obvious and only scattered across the documentation, e.g. module execution order (`bootcmd` on every boot, `runcmd` once), `defer` for files owned by users that do not exist yet, password hashes in crypt format, or the volume label `cidata`.
- **Time-consuming even for experts:** Even experienced users have to look up keys, check YAML indentation and syntax, and usually verify the result with several test boots of a VM. Errors often only show up at boot time, and cloud-init silently ignores some unknown or misspelled keys.
- **Additional tooling:** Building the seed image requires local tools such as `xorriso`, `mtools` or `qemu-img`.

A web application simplifies this process: create the configuration in a guided form, see and validate the resulting YAML immediately, and download a ready-to-use image.

### 1.3 Goals
| ID   | Goal | Measurable success criterion |
|------|------|------------------------------|
| G-01 | Create cloud-init configurations (NoCloud) conveniently via a web UI | A valid configuration can be created without local tools |
| G-02 | Generate and download a seed image that can be attached to a VM | Download as ISO, RAW or QCOW2 is possible; cloud-init recognizes the image |
| G-03 | Run as a container, Kubernetes-ready | Deployment via container image on K8s without special privileges |

### 1.4 Out of Scope
The following is explicitly **not** part of the current version:
- cloud-init datasources other than NoCloud (e.g. ConfigDrive, EC2, Azure) – _permanently, decided in OQ-01_
- Building complete operating system images with embedded configuration – _decided in OQ-02_
- Storing or archiving generated images – _decided in OQ-04_
- User management, login and permission model – _for now, decided in OQ-06_
- Languages other than English (UI, API, documentation) – _decided in NFR-014_

---

## 2. Stakeholders and Target Audience

### 2.1 Stakeholders
| Role | Description | Interest in the app |
|------|-------------|---------------------|
| Product owner | Daniel Quilitzsch | Functional requirements, acceptance |

### 2.2 User Roles / Personas
| Role | Description | Typical tasks |
|------|-------------|---------------|
| Administrator / DevOps | Provisions VMs (e.g. Proxmox, KVM/libvirt, VMware, bare metal) | Create cloud-init configuration, download seed image and attach it to a VM |

---

## 3. System Context

### 3.1 Platform(s)
- [x] Web app (browser)
- [ ] iOS
- [ ] Android
- [ ] Desktop (Windows / macOS / Linux)

### 3.2 External Systems and Interfaces
| System | Purpose | Type of integration |
|--------|---------|---------------------|
| Target hypervisor / VM | Attaches the generated seed image | Indirect via downloaded file (no direct integration) |

### 3.3 Domain Background: NoCloud
- cloud-init detects a NoCloud seed medium by its **filesystem label `cidata`** (or `CIDATA`).
- The medium contains the files `user-data` and `meta-data`, optionally `network-config` and `vendor-data`.
- Supported filesystems: ISO 9660 or VFAT.

---

## 4. Functional Requirements

> **Convention:** Every requirement has a unique ID (`FR-xxx`) that is never reused, even if a requirement is dropped (status "Rejected" instead).
> **Priority (MoSCoW):** Must · Should · Could · Won't (now)

### 4.1 Create Configuration

#### FR-001: Create a cloud-init configuration for NoCloud
- **Priority:** Must
- **Status:** Implemented (v0.17)
- **User story:** As an administrator, I want to create a cloud-init configuration for NoCloud via the web UI so that I don't have to write YAML by hand.
- **Description:** The app generates at least `user-data` and `meta-data`, optionally `network-config` and `vendor-data`.
- **Acceptance criteria:**
  - [x] Given a created configuration, when I save it, then valid `user-data` and `meta-data` exist.
- **Dependencies:** –

#### FR-004: Configuration via web form and REST API
- **Priority:** Must
- **Status:** Implemented (v0.17)
- **User story:** As an administrator, I want to set the essential cloud-init parameters either via a web form or via REST calls so that I can use the app both interactively and in automation (e.g. scripts or pipelines).
- **Description:**
  - A **Pydantic model** in the backend is the single authoritative description of a configuration ("single source of truth"). Form and REST API work on the same model.
  - The form is divided into sections (FR-005 to FR-012) that can be expanded and collapsed individually. Empty sections produce no entries in the YAML output.
  - The YAML (`user-data`, `meta-data`, `network-config`) is rendered from the model **in the backend only**.
- **Acceptance criteria:**
  - [x] Given a configuration created via the form, when I send the same values via the REST API, then identical YAML is produced.
  - [x] Given a REST call with invalid values, when it is processed, then the API responds with HTTP 422 and field-level error messages.
  - [x] Given an invalid value in the form, when I leave the field, then the error is shown directly at the field.
  - [x] Given an empty section, when the YAML is rendered, then it contains no keys for that section.
- **Dependencies:** FR-001, NFR-008, NFR-010

#### FR-005: Basics and meta-data
- **Priority:** Must
- **Status:** Implemented (v0.17)
- **Origin:** _Added by Claude (v0.5), because `meta-data` is mandatory for NoCloud._
- **User story:** As an administrator, I want to set the name, hostname and instance ID of the VM so that cloud-init identifies and names the VM correctly.
- **Description:** Fields: configuration name (app-internal only), `instance-id`, `local-hostname`, optional `fqdn`, timezone, locale.
- **Acceptance criteria:**
  - [x] Given a new configuration, when I don't enter an `instance-id`, then a unique ID is suggested automatically (e.g. `iid-<hostname>-<short-uuid>`).
  - [x] Given a hostname with invalid characters, when I enter it, then it is marked as an error (RFC 1123).
- **Clarifications (v0.17):** The configuration name is required (1–100 characters). The hostname is optional (a new configuration starts empty, FR-015) and is a single RFC 1123 label (e.g. `web-01`); the full name goes into `fqdn`. An FQDN that does not start with the hostname gives a warning. With an FQDN, `manage_etc_hosts: localhost` is rendered so that the FQDN resolves (`hostname -f`); only the 127.0.1.1 line of `/etc/hosts` is maintained (verified by booting Debian 13). Timezones are IANA names, locales POSIX names (e.g. `en_US.UTF-8`).
- **Dependencies:** FR-004

#### FR-006: Network configuration
- **Priority:** Must
- **Status:** Implemented (v0.17)
- **User story:** As an administrator, I want to configure the VM's network interfaces so that it is reachable at the right address on first boot.
- **Description:** The file `network-config` is generated in **Netplan version 2** format. Per interface:
  - Matching by name (e.g. `eth0`, `ens3`) or MAC address (`match: macaddress` + `set-name`)
  - DHCPv4 / DHCPv6 on/off
  - Static addresses in CIDR notation (IPv4 and IPv6), gateway, DNS servers, search domains, MTU
  - Without a network section, no `network-config` is generated (cloud-init then uses DHCP on the first interface).
  - **Bridges** (`bridges` in Netplan v2): name, member NICs (`interfaces`), the same address settings as a NIC (DHCP, static, gateway, DNS, MTU) and optionally STP and forward delay. A NIC that is a bridge member gets no address of its own.
  - Bonds and VLANs are not supported in the form (OQ-08); they can be added via YAML editing (FR-014) if needed.
- **Acceptance criteria:**
  - [x] Given an interface with static IP, gateway and DNS, when the YAML is rendered, then `network-config` contains a valid Netplan v2 entry with exactly these values.
  - [x] Given an invalid IP address or a gateway outside the subnet, when I enter it, then an error or warning is shown.
  - [x] Given DHCP and a static address at the same time, when I save, then this is allowed (both are set).
  - [x] Given a bridge `br0` with NIC `eth0` and a static IP, when the YAML is rendered, then `network-config` contains `eth0` without an address under `ethernets` and `br0` with `interfaces: [eth0]` and the IP under `bridges`.
  - [x] Given a NIC that is a bridge member and has an address of its own, when I save, then an error is shown.
  - [x] Given a bridge referencing an undefined NIC, when I save, then an error is shown.
- **Clarifications (v0.17):** Separate IPv4 and IPv6 gateway fields, rendered as default routes (`to: 0.0.0.0/0` / `to: ::/0`). MTU 576–9216. Bonds and VLANs added via YAML (FR-014) may be bridge members. A gateway without a static address of the same family (and without DHCP) gives a warning.
- **Dependencies:** FR-004

#### FR-007: Package management
- **Priority:** Must
- **Status:** Implemented (v0.17)
- **User story:** As an administrator, I want to define whether package sources are refreshed, the system is upgraded and which additional packages are installed so that the VM is ready to use after first boot.
- **Description:**
  - Toggles: `package_update`, `package_upgrade`, `package_reboot_if_required`
  - Package list via a **tag input**: packages are entered separated by Enter, comma or space (e.g. `git`, `wget`, `docker.io`), shown as removable chips and de-duplicated.
  - Several packages can be pasted at once (copy & paste of a list).
  - The target OS is **Debian** (OQ-09): package names and hints refer to the Debian package repositories (`apt`). Package names are not checked against the repositories; a typo only shows up at boot.
- **Acceptance criteria:**
  - [x] Given the input `git, wget docker.io`, when I press Enter, then three entries are created.
  - [x] Given a package that is already in the list, when I enter it again, then it is not added twice.
  - [x] Given enabled toggles and a package list, when the YAML is rendered, then `user-data` contains `package_update`, `package_upgrade` and `packages` with exactly these values.
- **Dependencies:** FR-004

#### FR-008: Create files (write_files)
- **Priority:** Must
- **Status:** Implemented (v0.17)
- **User story:** As an administrator, I want to have arbitrary files created on the VM so that configuration files and scripts are in place at first boot.
- **Description:** Dedicated UI component "file editor" with a list of files. Per file:
  - Target path (absolute), content, owner (`owner`, e.g. `root:root`), permissions (`permissions` as octal, e.g. `0644`), `append` and `defer` (write the file only after users have been created)
  - Content in a **code editor** with line numbers and syntax highlighting chosen by file extension (e.g. `.sh`, `.yaml`, `.json`, `.conf`)
  - **File upload** from the browser as an alternative to typing; binary files are Base64-encoded automatically (`encoding: b64`)
  - Permission presets (e.g. "Script 0755", "Config 0644", "Secret 0600")
  - Files can be duplicated, reordered and deleted
- **Acceptance criteria:**
  - [x] Given a relative target path, when I enter it, then it is marked as an error.
  - [x] Given an uploaded binary file, when the YAML is rendered, then it is included Base64-encoded with `encoding: b64`.
  - [x] Given a file owned by a user that is only created via FR-010, when I save, then `defer: true` is suggested.
  - [x] Given two files with the same target path without `append`, when I save, then a warning is shown.
- **Clarifications (v0.17):** File content is limited to 2 MiB per file. Text uploads stay text; non-UTF-8 files become `encoding: b64`. Permissions are normalized to four octal digits (`644` → `0644`).
- **Dependencies:** FR-004

#### FR-009: Run commands (bootcmd and runcmd)
- **Priority:** Must
- **Status:** Implemented (v0.17)
- **User story:** As an administrator, I want to define commands that run at boot so that I can automate setup steps that cloud-init does not cover directly.
- **Description:**
  - Two separate, ordered lists: **bootcmd** (very early, on **every** boot) and **runcmd** (once, at the end of the first boot).
  - Entries can be reordered via drag & drop. An entry is either a shell line (string) or a command with arguments (list).
  - A hint in the UI explains the difference, in particular that bootcmd runs on every boot.
- **Acceptance criteria:**
  - [x] Given three runcmd entries, when I change their order, then they appear in the YAML in exactly that order.
  - [x] Given a multi-line entry, when the YAML is rendered, then it is preserved correctly as a block literal.
- **Dependencies:** FR-004

#### FR-010: Users and groups
- **Priority:** Must
- **Status:** Implemented (v0.17)
- **User story:** As an administrator, I want to create users and groups so that I can log in with my own account after boot.
- **Description:**
  - **Groups:** name and optional members.
  - **Users:** name, display name (`gecos`), primary group, additional groups, shell (default `/bin/bash`), `sudo` rule (preset "passwordless": `ALL=(ALL) NOPASSWD:ALL`), password, `lock_passwd`, SSH public keys, system user yes/no.
  - Optionally, the distribution's default user is kept (`default` entry in `users`).
  - Passwords are **never stored in plain text**; only a hash is stored (SHA-512-crypt, `$6$…`). The password is entered in the form, sent to the backend via HTTPS, hashed immediately and discarded (OQ-10).
  - Alternatively, a pre-computed hash can be entered directly (e.g. from `mkpasswd -m sha-512`); it is validated for a valid crypt format.
  - A stored password is shown in the form only as "set" and can be replaced or removed, but not read.
- **Acceptance criteria:**
  - [x] Given a user with a password, when I save, then neither the datastore nor the YAML nor any log contains the plain-text password (NFR-007).
  - [x] Given a user in a group that does not exist and is not a standard group, when I save, then a warning is shown.
  - [x] Given a new user, when I mark them as administrator, then they are added to the Debian group `sudo` (not `wheel`).
  - [x] Given an invalid SSH public key, when I enter it, then it is marked as an error.
  - [x] Given a password entered in plain text, when I save, then the YAML contains a SHA-512-crypt hash under `passwd`, and the API never returns the plain-text password in any response.
  - [x] Given a directly entered hash in an invalid format, when I save, then an error is shown.
- **Clarifications (v0.17):** Hashing uses `openssl passwd -6` (password passed on stdin, never as an argument). Accepted precomputed hashes: SHA-512 (`$6$`), SHA-256 (`$5$`) and yescrypt (`$y$`, Debian's default). `lock_passwd` defaults to true (cloud-init default); a set but locked password gives a warning. "Keep the default user" is on by default. The administrator flag is rendered as the last group `sudo`.
- **Dependencies:** FR-004, FR-011

#### FR-011: SSH configuration
- **Priority:** Must
- **Status:** Implemented (v0.17)
- **User story:** As an administrator, I want to define how SSH is set up on the VM so that access is secure and works as intended.
- **Description:** Settings: allow password login (`ssh_pwauth`), disable root login (`disable_root`), regenerate host keys (`ssh_deletekeys`), key types (`ssh_genkeytypes`), global `ssh_authorized_keys`. Secure defaults: no password login, root disabled.
- **Acceptance criteria:**
  - [x] Given a new configuration, when I change nothing, then password login and root login are disabled.
  - [x] Given disabled password login and no user with an SSH key, when I save, then a warning is shown that the VM will not be reachable via SSH.
- **Clarifications (v0.17):** `ssh_pwauth` and `disable_root` are always rendered explicitly, so the secure defaults apply regardless of the image's defaults (exception to "empty sections produce no keys", FR-004). `ssh_deletekeys` and `ssh_genkeytypes` are only rendered when they differ from cloud-init's defaults.
- **Dependencies:** FR-004

#### FR-012: Partition, format and mount additional disks
- **Priority:** Must
- **Status:** Implemented (v0.17)
- **User story:** As an administrator, I want additional disks of the VM to be partitioned, formatted and mounted automatically so that data disks are usable right away.
- **Description:** Implemented via the cloud-init modules `disk_setup`, `fs_setup` and `mounts`. Per disk: device (e.g. `/dev/vdb` or `/dev/disk/by-id/…`), partition table (GPT/MBR), partitions, filesystem (`ext4`, `xfs`, `btrfs`), label, mount point, mount options.
- **Acceptance criteria:**
  - [x] Given a disk with filesystem and mount point, when the YAML is rendered, then `disk_setup`, `fs_setup` and `mounts` are filled consistently.
  - [x] Given the option "force overwrite", when I enable it, then I must confirm a clear data-loss warning. Default is "do not overwrite" (`overwrite: false`).
  - [x] Given a mount point used twice, when I save, then an error is shown.
- **Clarifications (v0.17):** Partitions are sized in percent of the disk. A label is required to mount a filesystem; mounts use `LABEL=<label>` and default to the options `defaults,nofail`. Filesystems reference partitions by number (`partition: 1`), which also works for `/dev/disk/by-id/…` and NVMe devices. Known limitation: cloud-init's own JSON schema rejects numeric partitions although cloud-init documents and supports them; the app filters this false positive (NFR-008), but cloud-init logs "cloud-config failed schema validation" at boot (see R-09). xfs/btrfs give a hint that the tools must be present in the image.
- **Dependencies:** FR-004

### 4.2 Generate and Download Image

#### FR-002: Generate seed image
- **Priority:** Must
- **Status:** Implemented (v0.17)
- **User story:** As an administrator, I want to generate a seed image from my configuration so that I can attach it to a VM as an additional drive.
- **Description:** Only a **seed drive** is generated (no operating system image). The filesystem carries the label `cidata` and contains the NoCloud files in its root directory. Supported output formats:

  | Format | Content | Generated with (guideline) |
  |--------|---------|----------------------------|
  | ISO    | ISO 9660 filesystem (with Joliet/Rock Ridge) | `xorriso` |
  | RAW    | Disk image with VFAT filesystem | `mkfs.vfat` + `mtools` |
  | QCOW2  | Same as RAW, converted to QCOW2 | `qemu-img convert` |
- **Acceptance criteria:**
  - [x] Given a valid configuration, when I choose a format, then an image in that format is generated.
  - [x] Given a generated image, when it is attached to a VM with cloud-init, then cloud-init applies the configuration on first boot.
- **Dependencies:** FR-001

#### FR-003: Download image
- **Priority:** Must
- **Status:** Implemented (v0.17)
- **User story:** As an administrator, I want to download the generated image so that I can use it in my virtualization environment.
- **Acceptance criteria:**
  - [x] Given a generated image, when I click "Download", then I receive the file with a meaningful file name and matching extension (`.iso`, `.img`/`.raw`, `.qcow2`).
  - [x] Given a saved configuration and a chosen format, when I request the download, then the image is generated fresh within the same request and delivered directly, without any image file being stored permanently.
  - [x] Given a completed download, when the request has ended, then all temporary files of the generation have been removed.
- **Note:** Images are not stored but generated on every download (OQ-04).
- **Dependencies:** FR-002

### 4.3 Preview

#### FR-013: Live preview of the generated YAML files
- **Priority:** Must
- **Status:** Implemented (v0.17)
- **User story:** As an administrator, I want to see immediately while typing in the form which YAML results from it so that I can understand and check the effect of my input.
- **Description:**
  - Below the form (reference: [Fuel Ignition](https://opensuse.github.io/fuel-ignition/edit)), the result is shown in tabs: `user-data`, `meta-data`, `network-config`, and `vendor-data` if present. Tabs without content are greyed out.
  - The preview updates on every change. Rendering is done by the backend (FR-004) via a dedicated preview endpoint; calls are debounced so that not every keystroke triggers a request.
  - The preview is read-only by default, has syntax highlighting and allows copying and downloading each file. Manual editing: see FR-014.
  - Validation errors (NFR-008) appear in the preview and link to the affected form field.
  - Secrets (password hashes) can be masked in the preview.
- **Acceptance criteria:**
  - [x] Given an open form, when I change a field, then the preview shows the change no later than 1 second after the last input.
  - [x] Given an error in the preview, when I click it, then the form jumps to the affected field.
  - [x] Given a preview, when I choose "Copy", then the content of the active file is in the clipboard.
  - [x] Given the same input, when I download the image, then it contains exactly the YAML shown in the preview.
- **Clarifications (v0.17):** Preview endpoint `POST /api/preview` (unsaved form state) and `GET /api/configurations/{id}/preview`; both return the files, warnings and cloud-init schema hints (NFR-008). Debounce: 300 ms. Secrets are masked by default.
- **Dependencies:** FR-004, NFR-008

#### FR-014: Edit YAML manually (form ↔ YAML)
- **Priority:** Must
- **Status:** Implemented (v0.17)
- **User story:** As an administrator, I want to adjust the generated YAML files by hand at the end so that I can also set options the form does not cover, without leaving the app.
- **Description:** Modeled on "Edit as YAML" in SUSE Rancher: the user switches between form view and YAML view, and both stay in sync.
  - Each preview file (FR-013) can be switched via "Edit as YAML" into an editor with syntax highlighting, line numbers and error markers.
  - When switching back or saving, the backend parses the YAML into the Pydantic model (FR-004). Values known to the form reappear in the form.
  - Keys unknown to the form (e.g. further cloud-init modules) are **not lost**: they are stored in the model as "additional settings", rendered again on output, and shown in the form as a separate section that can only be edited as YAML.
  - The edited YAML is validated against the cloud-init schema like any other configuration (NFR-008).
  - Changes in the YAML editor can be discarded ("revert to last saved state").
- **Acceptance criteria:**
  - [x] Given a hostname changed in the YAML editor, when I switch to the form, then the form shows the new hostname.
  - [x] Given a key added in the YAML editor that the form does not know (e.g. `ntp:`), when I save and reload the configuration, then it is still present in the YAML.
  - [x] Given YAML with a syntax error, when I try to switch to the form or save, then this is prevented and the error is shown with its line number.
  - [x] Given a value that violates the schema, when I save, then a hint with its location is shown; saving is allowed, but the download shows a warning.
  - [x] Given YAML comments, when I switch to the YAML editor, then the UI points out that comments are not preserved on save.
  - [x] Given a plain-text password in the YAML (`plain_text_passwd` or `chpasswd` with plain text), when I save, then a warning is shown (NFR-007).
- **Clarifications (v0.17):** A group of keys is taken over by the form only if rendering the form reproduces exactly the same YAML values (lossless round trip); otherwise the keys are kept unchanged as additional settings (per file: user-data, meta-data, network-config; vendor-data is YAML only) and the section shows a hint. A key set both in the form and as additional setting is an error. Values the form considers invalid are errors with line numbers. YAML input is limited to 1 MiB and 100,000 nodes (protection against alias/merge-key expansion). The form is locked while a file is edited as YAML. Endpoint: `POST /api/parse`.
- **Dependencies:** FR-004, FR-013, NFR-008

### 4.4 Manage Configurations

#### FR-015: Manage saved configurations (CRUD and duplicate)
- **Priority:** Must
- **Status:** Implemented (v0.17)
- **User story:** As an administrator, I want to list, open, edit, rename, duplicate and delete my saved configurations so that I can reuse and maintain them over time.
- **Description:**
  - **List** (UI-02): all saved configurations with name, hostname, last modified date; sortable by name and date, filterable by a search field (name, hostname).
  - **Create:** start a new, empty configuration with secure defaults (FR-011).
  - **Open / edit:** opens the configuration in the editor (UI-01); changes are saved explicitly ("Save"). Unsaved changes trigger a warning when leaving the editor.
  - **Rename:** directly in the list or in the editor.
  - **Duplicate:** creates a copy named "<name> (copy)" with a new ID and a new `instance-id`; password hashes and SSH keys are copied.
  - **Delete:** after confirmation; deletion is permanent (NFR-012).
  - REST API: `GET /api/configurations`, `POST /api/configurations`, `GET/PUT/DELETE /api/configurations/{id}`, `POST /api/configurations/{id}/duplicate`.
  - Concurrent changes are detected via the revision (DS-003).
- **Acceptance criteria:**
  - [x] Given several saved configurations, when I open the list, then all of them are shown with name, hostname and last modified date.
  - [x] Given a configuration, when I duplicate it, then a new configuration "<name> (copy)" with a new ID and a different `instance-id` is created and opened.
  - [x] Given a configuration, when I delete it and confirm, then it no longer appears in the list and `GET /api/configurations/{id}` returns HTTP 404.
  - [x] Given unsaved changes in the editor, when I navigate away, then I am asked whether to discard them.
  - [x] Given a configuration that was changed by someone else in the meantime, when I save, then I get a conflict message (HTTP 409) instead of silently overwriting.
- **Clarifications (v0.17):** Additional endpoints: `GET /api/configurations/{id}/files` (rendered files), `GET …/{id}/image?format=iso|raw|qcow2` (FR-003), `GET /api/defaults` (defaults and list templates from the model, FR-004). `GET /api/configurations` accepts `search` (name, hostname) and `sort` (`name`, `modified_at`, `created_at`, `-` for descending; default `-modified_at`). `PUT` requires the `revision` (DS-003 is implemented in the MVP, so the 409 criterion is not deferred). A `GET` response can be sent back unchanged with `PUT`.
- **Dependencies:** FR-004, DS-001, DS-003

### 4.5 Appearance

#### FR-016: Light and dark theme
- **Priority:** Must
- **Status:** Implemented (v0.17)
- **User story:** As an administrator, I want to switch between a light and a dark theme so that I can work comfortably in different environments.
- **Description:**
  - A toggle in the header switches between **light** and **dark**. **Light is the default.**
  - The choice is remembered in the browser (local storage) and applied on the next visit before the first render (no flicker).
  - All components, including code editors and the YAML preview, follow the theme.
- **Acceptance criteria:**
  - [x] Given a first visit, when the app loads, then the light theme is active.
  - [x] Given I switched to dark, when I reload the page, then the dark theme is active without a visible light flash.
  - [x] Given either theme, when I check text and controls, then contrast meets WCAG 2.1 AA (NFR-013).
- **Dependencies:** –

---

## 5. Non-functional Requirements

| ID      | Category | Requirement | Priority |
|---------|----------|-------------|----------|
| NFR-001 | Operations | The application is fully containerized and runs on Kubernetes. | Must |
| NFR-002 | Operations | Containers run as a **non-root user** and require **no privileged mode** (no loop devices, no `mount`). | Must |
| NFR-003 | Operations | Configuration exclusively via environment variables (12-factor). | Must |
| NFR-004 | Operations | Health endpoints for liveness and readiness (`/healthz`, `/readyz`). | Must |
| NFR-005 | Operations | The application is stateless; persistent data lives only in the datastore. Generated images are not persisted; temporary files exist only during a request in an ephemeral directory (e.g. `emptyDir` / `/tmp`). | Must |
| NFR-006 | Operations | Structured logging to stdout/stderr (JSON). | Should |
| NFR-007 | Security | Sensitive configuration content (password hashes, SSH keys, tokens) is never logged in plain text. | Must |
| NFR-008 | Quality | Generated configurations are validated against the official cloud-init JSON schema. | Should |
| NFR-009 | Maintainability | Datastore access goes through an abstraction layer (repository pattern). Business logic does not know any concrete DB backend. See section 8.3. | Must |
| NFR-010 | Maintainability | The REST API is documented via OpenAPI (provided automatically by FastAPI). | Must |
| NFR-011 | Performance | _Default set by Claude:_ Generating a seed image for a typical configuration (< 1 MB of content) takes < 2 s server-side; the preview endpoint responds in < 300 ms (p95). | Should |
| NFR-012 | Data protection | _Default set by Claude:_ The app stores no personal data beyond the configurations themselves, uses no tracking or telemetry and loads no assets from external CDNs. Deleted configurations are removed permanently. | Must |
| NFR-013 | Usability | _Default set by Claude:_ Desktop-first, fully usable from 1024 px width; all functions operable by keyboard; contrast meets WCAG 2.1 AA in both themes; each form section has a short help text with a link to the matching cloud-init documentation. | Should |
| NFR-014 | Language | **English only:** UI, API messages, logs, documentation and code comments are in English. No localization framework is required. | Must |
| NFR-015 | Maintainability | Only **established open-source libraries and tools** that are **actively maintained by their community** are used. Criteria and checks: see section 8.5. | Must |
| NFR-016 | Maintainability | Dependencies are pinned (lock files), updated automatically (e.g. Renovate or Dependabot) and scanned for known vulnerabilities in CI. | Should |
| NFR-017 | Licensing | The app is released under the **MIT license**; the repository contains a `LICENSE` file. | Must |

---

## 6. Data Model (Functional)

| Entity | Description | Key attributes | Relations |
|--------|-------------|----------------|-----------|
| Configuration | A saved NoCloud configuration, structured according to the Pydantic model (FR-004) | ID (UUID), name, basics, network, packages, files, bootcmd, runcmd, users, groups, SSH, disks, additional settings (FR-014), revision, created/modified timestamps | – |

_The structured model is stored, not the rendered YAML. The YAML is generated from it for preview and download._

_Generated images are not a persistent entity; they are created on every download (OQ-04)._

---

## 7. User Interface

### 7.1 Screens / Views
| ID    | Screen | Purpose | Related requirements |
|-------|--------|---------|----------------------|
| UI-01 | Configuration editor | Form with collapsible sections (top) and live YAML preview with tabs (bottom), switchable to YAML editing; save button; download button with format selection | FR-002 to FR-014 |
| UI-02 | Configuration list | Start page: list of saved configurations with search, sorting and actions (new, open, rename, duplicate, delete) | FR-015 |

### 7.2 Design Guidelines
- Light and dark theme with a toggle in the header; light is the default (FR-016).
- Clean, technical look with a consistent component library for Vue 3 (chosen according to section 8.5): **Vuetify** (v0.17; PrimeVue was rejected because it is no longer OSI-licensed since version 5, LIB-001). Code editors: CodeMirror 6.
- Code editors and the YAML preview use a monospace font and syntax highlighting matching the active theme.

---

## 8. Technical Constraints

### 8.1 Technology Stack
| Topic | Decision | Rationale |
|-------|----------|-----------|
| Backend | **Python 3.13 with FastAPI** | Requirement; modern, typed API with automatic OpenAPI docs |
| Frontend | **Vue.js** (version 3, built with Vite) | Requirement |
| Frontend delivery | The built frontend (static files) is **served by FastAPI** | One container, one deployment, no CORS issues |
| Datastore | **Document-based, swappable:** TinyDB (local/development) or CouchDB (production), selected via environment variable | Lightweight for dev, scalable for prod; see section 8.3 |
| Image generation | ISO: `xorriso` (not `genisoimage`, since cdrkit is no longer maintained, LIB-002); VFAT: `mkfs.vfat` + `mtools`; conversion: `qemu-img` | Works without root privileges and without mounts (see NFR-002) |
| Validation | cloud-init JSON schema (e.g. via `jsonschema`) | Detect errors early (NFR-008) |
| License | **MIT** (NFR-017) | Permissive; compatible with common open-source licenses of dependencies |

### 8.2 Build and Deployment
| Topic | Decision |
|-------|----------|
| Build | **Docker multi-stage build**: stage 1 builds the Vue frontend (Node), stage 2 contains the Python runtime, backend and built frontend. Node is not included in the final image. |
| Name | `cloudinit-nocloud-configurator`, used consistently for container image, Helm chart, Kubernetes resources and repository |
| Base image | **Alpine** (`python:3.13-alpine`) as the preferred, lightweight base image of the app container. Only if required tools or Python packages do not run reliably on Alpine (musl): **Debian slim** (`python:3.13-slim`). The image tools (`xorriso`, `dosfstools`, `mtools`, `qemu-img`) must be available as packages in the chosen base image. |
| Target platform | Kubernetes; additionally runnable locally via `docker run` or Docker Compose |
| Deployment artifacts | Kubernetes manifests for the default setup and a Helm chart for customized deployments, see section 8.4 |

### 8.3 Datastore Backends

The application supports two swappable datastore backends behind a common interface (NFR-009). The backend is selected at startup via environment variables.

| Backend | Use case | Characteristics | Limitations |
|---------|----------|-----------------|-------------|
| **TinyDB** (default) | Local development, single user, demo | Embedded, JSON file, no additional service | Only **1 process / 1 replica** (no concurrent writes); the file must be on a persistent volume if data should survive restarts |
| **CouchDB** | Production, Kubernetes | Separate service, HTTP/JSON API, multiple app replicas possible | Additional service to operate; optimistic locking via document revisions (`_rev`) |

#### Configuration (environment variables)

| Variable | Applies to | Description | Default |
|----------|------------|-------------|---------|
| `DATASTORE_BACKEND` | all | `tinydb` or `couchdb` | `tinydb` |
| `TINYDB_PATH` | TinyDB | Path to the database file | `./data/db.json` |
| `COUCHDB_URL` | CouchDB | URL of the CouchDB server, e.g. `http://couchdb:5984` | – (required) |
| `COUCHDB_USER` | CouchDB | User name | – (required) |
| `COUCHDB_PASSWORD` | CouchDB | Password (from a **Secret** in K8s) | – (required) |
| `COUCHDB_DATABASE` | CouchDB | Database name | `cloudinit` |

#### Requirements for the abstraction layer

| ID      | Requirement | Priority |
|---------|-------------|----------|
| DS-001 | Business logic and API access data only via a common repository interface (e.g. `get`, `list`, `create`, `update`, `delete`). | Must |
| DS-002 | Document IDs are generated by the application (UUID) and are backend-independent; internal backend IDs (e.g. TinyDB `doc_id`) are never exposed. | Must |
| DS-003 | Concurrent changes are detected (optimistic locking via a version/revision) and result in a defined conflict error (HTTP 409). | Should |
| DS-004 | An invalid or incomplete datastore configuration results in a clear error at startup; the application does not start. | Must |
| DS-005 | With CouchDB, missing databases are created at startup. | Should |
| DS-006 | The readiness check (`/readyz`) includes datastore availability. | Must |
| DS-007 | Both backends are verified with **the same automated tests** against the interface (contract tests). | Must |
| DS-008 | A Docker Compose file is provided for local development with CouchDB. _Implemented (v0.19): `compose.yaml`, settings via `.env`._ | Could |

### 8.4 Kubernetes Delivery

There are two delivery paths (OQ-05):

| Path | Audience | Content |
|------|----------|---------|
| **Kubernetes manifests** (`deploy/k8s/`) | Quick default start via `kubectl apply -f` | Minimal, working setup with fixed defaults |
| **Helm chart** (`deploy/helm/`) | Customized deployments, production | All settings configurable via `values.yaml`, including the datastore |

| ID      | Requirement | Priority |
|---------|-------------|----------|
| DEP-001 | The manifests contain at least namespace, deployment, service, ConfigMap and probes (NFR-004). Default setup: **TinyDB on a PersistentVolumeClaim with 1 replica** and update strategy `Recreate` (R-02). | Must |
| DEP-002 | The Helm chart allows choosing the datastore (`tinydb` or `couchdb`) and sets the environment variables from section 8.3 accordingly. | Must |
| DEP-003 | In the Helm chart, CouchDB can either be **installed alongside** (optional dependency, e.g. the official Apache CouchDB chart, via `couchdb.enabled`) or connected as an **external instance** via URL. | Must |
| DEP-004 | CouchDB credentials come from a Kubernetes Secret; an existing Secret can be referenced (`existingSecret`); passwords never appear in plain text in `values.yaml` examples. | Must |
| DEP-005 | The Helm chart prevents more than one replica with `tinydb` (template validation with a clear error message). | Must |
| DEP-006 | The Helm chart optionally supports Ingress (including annotations for upstream authentication, e.g. Basic Auth or OAuth2 Proxy), resource limits, SecurityContext (non-root, read-only root filesystem, NFR-002), labels/annotations and image tag. | Should |
| DEP-007 | The manifests are generated from the Helm chart with default values (`helm template`) so both paths do not drift apart; a CI check ensures the committed manifests are up to date. | Should |
| DEP-008 | The Helm chart is checked with `helm lint`. | Should |

### 8.5 Selection of Libraries and Tools

Every dependency (Python, JavaScript, system packages in the container) must meet the following criteria before it is added (NFR-015). Exceptions are documented below with a rationale.

| ID      | Criterion |
|---------|-----------|
| LIB-001 | **Open source** under an OSI-approved license that is compatible with the app's MIT license (NFR-017). |
| LIB-002 | **Actively maintained:** a release or significant commits within the last 12 months; reported security issues are fixed. |
| LIB-003 | **Established:** broad usage (e.g. downloads, dependent projects) and more than one person with write access, or backing by an organization or foundation. |
| LIB-004 | **No archived or deprecated projects.** |
| LIB-005 | Packages from official sources (PyPI, npm, Alpine or Debian repositories) and standard solutions of the respective ecosystem are preferred over niche solutions. |
| LIB-006 | The dependencies in use are listed with purpose and license in an overview in the repository (`docs/dependencies.md`) and reviewed for every release. |

#### Documented exceptions

| Dependency | Criterion not met | Rationale |
|------------|-------------------|-----------|
| TinyDB | LIB-003 (essentially a single maintainer) | Widely used and maintained; used only for local development and single-instance setups; encapsulated behind the repository interface (NFR-009), so it can be replaced without touching business logic. Production uses CouchDB (Apache Software Foundation). |

---

## 9. Assumptions and Risks

### 9.1 Assumptions
- The target VMs/images have cloud-init installed and the NoCloud datasource enabled.
- The target OS of the VMs is Debian (current stable release, e.g. the official Debian cloud images `genericcloud`). Other distributions often work too but are not specifically supported or tested (OQ-09).
- Generated seed images are small (a few KB to MB); generation typically takes only seconds.
- The app runs in a trusted network or is protected by an upstream component (e.g. Ingress with Basic Auth or an OAuth2 Proxy). All users see all configurations (OQ-06).

### 9.2 Risks
| ID   | Risk | Impact | Mitigation |
|------|------|--------|------------|
| R-01 | Image tools require root privileges or loop devices | Not K8s-ready without privileged pods | Only use tools that create images without mounting (xorriso, mtools) |
| R-02 | TinyDB is accidentally run with multiple replicas or workers | Data conflicts or loss | TinyDB only for dev/single instance; CouchDB for the K8s setup; warning in the startup log when TinyDB is active; Helm validation (DEP-005) |
| R-03 | Configurations contain credentials (password hashes, SSH keys, tokens); without login, anyone with network access can read them | Security risk in case of a leak | No plain-text logging (NFR-007); do not expose the app publicly or use upstream access control (DEP-006); login can be added later (OQ-06) |
| R-04 | Generated images consume storage | Storage fills up | Resolved: images are not stored (OQ-04); temporary files are removed after every request |
| R-05 | TinyDB and CouchDB behave differently | Errors only surface in production | Shared contract tests (DS-007); CouchDB setup testable locally via Docker Compose (DS-008) |
| R-06 | Package names and commands are distribution-specific | Configuration does not work as expected on distributions other than Debian | Debian as fixed target (OQ-09); UI presets and hints aligned with Debian; acceptance test with a Debian cloud image |
| R-07 | Manifests and Helm chart are maintained separately and drift apart | Default setup behaves differently from the chart | Generate manifests from the chart and check in CI (DEP-007) |
| R-09 | cloud-init's JSON schema rejects valid settings (numeric `fs_setup` partitions, FR-012) | cloud-init logs a schema warning at boot although the configuration works | Known false positive filtered in the app's schema check; behavior verified by booting Debian 13 (`scripts/boot-test.sh`); revisit when cloud-init fixes its schema |
| R-08 | A library in use is no longer maintained | Security issues, incompatibilities, costly migration | Selection criteria (8.5), DB abstraction (NFR-009) and regular dependency reviews (NFR-016, LIB-006) |

---

## 10. Open Questions

| ID    | Question | Status | Answer / decision |
|-------|----------|--------|-------------------|
| OQ-01 | Stay with NoCloud, or add further datasources later (e.g. ConfigDrive for OpenStack)? | Decided (v0.7) | NoCloud only. No further datasources planned. |
| OQ-02 | Do RAW/QCOW2 mean a **small seed drive** (VFAT with label `cidata`) or a **complete OS image** with embedded configuration? | Decided (v0.3) | Seed drive that is attached to the VM in addition. OS images are out of scope. |
| OQ-03 | Which document database? | Decided (v0.3) | TinyDB for local/dev, CouchDB for production; selected via environment variable (section 8.3). |
| OQ-04 | Should generated images be stored (for how long?) or generated on every download? | Decided (v0.4) | Generate on the fly on every download, store nothing. Seed images are small and quick to build; the app stays stateless and needs no file storage. |
| OQ-05 | Kubernetes delivery as plain manifests, Kustomize or Helm chart? | Decided (v0.8) | Manifests for the default setup, Helm chart for customized deployments (e.g. with CouchDB). Details in section 8.4. |
| OQ-06 | Is user management / login required (single user, multi-user, SSO)? | Decided (v0.9) | Not for now. Access control upstream if needed (Ingress/proxy). Can be added later as a new requirement. |
| OQ-07 | Should users be able to add YAML for cloud-init modules not covered by the form and edit the preview directly (YAML back into the form)? | Decided (v0.6) | Yes: manual YAML editing with round trip to the form, modeled on Rancher (FR-014). Unknown keys are kept as "additional settings"; no separate free-text field. |
| OQ-08 | Which network scope: Ethernet interfaces only, or also bonds, bridges and VLANs? | Decided (v0.10) | NICs (Ethernet) and bridges. Bonds and VLANs not in the form, only via YAML editing (FR-014). |
| OQ-09 | Which distributions run **in the target VMs** that boot the seed drive? _Not to be confused with the base image of the app container (section 8.2)._ | Decided (v0.14) | Debian. Package names, admin group (`sudo`) and UI hints follow Debian; other distributions are not specifically supported. |
| OQ-10 | Where is the user password hashed: in the browser or in the backend? | Decided (v0.12) | In the backend: transmitted via HTTPS, hashed immediately (SHA-512-crypt), only the hash is stored. A pre-computed hash can also be entered directly (FR-010). |

---

## 11. Release Planning

| Release | Content (requirement IDs) | Target date |
|---------|---------------------------|-------------|
| MVP (v1.0) | All requirements with priority **Must**: FR-001 to FR-016; NFR-001 to NFR-005, NFR-007, NFR-009, NFR-010, NFR-012, NFR-014, NFR-015, NFR-017; DS-001, DS-002, DS-004, DS-006, DS-007; DEP-001 to DEP-005 | _not set_ |
| v1.1 | Remaining **Should** and **Could** requirements: NFR-006, NFR-008, NFR-011, NFR-013, NFR-016; DS-003, DS-005, DS-008; DEP-006 to DEP-008 (earlier where cheap to include) | _not set_ |

_Note: FR-015 relies on DS-003 for conflict detection. DS-003 (and NFR-008) are implemented in the MVP (v0.17), so the 409 acceptance criterion is not deferred._

---

## 12. Glossary

| Term | Meaning |
|------|---------|
| cloud-init | Standard tool for initial configuration of Linux instances on first boot |
| NoCloud | cloud-init datasource that reads configuration data from a local medium (label `cidata`) |
| user-data | Main configuration (usually `#cloud-config` in YAML format) |
| meta-data | Instance metadata, e.g. `instance-id`, `local-hostname` |
| network-config | Optional network configuration (Netplan v2 or v1 format) |
| vendor-data | Optional additional configuration (e.g. from the platform operator) |
| Netplan v2 | YAML format for network configuration that cloud-init understands for `network-config` |
| bootcmd / runcmd | Command lists in cloud-init: bootcmd runs early on every boot, runcmd once at the end of the first boot |
| write_files | cloud-init module for creating files with content, owner and permissions |
| Debounce | Technique where an action is only triggered after a short pause in input |
| Seed image | Small disk image that contains the NoCloud files |
| ISO | Disk image in ISO 9660 format |
| RAW | Uncompressed, block-level disk image |
| QCOW2 | "QEMU Copy-On-Write v2" – disk image format of QEMU/KVM |
| Multi-stage build | Docker build in several stages; only what is needed ends up in the final image |
| MVP | Minimum Viable Product – the smallest usable version of the app |
| MoSCoW | Prioritization method: Must, Should, Could, Won't |
