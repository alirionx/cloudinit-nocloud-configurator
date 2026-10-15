<script setup lang="ts">
// A list entry with move, duplicate and delete actions (FR-008 and other list sections).
import { ArrowDown, ArrowUp, CopyPlus, Trash2 } from '@lucide/vue'

defineProps<{ title: string; index: number; count: number; duplicable?: boolean }>()
const emit = defineEmits<{ move: [to: number]; duplicate: []; remove: [] }>()
</script>

<template>
  <v-card variant="outlined" class="mb-3 item-card">
    <div class="d-flex align-center px-3 py-1 item-header">
      <slot name="handle" />
      <span class="text-subtitle-2 text-truncate">{{ title }}</span>
      <v-spacer />
      <v-btn
        :icon="ArrowUp"
        size="small"
        variant="text"
        :disabled="index === 0"
        :aria-label="`Move ${title} up`"
        @click="emit('move', index - 1)"
      />
      <v-btn
        :icon="ArrowDown"
        size="small"
        variant="text"
        :disabled="index === count - 1"
        :aria-label="`Move ${title} down`"
        @click="emit('move', index + 1)"
      />
      <v-btn
        v-if="duplicable"
        :icon="CopyPlus"
        size="small"
        variant="text"
        :aria-label="`Duplicate ${title}`"
        @click="emit('duplicate')"
      />
      <v-btn :icon="Trash2" size="small" variant="text" color="error" :aria-label="`Remove ${title}`" @click="emit('remove')" />
    </div>
    <v-divider />
    <div class="pa-3"><slot /></div>
  </v-card>
</template>

<style scoped>
.item-header {
  background: rgb(var(--v-theme-surface-variant));
}
</style>
