<script setup lang="ts">
// FR-013: read-only preview of the generated files in tabs, with copy, download,
// secret masking and clickable validation messages.
import { Copy, Download, Eye, EyeOff } from '@lucide/vue'
import { computed, ref, watch } from 'vue'
import type { FileName, Issue } from '../api/types'
import CodeEditor from './CodeEditor.vue'
import { maskSecrets } from './secrets'

const props = defineProps<{
  files: Record<FileName, string | null> | null
  errors: Issue[]
  warnings: Issue[]
  failure: string | null
  loading: boolean
}>()
const emit = defineEmits<{ focus: [path: Issue['loc']] }>()

const FILE_NAMES: FileName[] = ['user-data', 'meta-data', 'network-config', 'vendor-data']

const active = ref<FileName>('user-data')
const masked = ref(true)
const copied = ref(false)

const available = (name: FileName) => props.files?.[name] != null

// Switch away from a tab whose file disappeared.
watch(
  () => props.files,
  () => {
    if (props.files && !available(active.value)) active.value = 'user-data'
  },
)

const content = computed(() => {
  const text = props.files?.[active.value] ?? ''
  return masked.value ? maskSecrets(text) : text
})

async function copy() {
  // The clipboard always receives the real content (FR-013).
  await navigator.clipboard.writeText(props.files?.[active.value] ?? '')
  copied.value = true
  setTimeout(() => (copied.value = false), 1500)
}

function download() {
  const blob = new Blob([props.files?.[active.value] ?? ''], { type: 'text/yaml' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = active.value
  link.click()
  URL.revokeObjectURL(url)
}

const label = (loc: Issue['loc']) => loc.map((part) => (typeof part === 'number' ? `#${part + 1}` : part)).join(' › ')
</script>

<template>
  <v-card variant="outlined" class="yaml-preview">
    <div class="d-flex align-center flex-wrap">
      <v-tabs v-model="active" density="compact" color="primary">
        <v-tab v-for="name in FILE_NAMES" :key="name" :value="name" :disabled="!available(name)">
          {{ name }}
        </v-tab>
      </v-tabs>
      <v-spacer />
      <v-progress-circular v-if="loading" indeterminate size="18" width="2" class="mr-2" aria-label="Updating preview" />
      <v-btn
        variant="text"
        size="small"
        :prepend-icon="masked ? EyeOff : Eye"
        :aria-pressed="masked"
        @click="masked = !masked"
      >
        {{ masked ? 'Secrets masked' : 'Secrets shown' }}
      </v-btn>
      <v-btn variant="text" size="small" :prepend-icon="Copy" :disabled="!files" @click="copy">
        {{ copied ? 'Copied' : 'Copy' }}
      </v-btn>
      <v-btn variant="text" size="small" :prepend-icon="Download" :disabled="!files" @click="download">
        Download file
      </v-btn>
      <slot name="actions" :file="active" />
    </div>

    <v-alert v-if="failure" type="error" variant="tonal" density="compact" class="ma-2">{{ failure }}</v-alert>

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

    <slot name="editor" :file="active">
      <CodeEditor :model-value="content" language="yaml" readonly :label="`Preview of ${active}`" max-height="40rem" />
    </slot>
  </v-card>
</template>

<style scoped>
/* Full-strength message text for WCAG AA contrast (NFR-013). */
.yaml-preview :deep(.v-list-item-subtitle) {
  opacity: 1;
}
</style>
