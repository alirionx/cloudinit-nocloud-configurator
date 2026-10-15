// Thin wrapper around the REST API (FR-004, FR-015).
import type {
  Configuration,
  Defaults,
  ConfigurationSummary,
  FileName,
  Issue,
  ParseResponse,
  PreviewResponse,
  YamlError,
  StoredConfiguration,
} from './types'

/** An API error. `issues` holds field-level validation errors (HTTP 422). */
export class ApiError extends Error {
  readonly status: number
  readonly issues: Issue[]
  /** YAML errors with line numbers (parse endpoint, FR-014). */
  readonly yamlErrors: YamlError[]

  constructor(status: number, message: string, issues: Issue[] = [], yamlErrors: YamlError[] = []) {
    super(message)
    this.status = status
    this.issues = issues
    this.yamlErrors = yamlErrors
  }
}

interface ValidationDetail {
  loc: (string | number)[]
  msg: string
  type?: string
  line?: number | null
}

async function request<T>(method: string, url: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, {
    method,
    signal,
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (response.status === 204) return undefined as T
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = data?.detail
    if (response.status === 422 && Array.isArray(detail) && detail.some((d: ValidationDetail) => d.type === 'yaml_error')) {
      const errors = (detail as ValidationDetail[]).map((d) => ({ line: d.line ?? null, msg: d.msg }))
      throw new ApiError(422, 'The YAML contains errors.', [], errors)
    }
    if (response.status === 422 && Array.isArray(detail)) {
      // Drop the leading "body" segment so paths match the form model.
      const issues = (detail as ValidationDetail[]).map((d) => ({
        loc: d.loc[0] === 'body' ? d.loc.slice(1) : d.loc,
        msg: d.msg,
      }))
      throw new ApiError(422, 'Please correct the highlighted fields.', issues)
    }
    throw new ApiError(response.status, typeof detail === 'string' ? detail : response.statusText)
  }
  return data as T
}

const BASE = '/api/configurations'

export const api = {
  list: () => request<ConfigurationSummary[]>('GET', BASE),
  get: (id: string) => request<StoredConfiguration>('GET', `${BASE}/${id}`),
  create: (config: Configuration) => request<StoredConfiguration>('POST', BASE, config),
  update: (id: string, config: Configuration, revision: string) =>
    request<StoredConfiguration>('PUT', `${BASE}/${id}`, { ...config, revision }),
  remove: (id: string) => request<void>('DELETE', `${BASE}/${id}`),
  duplicate: (id: string) => request<StoredConfiguration>('POST', `${BASE}/${id}/duplicate`),
  preview: (config: Configuration, signal?: AbortSignal) =>
    request<PreviewResponse>('POST', '/api/preview', config, signal),
  parse: (configuration: Configuration, file: FileName, content: string) =>
    request<ParseResponse>('POST', '/api/parse', { configuration, file, content }),
  defaults: () => request<Defaults>('GET', '/api/defaults'),
  imageUrl: (id: string, format: ImageFormat) => `${BASE}/${id}/image?format=${format}`,
}

export type ImageFormat = 'iso' | 'raw' | 'qcow2'
