<script setup lang="ts">
// FR-013: preview of the generated files in tabs, with copy, download, secret masking
// and clickable validation messages. FR-014: each file can be edited as YAML.
import { Check, Copy, Download, Eye, EyeOff, FilePenLine, Undo2 } from '@lucide/vue'
import { computed, ref, watch } from 'vue'
import type { FileName, Issue, SchemaIssue, YamlError } from '../api/types'
import CodeEditor, { type LineDiagnostic } from './CodeEditor.vue'
import { maskSecrets } from './secrets'

const props = defineProps<{
  files: Record<FileName, string | null> | null
  errors: Issue[]
  warnings: Issue[]
  schemaIssues: SchemaIssue[]
  failure: string | null
  loading: boolean
  /** The file currently edited as YAML, if any (FR-014). */
  editing: FileName | null
  yamlErrors: YamlError[]
  notices: string[]
  applying: boolean
}>()
const emit = defineEmits<{
  focus: [path: Issue['loc']]
  edit: [file: FileName]
  apply: [text: string]
  discard: []
}>()

const FILE_NAMES: FileName[] = ['user-data', 'meta-data', 'network-config', 'vendor-data']

const active = ref<FileName>('user-data')
const masked = ref(true)
const copied = ref(false)
const editText = ref('')

const available = (name: FileName) => props.files?.[name] != null

watch(
  () => props.editing,
  (file) => {
    if (file) {
      active.value = file
      editText.value = props.files?.[file] ?? (file === 'vendor-data' ? '#cloud-config\n' : '')
    }
  },
)

const content = computed(() => {
  const text = props.files?.[active.value] ?? ''
  return masked.value ? maskSecrets(text) : text
})

