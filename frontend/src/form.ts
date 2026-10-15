// Form state helpers. The form works on the same structure as the API (FR-004).
import { inject, type InjectionKey, provide, type Ref } from 'vue'
import type { Configuration, ItemTemplates, StoredConfiguration } from './api/types'

/** Deep copy of form data (plain JSON). Unlike structuredClone it also accepts Vue proxies. */
export function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

/** The editable part of a stored configuration (without ID, revision, timestamps). */
export function toConfiguration(stored: StoredConfiguration): Configuration {
  const { id: _id, revision: _revision, created_at: _created, modified_at: _modified, ...config } = stored
  return clone(config)
}

export function randomSuffix(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(4))
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
}

/** FR-005: iid-<hostname>-<short-uuid>, same format as the backend. */
export function suggestInstanceId(hostname: string | null, suffix: string): string {
  const host = hostname?.trim()
  return host && /^[A-Za-z0-9-]+$/.test(host) ? `iid-${host}-${suffix}` : `iid-${suffix}`
}

/**
 * FR-007: split free text into entries (Enter, comma, space or pasted lists) and
 * merge them into a list without duplicates, keeping the order.
 */
export function mergeTags(current: string[], input: string[] | string, separators = /[\s,]+/): string[] {
  const values = (Array.isArray(input) ? input : [input]).flatMap((value) => value.split(separators))
  const result: string[] = []
  for (const value of [...current, ...values]) {
    const trimmed = value.trim()
    if (trimmed && !result.includes(trimmed)) result.push(trimmed)
  }
  return result
}

/** Move a list entry (drag & drop, up/down buttons). */
export function moveItem<T>(list: T[], from: number, to: number): void {
  if (to < 0 || to >= list.length || from === to) return
  const [item] = list.splice(from, 1)
  list.splice(to, 0, item!)
}

// Templates for new list entries come from the backend (GET /api/defaults).
const TEMPLATES: InjectionKey<Ref<ItemTemplates | null>> = Symbol('templates')

export function provideTemplates(templates: Ref<ItemTemplates | null>) {
  provide(TEMPLATES, templates)
}

/** A fresh copy of the default values for a new list entry. */
export function useTemplates() {
  const templates = inject(TEMPLATES)
  if (!templates) throw new Error('templates not provided')
  return <K extends keyof ItemTemplates>(kind: K): ItemTemplates[K] => {
    if (!templates.value) throw new Error('templates not loaded')
    return clone(templates.value[kind])
  }
}

/** user-data keys per form section (mirrors the backend's `keys.py`, for hints only). */
const SECTION_KEYS: Record<string, string[]> = {
  basics: ['fqdn', 'manage_etc_hosts', 'timezone', 'locale'],
  users: ['users', 'groups'],
  ssh: ['ssh_pwauth', 'disable_root', 'ssh_deletekeys', 'ssh_genkeytypes', 'ssh_authorized_keys'],
  packages: ['package_update', 'package_upgrade', 'package_reboot_if_required', 'packages'],
  write_files: ['write_files'],
  commands: ['bootcmd', 'runcmd'],
  disks: ['disk_setup', 'fs_setup', 'mounts'],
  network: [],
}

/** FR-014: keys of a section that are kept as YAML-only additional settings. */
export function yamlOnlyKeys(config: Configuration, section: string): string[] {
  if (section === 'network') {
    return ['ethernets', 'bridges'].filter((key) => key in config.additional.network)
  }
  return (SECTION_KEYS[section] ?? []).filter((key) => key in config.additional.user_data)
}
