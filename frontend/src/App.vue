<script setup lang="ts">
import { BookOpen, Moon, Sun } from '@lucide/vue'
import { computed } from 'vue'
import { useThemeSwitch } from './composables/theme'

const { theme, toggle } = useThemeSwitch()
const dark = computed(() => theme.global.current.value.dark)
</script>

<template>
  <v-app>
    <v-app-bar density="compact" flat border="b">
      <v-app-bar-title>
        <router-link to="/" class="home-link">cloudinit-nocloud-configurator</router-link>
      </v-app-bar-title>
      <v-btn :prepend-icon="BookOpen" variant="text" href="/docs" target="_blank" rel="noopener">API docs</v-btn>
      <v-btn
        :icon="dark ? Sun : Moon"
        variant="text"
        :aria-label="dark ? 'Switch to light theme' : 'Switch to dark theme'"
        :title="dark ? 'Switch to light theme' : 'Switch to dark theme'"
        @click="toggle"
      />
    </v-app-bar>
    <v-main>
      <router-view />
    </v-main>
  </v-app>
</template>

<style>
.home-link {
  color: inherit;
  text-decoration: none;
  font-weight: 600;
}
.v-icon svg,
.v-btn svg {
  width: 1em;
  height: 1em;
}
/* Warnings shown as field messages (FR-006 to FR-012). */
.has-warning .v-messages {
  color: rgb(var(--v-theme-warning));
  opacity: 1;
}
</style>