/** FR-014: comments (other than the #cloud-config header) are lost when applying. */
const hasComments = computed(() =>
  editText.value
    .split('\n')
    .some((line, index) => /(^|\s)#/.test(line) && !(index === 0 && line.startsWith('#cloud-config'))),
)

const activeSchemaIssues = computed(() => props.schemaIssues.filter((issue) => issue.file === active.value))

const diagnostics = computed<LineDiagnostic[]>(() => [
  ...(props.editing
    ? props.yamlErrors.filter((e) => e.line).map((e) => ({ line: e.line!, message: e.msg, severity: 'error' as const }))
    : []),
  ...activeSchemaIssues.value
    .filter((issue) => issue.line)
    .map((issue) => ({ line: issue.line!, message: `cloud-init schema: ${issue.msg}`, severity: 'warning' as const })),
])

async function copy() {
  // The clipboard always receives the real content (FR-013).
  await navigator.clipboard.writeText(props.editing ? editText.value : (props.files?.[active.value] ?? ''))
  copied.value = true
  setTimeout(() => (copied.value = false), 1500)
}

function download() {
  const text = props.editing ? editText.value : (props.files?.[active.value] ?? '')
  const blob = new Blob([text], { type: 'text/yaml' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = active.value
  link.click()
  URL.revokeObjectURL(url)
}

const label = (loc: Issue['loc']) =>
  loc.map((part) => (typeof part === 'number' ? `#${part + 1}` : part)).join(' › ')
const schemaLabel = (issue: SchemaIssue) =>
  `${issue.file}${issue.line ? `, line ${issue.line}` : ''}${issue.path.length ? ` (${issue.path.join('.')})` : ''}`

defineExpose({ editText })
</script>

<template>
  <v-card border class="yaml-preview" title="Preview" subtitle="Generated NoCloud files">
    <div class="d-flex align-center flex-wrap">
      <v-tabs v-model="active" density="compact" color="primary">
        <v-tab
          v-for="name in FILE_NAMES"
          :key="name"
          :value="name"
          :disabled="editing ? editing !== name : !available(name)"
        >
          {{ name }}
        </v-tab>
      </v-tabs>
      <v-spacer />
      <v-progress-circular v-if="loading" indeterminate size="18" width="2" class="mr-2" aria-label="Updating preview" />
      <template v-if="!editing">
        <v-btn variant="text" size="small" :prepend-icon="masked ? EyeOff : Eye" :aria-pressed="masked" @click="masked = !masked">
          {{ masked ? 'Secrets masked' : 'Secrets shown' }}
        </v-btn>
        <v-menu>
          <template #activator="{ props: menuProps }">
            <v-btn v-bind="menuProps" variant="text" size="small" :prepend-icon="FilePenLine" append-icon="$dropdown">
              Edit as YAML
            </v-btn>
          </template>
          <v-list density="compact" aria-label="File to edit">
            <v-list-item
              v-for="name in FILE_NAMES"
              :key="name"
              :title="available(name) ? `Edit ${name}` : `Add ${name}`"
              @click="emit('edit', name)"
            />
          </v-list>
        </v-menu>
      </template>
      <v-btn variant="text" size="small" :prepend-icon="Copy" :disabled="!files" @click="copy">
        {{ copied ? 'Copied' : 'Copy' }}
      </v-btn>
      <v-btn variant="text" size="small" :prepend-icon="Download" :disabled="!files" @click="download">
        Download file
      </v-btn>
    </div>

    <v-alert v-if="failure" type="error" variant="tonal" density="compact" class="ma-2">{{ failure }}</v-alert>

    <template v-if="editing">
      <v-alert type="info" variant="tonal" density="compact" class="ma-2" :icon="FilePenLine">
        Editing <strong>{{ editing }}</strong> as YAML. The form is locked until you apply or discard the changes.
        Settings the form does not support are kept as additional settings.
        <template #append>
          <v-btn variant="text" size="small" :prepend-icon="Undo2" @click="emit('discard')">Discard YAML changes</v-btn>
          <v-btn
            color="primary"
            variant="flat"
            size="small"
            :prepend-icon="Check"
            :loading="applying"
            @click="emit('apply', editText)"
          >
            Apply to form
          </v-btn>
        </template>
      </v-alert>
      <v-alert v-if="hasComments" type="warning" variant="tonal" density="compact" class="mx-2 mb-2">
        Comments are not preserved: they are removed when the YAML is applied.
      </v-alert>
      <v-list v-if="yamlErrors.length" density="compact" class="py-0" aria-label="YAML errors">
        <v-list-item
          v-for="(error, index) in yamlErrors"
          :key="index"
          base-color="error"
          prepend-icon="$error"
          :title="error.line ? `Line ${error.line}` : 'YAML'"
          :subtitle="error.msg"
        />
      </v-list>
    </template>

    <template v-else>
      <v-alert
        v-for="(notice, index) in notices"
        :key="`n${index}`"
        type="info"
        variant="tonal"
        density="compact"
        class="mx-2 mt-2"
      >
        {{ notice }}
      </v-alert>
      <v-list v-if="errors.length || warnings.length" density="compact" class="py-0" aria-label="Validation messages">
        <v-list-item
          v-for="(issue, index) in errors"
          :key="`e${index}`"
          base-color="error"
          prepend-icon="$error"
          :title="label(issue.loc)"
          :subtitle="issue.msg"
          @click="emit('focus', issue.loc)"
        />
        <v-list-item
          v-for="(issue, index) in warnings"
          :key="`w${index}`"
          base-color="warning"
          prepend-icon="$warning"
          :title="label(issue.loc)"
          :subtitle="issue.msg"
          @click="emit('focus', issue.loc)"
        />
      </v-list>
    </template>
    <v-list v-if="schemaIssues.length" density="compact" class="py-0" aria-label="cloud-init schema hints">
      <v-list-item
        v-for="(issue, index) in schemaIssues"
        :key="`s${index}`"
        base-color="warning"
        prepend-icon="$info"
        :title="`cloud-init schema: ${schemaLabel(issue)}`"
        :subtitle="issue.msg"
        @click="active = issue.file"
      />
    </v-list>

    <CodeEditor
      v-if="editing"
      v-model="editText"
      language="yaml"
      :diagnostics="diagnostics"
      :label="`Edit ${editing}`"
      min-height="16rem"
      max-height="40rem"
    />
    <template v-else>
      <CodeEditor
        :model-value="content"
        language="yaml"
        readonly
        :diagnostics="diagnostics"
        :label="`Preview of ${active}`"
        max-height="40rem"
      />
    </template>
  </v-card>
</template>

<style scoped>
/* Full-strength message text for WCAG AA contrast (NFR-013). */
.yaml-preview :deep(.v-list-item-subtitle) {
  opacity: 1;
}
</style>
