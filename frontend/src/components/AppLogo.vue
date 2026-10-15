<script setup lang="ts">
// Logo: a disc (the seed drive) in the accent color.
defineProps<{ size?: number }>()
</script>

<template>
  <svg :width="size ?? 36" :height="size ?? 36" viewBox="0 0 32 32" aria-hidden="true">
    <rect width="32" height="32" rx="9" fill="rgb(var(--v-theme-primary))" />
    <circle cx="16" cy="16" r="9" fill="none" stroke="rgb(var(--v-theme-on-primary))" stroke-width="3" />
    <circle cx="16" cy="16" r="2.6" fill="rgb(var(--v-theme-on-primary))" />
    <path d="M16 7a9 9 0 0 1 9 9" fill="none" stroke="rgb(var(--v-theme-on-primary))" stroke-width="3" stroke-linecap="round" opacity="0.45" />
  </svg>
</template>
