<script setup lang="ts">
// FR-014: settings the form does not cover, kept unchanged and edited as YAML only.
import { FilePenLine } from '@lucide/vue'
import { computed } from 'vue'
import type { Additional, FileName } from '../../api/types'

const additional = defineModel<Additional>({ required: true })
const emit = defineEmits<{ edit: [file: FileName] }>()

const groups = computed(() => [
  { file: 'user-data' as FileName, part: 'user_data' as const, keys: Object.keys(additional.value.user_data) },
  { file: 'meta-data' as FileName, part: 'meta_data' as const, keys: Object.keys(additional.value.meta_data) },
  { file: 'network-config' as FileName, part: 'network' as const, keys: Object.keys(additional.value.network) },
])

function remove(part: 'user_data' | 'meta_data' | 'network', key: string) {
  const copy = { ...additional.value[part] }
  delete copy[key]
  additional.value[part] = copy
}
</script>

<template>
  <p v-if="!groups.some((g) => g.keys.length) && !additional.vendor_data" class="text-body-2 text-medium-emphasis mb-3">
    No additional settings. Add further cloud-init modules (e.g. <code>ntp</code>, <code>apt</code>) with "Edit as YAML".
  </p>
  <div v-for="group in groups.filter((g) => g.keys.length)" :key="group.file" class="mb-3">
    <div class="d-flex align-center ga-2 mb-1">
      <span class="text-subtitle-2">{{ group.file }}</span>
      <v-btn size="x-small" variant="text" :prepend-icon="FilePenLine" @click="emit('edit', group.file)">Edit as YAML</v-btn>
    </div>
    <div class="d-flex flex-wrap ga-1">
      <v-chip
        v-for="key in group.keys"
        :key="key"
        size="small"
        closable
        :close-label="`Remove ${key}`"
        @click:close="remove(group.part, key)"
      >
        {{ key }}
      </v-chip>
    </div>
  </div>
  <div v-if="additional.vendor_data" class="d-flex align-center ga-2">
    <span class="text-subtitle-2">vendor-data</span>
    <v-btn size="x-small" variant="text" :prepend-icon="FilePenLine" @click="emit('edit', 'vendor-data')">Edit as YAML</v-btn>
    <v-btn size="x-small" variant="text" color="error" @click="additional.vendor_data = null">Remove vendor-data</v-btn>
  </div>
</template>
