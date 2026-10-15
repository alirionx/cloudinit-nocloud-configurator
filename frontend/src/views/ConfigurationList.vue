<script setup lang="ts">
// UI-02 / FR-015: list of saved configurations with search, sorting and actions.
import { Copy, Pencil, Plus, Search, Trash2 } from '@lucide/vue'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError, api } from '../api/client'
import type { ConfigurationSummary } from '../api/types'

const router = useRouter()

const items = ref<ConfigurationSummary[]>([])
const loading = ref(true)
const loadError = ref<string | null>(null)
const search = ref('')
const message = ref<{ text: string; color: string } | null>(null)

const renaming = ref<ConfigurationSummary | null>(null)
const newName = ref('')
const renameError = ref<string[]>([])
const deleting = ref<ConfigurationSummary | null>(null)

const headers = [
  { title: 'Name', key: 'name', sortable: true },
  { title: 'Hostname', key: 'hostname', sortable: true },
  { title: 'Last modified', key: 'modified_at', sortable: true },
  { title: 'Actions', key: 'actions', sortable: false, align: 'end' as const },
]

async function load() {
  loading.value = true
  try {
    items.value = await api.list()
    loadError.value = null
  } catch (error) {
    loadError.value = `Could not load configurations: ${(error as Error).message}`
  } finally {
    loading.value = false
  }
}
onMounted(load)

/** FR-015: the search field filters by name and hostname. */
function filter(_value: unknown, query: string, item?: { raw: ConfigurationSummary }) {
  if (!item) return false
  const needle = query.trim().toLowerCase()
  return [item.raw.name, item.raw.hostname ?? ''].some((text) => text.toLowerCase().includes(needle))
}

const formatDate = (iso: string) =>
  new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(iso))

function open(id: string) {
  router.push(`/configurations/${id}`)
}

async function duplicate(item: ConfigurationSummary) {
  try {
    const copy = await api.duplicate(item.id)
    open(copy.id)
  } catch (error) {
    message.value = { text: `Duplicating failed: ${(error as Error).message}`, color: 'error' }
  }
}

function startRename(item: ConfigurationSummary) {
  renaming.value = item
  newName.value = item.name
  renameError.value = []
}

async function confirmRename() {
  const item = renaming.value!
  try {
    const current = await api.get(item.id)
    const { id, revision, created_at: _c, modified_at: _m, ...config } = current
    await api.update(id, { ...config, name: newName.value }, revision)
    renaming.value = null
    await load()
  } catch (error) {
    if (error instanceof ApiError && error.status === 422) {
      renameError.value = error.issues.filter((i) => i.loc[0] === 'name').map((i) => i.msg)
    } else {
      renameError.value = [(error as Error).message]
    }
  }
}

async function confirmDelete() {
  const item = deleting.value!
  deleting.value = null
  try {
    await api.remove(item.id)
    message.value = { text: `Deleted "${item.name}".`, color: 'success' }
  } catch (error) {
    message.value = { text: `Deleting failed: ${(error as Error).message}`, color: 'error' }
  }
  await load()
}
</script>

<template>
  <v-container class="page">
    <div class="d-flex align-center flex-wrap ga-3 mb-6">
      <div>
        <h1 class="page-title">Configurations</h1>
        <p class="text-body-2 text-medium-emphasis mt-1">
          {{ items.length }} saved {{ items.length === 1 ? 'configuration' : 'configurations' }} · NoCloud seed drives
        </p>
      </div>
      <v-spacer />
      <v-text-field
        v-model="search"
        :prepend-inner-icon="Search"
        label="Search name or hostname"
        hide-details
        clearable
        style="max-width: 22rem"
      />
      <v-btn color="primary" variant="flat" size="large" :prepend-icon="Plus" to="/configurations/new">
        New configuration
      </v-btn>
    </div>

    <v-alert v-if="loadError" type="error" variant="tonal" class="mb-4">{{ loadError }}</v-alert>

    <v-card class="table-card" border>
    <v-data-table
      :headers="headers"
      :items="items"
      :search="search"
      :custom-filter="filter"
      :loading="loading"
      :sort-by="[{ key: 'modified_at', order: 'desc' }]"
      item-value="id"
      hover
      no-data-text="No configurations yet. Create your first one."
      @click:row="(_event: Event, row: { item: ConfigurationSummary }) => open(row.item.id)"
    >
      <template #[`item.name`]="{ item }">
        <router-link :to="`/configurations/${item.id}`" class="name-link" @click.stop>{{ item.name }}</router-link>
      </template>
      <template #[`item.hostname`]="{ item }">
        <span :class="{ 'text-medium-emphasis': !item.hostname }">{{ item.hostname ?? '—' }}</span>
      </template>
      <template #[`item.modified_at`]="{ item }">{{ formatDate(item.modified_at) }}</template>
      <template #[`item.actions`]="{ item }">
        <div class="d-flex justify-end" @click.stop>
          <v-btn :icon="Pencil" variant="text" size="small" :aria-label="`Rename ${item.name}`" @click="startRename(item)" />
          <v-btn :icon="Copy" variant="text" size="small" color="primary" :aria-label="`Duplicate ${item.name}`" @click="duplicate(item)" />
          <v-btn
            :icon="Trash2"
            variant="text"
            size="small"
            color="secondary"
            :aria-label="`Delete ${item.name}`"
            @click="deleting = item"
          />
        </div>
      </template>
    </v-data-table>
    </v-card>

    <v-dialog :model-value="!!renaming" max-width="460" @update:model-value="renaming = null">
      <v-card title="Rename configuration">
        <v-card-text>
          <v-text-field
            v-model="newName"
            label="Name"
            autofocus
            :error-messages="renameError"
            @keyup.enter="confirmRename"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="renaming = null">Cancel</v-btn>
          <v-btn color="primary" @click="confirmRename">Rename</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog :model-value="!!deleting" max-width="460" @update:model-value="deleting = null">
      <v-card title="Delete configuration?">
        <v-card-text>
          "{{ deleting?.name }}" will be deleted permanently. This cannot be undone.
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="deleting = null">Cancel</v-btn>
          <v-btn color="error" @click="confirmDelete">Delete</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-snackbar :model-value="!!message" :color="message?.color" timeout="3000" @update:model-value="message = null">
      {{ message?.text }}
    </v-snackbar>
  </v-container>
</template>

<style scoped>
.page {
  max-width: 1200px;
  padding: 40px 32px;
}
.table-card {
  background: rgb(var(--v-theme-surface));
}
.table-card :deep(.v-table) {
  background: transparent;
}
.table-card :deep(th) {
  font-size: 0.75rem !important;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 600 !important;
}
.name-link {
  color: rgb(var(--v-theme-primary));
  text-decoration: none;
  font-weight: 600;
}
.name-link:hover {
  text-decoration: underline;
}
</style>
