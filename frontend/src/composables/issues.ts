// Field-level errors and warnings for the editor form (FR-004, FR-013).
//
// The backend validates (single source of truth); this module only decides where and
// when its messages are shown. An error appears at its field once the field has been
// left (blur) or after a save attempt.
import { type InjectionKey, computed, inject, nextTick, provide, reactive, ref } from 'vue'
import type { Issue } from '../api/types'

export type Path = (string | number)[]

export const pathKey = (path: Path) => path.join('.')

/** DOM id of the input for a model path, e.g. "field-basics-hostname". */
export const fieldId = (path: Path) => `field-${path.join('-')}`

export interface IssueState {
  setErrors(errors: Issue[]): void
  setWarnings(warnings: Issue[]): void
  errors: Readonly<{ value: Issue[] }>
  warnings: Readonly<{ value: Issue[] }>
  /** Messages for exactly this path (visible ones only for errors). */
  errorsAt(path: Path): string[]
  warningsAt(path: Path): string[]
  /** Visible errors of the entries of a list field, e.g. packages.3 -> { index: 3, msg }. */
  itemErrorsAt(path: Path): { index: number; msg: string }[]
  /** Number of errors in a section (shown in the section header). */
  countIn(section: string): number
  touch(path: Path): void
  revealAll(): void
  /** Open the section and focus the field of an issue (FR-013). */
  focus(path: Path): Promise<void>
}

const KEY: InjectionKey<IssueState> = Symbol('issues')

export function createIssueState(openSection: (section: string) => void): IssueState {
  const errors = ref<Issue[]>([])
  const warnings = ref<Issue[]>([])
  const touched = reactive(new Set<string>())
  const showAll = ref(false)

  const errorsByKey = computed(() => groupByKey(errors.value))
  const warningsByKey = computed(() => groupByKey(warnings.value))

  async function focus(path: Path) {
    if (path.length) openSection(String(path[0]))
    // Wait for the expansion panel to render its content.
    await nextTick()
    await new Promise((resolve) => setTimeout(resolve, 50))
    let element: HTMLElement | null = null
    for (let length = path.length; length > 0 && !element; length--) {
      element = document.getElementById(fieldId(path.slice(0, length)))
    }
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' })
      element.focus({ preventScroll: true })
    }
    touched.add(pathKey(path))
  }

  return {
    errors,
    warnings,
    setErrors: (value) => (errors.value = value),
    setWarnings: (value) => (warnings.value = value),
    errorsAt: (path) => {
      const key = pathKey(path)
      return showAll.value || touched.has(key) ? (errorsByKey.value.get(key) ?? []) : []
    },
    warningsAt: (path) => warningsByKey.value.get(pathKey(path)) ?? [],
    itemErrorsAt: (path) => {
      if (!(showAll.value || touched.has(pathKey(path)))) return []
      return errors.value
        .filter(
          (issue) =>
            issue.loc.length === path.length + 1 &&
            typeof issue.loc[path.length] === 'number' &&
            pathKey(issue.loc.slice(0, path.length)) === pathKey(path),
        )
        .map((issue) => ({ index: issue.loc[path.length] as number, msg: issue.msg }))
    },
    countIn: (section) => errors.value.filter((issue) => issue.loc[0] === section).length,
    touch: (path) => touched.add(pathKey(path)),
    revealAll: () => (showAll.value = true),
    focus,
  }
}

function groupByKey(issues: Issue[]): Map<string, string[]> {
  const map = new Map<string, string[]>()
  for (const issue of issues) {
    const key = pathKey(issue.loc)
    map.set(key, [...(map.get(key) ?? []), issue.msg])
  }
  return map
}

export function provideIssues(state: IssueState) {
  provide(KEY, state)
}

export function useIssues(): IssueState {
  const state = inject(KEY)
  if (!state) throw new Error('useIssues() called outside of the editor')
  return state
}

/** Bindings for one form field: id, error and warning messages, blur handling. */
export function useField(path: () => Path, state?: IssueState) {
  const issues = state ?? useIssues()
  return computed(() => {
    const current = path()
    return {
      id: fieldId(current),
      'error-messages': issues.errorsAt(current),
      messages: issues.warningsAt(current),
      class: issues.warningsAt(current).length ? 'has-warning' : undefined,
      onBlur: () => issues.touch(current),
    }
  })
}

/**
 * Field bindings for dynamic paths (list entries). Call `useBinder()` in setup and
 * `bind(path)` in the template: `v-bind="bind(['network', 'ethernets', i, 'name'])"`.
 */
export function useBinder() {
  const issues = useIssues()
  return (path: Path) => ({
    id: fieldId(path),
    'error-messages': issues.errorsAt(path),
    messages: issues.warningsAt(path),
    class: issues.warningsAt(path).length ? 'has-warning' : undefined,
    onBlur: () => issues.touch(path),
  })
}
