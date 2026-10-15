<script setup lang="ts">
// Code editor with line numbers, syntax highlighting and error markers (FR-008, FR-013, FR-014).
// Follows the active light/dark theme (FR-016).
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands'
import { json } from '@codemirror/lang-json'
import { yaml } from '@codemirror/lang-yaml'
import {
  HighlightStyle,
  StreamLanguage,
  bracketMatching,
  defaultHighlightStyle,
  syntaxHighlighting,
} from '@codemirror/language'
import { properties } from '@codemirror/legacy-modes/mode/properties'
import { python } from '@codemirror/legacy-modes/mode/python'
import { shell } from '@codemirror/legacy-modes/mode/shell'
import { toml } from '@codemirror/legacy-modes/mode/toml'
import { type Diagnostic, lintGutter, setDiagnostics } from '@codemirror/lint'
import { Compartment, EditorState, type Extension } from '@codemirror/state'
import { oneDarkHighlightStyle, oneDarkTheme } from '@codemirror/theme-one-dark'
import {
  EditorView,
  drawSelection,
  highlightActiveLine,
  highlightActiveLineGutter,
  keymap,
  lineNumbers,
} from '@codemirror/view'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useTheme } from 'vuetify'

export type Language = 'yaml' | 'json' | 'shell' | 'properties' | 'toml' | 'python' | 'text'

export interface LineDiagnostic {
  line: number // 1-based
  message: string
  severity?: 'error' | 'warning'
}

const props = withDefaults(
  defineProps<{
    modelValue: string
    language?: Language
    readonly?: boolean
    diagnostics?: LineDiagnostic[]
    minHeight?: string
    maxHeight?: string
    label?: string
    id?: string
  }>(),
  {
    language: 'text',
    readonly: false,
    diagnostics: () => [],
    minHeight: '8rem',
    maxHeight: '32rem',
    label: undefined,
    id: undefined,
  },
)
const emit = defineEmits<{ 'update:modelValue': [value: string]; blur: [] }>()

const host = ref<HTMLElement>()
const vuetifyTheme = useTheme()
const dark = computed(() => vuetifyTheme.global.current.value.dark)

const languageCompartment = new Compartment()
const themeCompartment = new Compartment()
const readonlyCompartment = new Compartment()
let view: EditorView | undefined

function languageExtension(language: Language): Extension {
  switch (language) {
    case 'yaml':
      return yaml()
    case 'json':
      return json()
    case 'shell':
      return StreamLanguage.define(shell)
    case 'properties':
      return StreamLanguage.define(properties)
    case 'toml':
      return StreamLanguage.define(toml)
    case 'python':
      return StreamLanguage.define(python)
    default:
      return []
  }
}

const lightHighlight = HighlightStyle.define(defaultHighlightStyle.specs)
// One Dark's gray (comments, gutter) is below 4.5:1 contrast; use a brighter gray (NFR-013).
const ONE_DARK_GRAY = '#7d8799'
const READABLE_GRAY = '#a3abb9'
const darkHighlight = HighlightStyle.define(
  oneDarkHighlightStyle.specs.map((spec) => (spec.color === ONE_DARK_GRAY ? { ...spec, color: READABLE_GRAY } : spec)),
)

function themeExtension(isDark: boolean): Extension {
  const base = EditorView.theme(
    {
      '&': { minHeight: props.minHeight, maxHeight: props.maxHeight, fontSize: '0.875rem' },
      '.cm-scroller': { fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace' },
      '&.cm-focused': { outline: '2px solid rgb(var(--v-theme-primary))' },
    },
    { dark: isDark },
  )
  const darkGutter = EditorView.theme(
    { '.cm-gutters': { color: READABLE_GRAY }, '.cm-activeLineGutter': { color: '#d7dae0' } },
    { dark: true },
  )
  return isDark
    ? [base, darkGutter, oneDarkTheme, syntaxHighlighting(darkHighlight)]
    : [base, syntaxHighlighting(lightHighlight)]
}

function readonlyExtension(readonly: boolean): Extension {
  return [EditorState.readOnly.of(readonly), EditorView.editable.of(!readonly)]
}

function toDiagnostics(state: EditorState, items: LineDiagnostic[]): Diagnostic[] {
  return items.map((item) => {
    const line = state.doc.line(Math.min(Math.max(item.line, 1), state.doc.lines))
    return { from: line.from, to: line.to, message: item.message, severity: item.severity ?? 'error' }
  })
}

onMounted(() => {
  view = new EditorView({
    parent: host.value!,
    state: EditorState.create({
      doc: props.modelValue,
      extensions: [
        lineNumbers(),
        highlightActiveLineGutter(),
        highlightActiveLine(),
        drawSelection(),
        history(),
        bracketMatching(),
        lintGutter(),
        keymap.of([...defaultKeymap, ...historyKeymap, indentWithTab]),
        EditorView.lineWrapping,
        languageCompartment.of(languageExtension(props.language)),
        themeCompartment.of(themeExtension(dark.value)),
        readonlyCompartment.of(readonlyExtension(props.readonly)),
        EditorView.contentAttributes.of({
          ...(props.label ? { 'aria-label': props.label } : {}),
          ...(props.id ? { id: props.id } : {}),
        }),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) emit('update:modelValue', update.state.doc.toString())
        }),
        EditorView.domEventHandlers({ blur: () => emit('blur') }),
      ],
    }),
  })
  applyDiagnostics()
})

onBeforeUnmount(() => view?.destroy())

watch(
  () => props.modelValue,
  (value) => {
    if (view && value !== view.state.doc.toString()) {
      view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: value } })
      applyDiagnostics()
    }
  },
)
watch(
  () => props.language,
  (language) => view?.dispatch({ effects: languageCompartment.reconfigure(languageExtension(language)) }),
)
watch(dark, (isDark) => view?.dispatch({ effects: themeCompartment.reconfigure(themeExtension(isDark)) }))
watch(
  () => props.readonly,
  (readonly) => view?.dispatch({ effects: readonlyCompartment.reconfigure(readonlyExtension(readonly)) }),
)
watch(() => props.diagnostics, applyDiagnostics, { deep: true })

function applyDiagnostics() {
  if (view) view.dispatch(setDiagnostics(view.state, toDiagnostics(view.state, props.diagnostics)))
}

defineExpose({ focus: () => view?.focus() })
</script>

<template>
  <div ref="host" class="code-editor" />
</template>

<style scoped>
.code-editor {
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 4px;
  overflow: hidden;
}
.code-editor :deep(.cm-editor) {
  background: rgb(var(--v-theme-surface));
}
</style>
