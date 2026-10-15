<script setup lang="ts">
// A collapsible form section with help text and a link to the cloud-init docs (FR-004, NFR-013).
import { ExternalLink } from '@lucide/vue'
import type { Component } from 'vue'

defineProps<{
  value: string
  title: string
  icon?: Component
  summary?: string
  help: string
  docs?: string
  errorCount?: number
  /** FR-014: hint that parts of this section are kept as YAML only. */
  notice?: string
}>()
</script>

<template>
  <v-expansion-panel :value="value" :id="`section-${value}`">
    <v-expansion-panel-title>
      <div class="d-flex align-center ga-3 w-100">
        <span v-if="icon" class="section-icon" aria-hidden="true"><component :is="icon" :size="18" /></span>
        <span class="text-subtitle-1 font-weight-bold">{{ title }}</span>
        <span v-if="summary" class="text-body-2 text-medium-emphasis text-truncate">{{ summary }}</span>
        <v-spacer />
        <v-chip v-if="errorCount" color="error" size="small" variant="flat" class="mr-2">
          {{ errorCount }} {{ errorCount === 1 ? 'error' : 'errors' }}
        </v-chip>
      </div>
    </v-expansion-panel-title>
    <v-expansion-panel-text>
      <p class="text-body-2 text-medium-emphasis mb-4">
        {{ help }}
        <a v-if="docs" :href="docs" target="_blank" rel="noopener noreferrer" class="docs-link">
          cloud-init documentation<ExternalLink :size="14" class="ml-1" aria-hidden="true" />
        </a>
      </p>
      <v-alert v-if="notice" type="info" variant="tonal" density="compact" class="mb-4">{{ notice }}</v-alert>
      <slot />
    </v-expansion-panel-text>
  </v-expansion-panel>
</template>

<style scoped>
.section-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.12);
  flex: none;
}
.docs-link {
  color: rgb(var(--v-theme-primary));
  display: inline-flex;
  align-items: center;
}
</style>
