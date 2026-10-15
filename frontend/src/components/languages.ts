import type { Language } from './CodeEditor.vue'

const BY_EXTENSION: Record<string, Language> = {
  yaml: 'yaml',
  yml: 'yaml',
  json: 'json',
  sh: 'shell',
  bash: 'shell',
  zsh: 'shell',
  conf: 'properties',
  cfg: 'properties',
  ini: 'properties',
  properties: 'properties',
  env: 'properties',
  service: 'properties',
  timer: 'properties',
  network: 'properties',
  toml: 'toml',
  py: 'python',
}

/** FR-008: syntax highlighting chosen by file extension. */
export function languageForPath(path: string): Language {
  const name = path.split('/').pop() ?? ''
  const extension = name.includes('.') ? name.split('.').pop()!.toLowerCase() : ''
  return BY_EXTENSION[extension] ?? 'text'
}
