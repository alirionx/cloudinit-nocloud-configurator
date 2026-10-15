// Types mirroring the backend's Pydantic model (FR-004). The backend stays the single
// source of truth: the form only collects input; validation, defaults and YAML come
// from the API.

export interface Basics {
  instance_id: string | null
  hostname: string | null
  fqdn: string | null
  timezone: string | null
  locale: string | null
}

// FR-006
export interface AddressSettings {
  dhcp4: boolean
  dhcp6: boolean
  addresses: string[]
  gateway4: string | null
  gateway6: string | null
  nameservers: string[]
  search: string[]
  mtu: number | null
}
export interface Ethernet extends AddressSettings {
  name: string
  match_mac: string | null
}
export interface Bridge extends AddressSettings {
  name: string
  interfaces: string[]
  stp: boolean | null
  forward_delay: number | null
}
export interface Network {
  ethernets: Ethernet[]
  bridges: Bridge[]
}

// FR-007
export interface Packages {
  update: boolean
  upgrade: boolean
  reboot_if_required: boolean
  packages: string[]
}

// FR-008
export interface WriteFile {
  path: string
  content: string
  encoding: 'text' | 'b64'
  owner: string | null
  permissions: string | null
  append: boolean
  defer: boolean
}

// FR-009
export type Command = string | string[]
export interface Commands {
  bootcmd: Command[]
  runcmd: Command[]
}

// FR-010
export interface Group {
  name: string
  members: string[]
}
export interface User {
  name: string
  gecos: string | null
  primary_group: string | null
  groups: string[]
  admin: boolean
  sudo: string | null
  shell: string | null
  /** Write-only: a new plain-text password. Never returned by the API. */
  password?: string | null
  password_hash: string | null
  lock_passwd: boolean
  ssh_authorized_keys: string[]
  system: boolean
}
export interface Users {
  keep_default_user: boolean
  users: User[]
  groups: Group[]
}

// FR-011
export type HostKeyType = 'rsa' | 'ecdsa' | 'ed25519'
export interface Ssh {
  password_authentication: boolean
  disable_root: boolean
  delete_host_keys: boolean
  host_key_types: HostKeyType[]
  authorized_keys: string[]
}

// FR-012
export type Filesystem = 'ext4' | 'xfs' | 'btrfs'
export interface Partition {
  size_percent: number
  filesystem: Filesystem | null
  label: string | null
  mount_point: string | null
  mount_options: string | null
}
export interface Disk {
  device: string
  table_type: 'gpt' | 'mbr'
  overwrite: boolean
  partitions: Partition[]
}

export interface Configuration {
  name: string
  basics: Basics
  network: Network
  packages: Packages
  write_files: WriteFile[]
  commands: Commands
  users: Users
  ssh: Ssh
  disks: Disk[]
}

export interface StoredConfiguration extends Configuration {
  id: string
  revision: string
  created_at: string
  modified_at: string
}

export interface ConfigurationSummary {
  id: string
  name: string
  hostname: string | null
  created_at: string
  modified_at: string
}

/** A validation error or warning, located by its path in the model. */
export interface Issue {
  loc: (string | number)[]
  msg: string
}

export type FileName = 'user-data' | 'meta-data' | 'network-config' | 'vendor-data'

export interface PreviewResponse {
  files: Record<FileName, string | null>
  warnings: Issue[]
}

export interface ItemTemplates {
  ethernet: Ethernet
  bridge: Bridge
  write_file: WriteFile
  user: User
  group: Group
  disk: Disk
  partition: Partition
}

export interface Defaults {
  configuration: Configuration
  items: ItemTemplates
}
