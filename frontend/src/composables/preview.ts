// FR-013: live preview, rendered by the backend, debounced.
import { type Ref, onBeforeUnmount, ref, watch } from 'vue'
import { ApiError, api } from '../api/client'
import type { Configuration, FileName, Issue, SchemaIssue } from '../api/types'

/** Delay after the last change; well below the 1 s required by FR-013. */
export const PREVIEW_DEBOUNCE_MS = 300

export function usePreview(form: Ref<Configuration | null>, delay = PREVIEW_DEBOUNCE_MS) {
  const files = ref<Record<FileName, string | null> | null>(null)
  const warnings = ref<Issue[]>([])
  const schemaIssues = ref<SchemaIssue[]>([])
  const errors = ref<Issue[]>([])
  const failure = ref<string | null>(null)
  const loading = ref(false)

  let timer: ReturnType<typeof setTimeout> | undefined
  let controller: AbortController | undefined

  async function refresh() {
    if (!form.value) return
    controller?.abort()
    controller = new AbortController()
    loading.value = true
    try {
      const result = await api.preview(form.value, controller.signal)
      files.value = result.files
      warnings.value = result.warnings
      schemaIssues.value = result.schema_issues
      errors.value = []
      failure.value = null
    } catch (error) {
      if ((error as Error).name === 'AbortError') return
      if (error instanceof ApiError && error.status === 422) {
        // Keep the last valid files visible; show what needs fixing.
        errors.value = error.issues
        failure.value = null
      } else {
        failure.value = `Preview unavailable: ${(error as Error).message}`
      }
    } finally {
      loading.value = false
    }
  }

  function schedule() {
    clearTimeout(timer)
    timer = setTimeout(refresh, delay)
  }

  watch(form, schedule, { deep: true, immediate: true })
  onBeforeUnmount(() => {
    clearTimeout(timer)
    controller?.abort()
  })

  return { files, warnings, schemaIssues, errors, failure, loading, refresh }
}
