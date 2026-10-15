<script setup lang="ts">
// Layout: permanent navigation sidebar (section 7.2) and the routed view.
import { BookOpen, LayoutList, Moon, Plus, Sun } from '@lucide/vue'
import { computed } from 'vue'
import AppLogo from './components/AppLogo.vue'
import { useThemeSwitch } from './composables/theme'

const { theme, toggle } = useThemeSwitch()
const dark = computed(() => theme.global.current.value.dark)
</script>

<template>
  <v-app>
    <v-navigation-drawer permanent width="248" border="0" class="sidebar" aria-label="Main navigation">
      <router-link to="/" class="brand d-flex align-center ga-3 px-5 pt-6 pb-8" aria-label="Home">
        <AppLogo :size="38" />
        <div class="brand-text">
          <div class="brand-title">cloudinit</div>
          <div class="brand-subtitle">NoCloud configurator</div>
        </div>
      </router-link>

      <v-list nav density="comfortable" class="px-3">
        <v-list-subheader class="nav-heading">Seed drives</v-list-subheader>
        <v-list-item :prepend-icon="LayoutList" title="Configurations" to="/" exact rounded="lg" />
        <v-list-item :prepend-icon="Plus" title="New configuration" to="/configurations/new" rounded="lg" />
        <v-list-subheader class="nav-heading mt-4">Developer</v-list-subheader>
        <v-list-item :prepend-icon="BookOpen" title="API docs" href="/docs" target="_blank" rel="noopener" rounded="lg" />
      </v-list>

      <template #append>
        <v-list nav density="comfortable" class="px-3 pb-4">
          <v-list-item
            :prepend-icon="dark ? Sun : Moon"
            :title="dark ? 'Light mode' : 'Dark mode'"
            :aria-label="dark ? 'Switch to light theme' : 'Switch to dark theme'"
            role="button"
            rounded="lg"
            @click="toggle"
          />
        </v-list>
      </template>
    </v-navigation-drawer>

    <v-main>
      <router-view />
    </v-main>
  </v-app>
</template>

<style>
:root {
  --app-font: 'Inter Variable', 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
}
.v-application,
.v-application .text-h1,
.v-application .text-h2,
.v-application .text-h3,
.v-application .text-h4,
.v-application .text-h5,
.v-application .text-h6,
.v-application .text-subtitle-1,
.v-application .text-subtitle-2,
.v-application .text-body-1,
.v-application .text-body-2,
.v-application .text-caption,
.v-application .text-button {
  font-family: var(--app-font) !important;
  letter-spacing: normal !important;
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
/* Page header used by the views. */
.page-title {
  font-size: 1.75rem;
  font-weight: 700;
  letter-spacing: -0.01em;
}
</style>

<style scoped>
.sidebar {
  background: rgb(var(--v-theme-background)) !important;
}
.brand {
  text-decoration: none;
  color: inherit;
}
.brand-title {
  font-weight: 800;
  font-size: 1.15rem;
  line-height: 1.1;
}
.brand-subtitle {
  font-size: 0.75rem;
  opacity: 0.75;
}
.nav-heading {
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.08em !important;
  text-transform: uppercase;
}
.sidebar :deep(.v-list-item--active) {
  background: rgb(var(--v-theme-surface-variant));
  color: rgb(var(--v-theme-on-surface));
}
.sidebar :deep(.v-list-item--active .v-list-item__overlay) {
  opacity: 0;
}
.sidebar :deep(.v-list-item--active .v-icon) {
  color: rgb(var(--v-theme-primary));
}
</style>
