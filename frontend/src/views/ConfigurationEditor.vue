<script setup lang="ts">
// UI-01: configuration editor. Collapsible form sections on top, live YAML preview below
// (FR-004, FR-013), explicit save (FR-015) and image download (FR-002, FR-003).
import { ArrowLeft, Download, Save } from '@lucide/vue'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError, type ImageFormat, api } from '../api/client'
import type { Configuration, ItemTemplates, StoredConfiguration } from '../api/types'
import SectionPanel from '../components/SectionPanel.vue'
import YamlPreview from '../components/YamlPreview.vue'
import BasicsSection from '../components/sections/BasicsSection.vue'
import CommandsSection from '../components/sections/CommandsSection.vue'
import DisksSection from '../components/sections/DisksSection.vue'
import FilesSection from '../components/sections/FilesSection.vue'
import NetworkSection from '../components/sections/NetworkSection.vue'
import PackagesSection from '../components/sections/PackagesSection.vue'
import SshSection from '../components/sections/SshSection.vue'
import UsersSection from '../components/sections/UsersSection.vue'
import { createIssueState, provideIssues, useField } from '../composables/issues'
import { usePreview } from '../composables/preview'
import { useUnsavedGuard } from '../composables/unsavedGuard'
import { clone, provideTemplates, randomSuffix, suggestInstanceId, toConfiguration } from '../form'

const DOCS = 'https://docs.cloud-init.io/en/latest/reference'

const route = useRoute()
const router = useRouter()

const stored = ref<StoredConfiguration | null>(null)
const form = ref<Configuration | null>(null)
const savedSnapshot = ref('')
const loadError = ref<string | null>(null)
const saving = ref(false)
const message = ref<{ text: string; color: string } | null>(null)
const conflict = ref(false)
const downloadPrompt = ref<ImageFormat | null>(null)

// FR-005: for new configurations the instance-id follows the hostname until edited.
const autoInstanceId = ref(false)
const instanceIdSuffix = randomSuffix()

const openSections = ref<string[]>(['basics'])
const issues = createIssueState((section) => {
  if (!openSections.value.includes(section)) openSections.value = [...openSections.value, section]
})
provideIssues(issues)
const nameField = useField(() => ['name'], issues)

// FR-004: defaults and list templates come from the backend model.
const newConfiguration = ref<Configuration | null>(null)
const templates = ref<ItemTemplates | null>(null)
provideTemplates(templates)

const isNew = computed(() => !stored.value)
const dirty = computed(() => !!form.value && JSON.stringify(form.value) !== savedSnapshot.value)
const { pending: leavePending } = useUnsavedGuard(dirty)

const preview = usePreview(form)
watch(preview.errors, (errors) => issues.setErrors(errors))
watch(preview.warnings, (warnings) => issues.setWarnings(warnings))

const errorCount = (section: string) => issues.countIn(section)

const plural = (count: number, word: string) => (count === 1 ? `1 ${word}` : `${count} ${word}s`)
const summaries = computed(() => {
  const f = form.value
  if (!f) return {} as Record<string, string>
  const nonEmpty = (parts: (string | false | null | undefined)[]) => parts.filter(Boolean).join(' · ')
  return {
    basics: nonEmpty([f.basics.hostname, f.basics.timezone]),
    network: nonEmpty([
      f.network.ethernets.length > 0 && plural(f.network.ethernets.length, 'NIC'),
      f.network.bridges.length > 0 && plural(f.network.bridges.length, 'bridge'),
    ]),
    packages: nonEmpty([
      f.packages.packages.length > 0 && plural(f.packages.packages.length, 'package'),
      f.packages.update && 'update',
      f.packages.upgrade && 'upgrade',
    ]),
    write_files: f.write_files.length ? plural(f.write_files.length, 'file') : '',
    commands: nonEmpty([
      f.commands.runcmd.length > 0 && `${f.commands.runcmd.length} runcmd`,
      f.commands.bootcmd.length > 0 && `${f.commands.bootcmd.length} bootcmd`,
    ]),
    users: nonEmpty([
      f.users.users.length > 0 && plural(f.users.users.length, 'user'),
      f.users.groups.length > 0 && plural(f.users.groups.length, 'group'),
    ]),
    ssh: nonEmpty([
      f.ssh.password_authentication ? 'password login allowed' : 'keys only',
      f.ssh.authorized_keys.length > 0 && plural(f.ssh.authorized_keys.length, 'key'),
    ]),
    disks: f.disks.length ? plural(f.disks.length, 'disk') : '',
  } as Record<string, string>
})

function setLoaded(config: StoredConfiguration | null) {
  stored.value = config
  form.value = config ? toConfiguration(config) : clone(newConfiguration.value!)
  savedSnapshot.value = config ? JSON.stringify(form.value) : ''
  autoInstanceId.value = !config
  if (!config) form.value.basics.instance_id = suggestInstanceId(null, instanceIdSuffix)
}

async function load() {
  loadError.value = null
  if (!templates.value) {
    try {
      const defaults = await api.defaults()
      newConfiguration.value = defaults.configuration
      templates.value = defaults.items
    } catch (error) {
      loadError.value = `Could not load defaults: ${(error as Error).message}`
      return
    }
  }
  const id = route.params.id as string | undefined
  if (!id) return setLoaded(null)
  if (stored.value?.id === id) return
  try {
    setLoaded(await api.get(id))
  } catch (error) {
    loadError.value = error instanceof ApiError && error.status === 404 ? 'Configuration not found.' : String(error)
  }
}
watch(() => route.params.id, load, { immediate: true })

watch(
  () => form.value?.basics.hostname,
  (hostname) => {
    if (form.value && autoInstanceId.value) {
      form.value.basics.instance_id = suggestInstanceId(hostname ?? null, instanceIdSuffix)
    }
  },
)

async function save(): Promise<boolean> {
  if (!form.value) return false
  saving.value = true
  try {
    const result = stored.value
      ? await api.update(stored.value.id, form.value, stored.value.revision)
      : await api.create(form.value)
    const wasNew = !stored.value
    setLoaded(result)
    message.value = { text: 'Saved.', color: 'success' }
    if (wasNew) await router.replace(`/configurations/${result.id}`)
    return true
  } catch (error) {
    if (error instanceof ApiError && error.status === 422) {
      issues.setErrors(error.issues)
      issues.revealAll()
      if (error.issues[0]) await issues.focus(error.issues[0].loc)
      message.value = { text: error.message, color: 'error' }
    } else if (error instanceof ApiError && error.status === 409) {
      conflict.value = true
    } else {
      message.value = { text: `Saving failed: ${(error as Error).message}`, color: 'error' }
    }
    return false
  } finally {
    saving.value = false
  }
}

async function reloadAfterConflict() {
  conflict.value = false
  if (!stored.value) return
  setLoaded(await api.get(stored.value.id))
  message.value = { text: 'Reloaded the latest saved version.', color: 'info' }
}

function startDownload(format: ImageFormat) {
  if (!stored.value) return
  const link = document.createElement('a')
  link.href = api.imageUrl(stored.value.id, format)
  link.click()
}

function requestDownload(format: ImageFormat) {
  if (isNew.value || dirty.value) downloadPrompt.value = format
  else startDownload(format)
}

async function saveAndDownload() {
  const format = downloadPrompt.value!
  downloadPrompt.value = null
  if (await save()) startDownload(format)
}

const FORMATS: { value: ImageFormat; title: string; subtitle: string }[] = [
  { value: 'iso', title: 'ISO', subtitle: 'ISO 9660, attach as CD-ROM' },
  { value: 'raw', title: 'RAW', subtitle: 'VFAT disk image (.img)' },
  { value: 'qcow2', title: 'QCOW2', subtitle: 'For QEMU/KVM, Proxmox' },
]
</script>

<template>
  <v-container fluid class="editor pa-4">
    <v-alert v-if="loadError" type="error" variant="tonal">
      {{ loadError }}
      <template #append><v-btn to="/" variant="text">Back to list</v-btn></template>
    </v-alert>

    <template v-else-if="form">
      <div class="d-flex align-center flex-wrap ga-2 mb-4">
        <v-btn :icon="ArrowLeft" variant="text" to="/" aria-label="Back to the list" />
        <v-text-field
          v-model="form.name"
          label="Configuration name"
          class="name-field"
          hide-details="auto"
          v-bind="nameField"
        />
        <v-chip v-if="dirty" color="warning" variant="tonal" size="small">Unsaved changes</v-chip>
        <v-spacer />
        <v-btn color="primary" :prepend-icon="Save" :loading="saving" :disabled="!dirty && !isNew" @click="save">
          Save
        </v-btn>
        <v-menu>
          <template #activator="{ props: menuProps }">
            <v-btn v-bind="menuProps" variant="tonal" :prepend-icon="Download" append-icon="$dropdown">
              Download
            </v-btn>
          </template>
          <v-list density="compact" aria-label="Image format">
            <v-list-item
              v-for="format in FORMATS"
              :key="format.value"
              :title="format.title"
              :subtitle="format.subtitle"
              @click="requestDownload(format.value)"
            />
          </v-list>
        </v-menu>
      </div>

      <v-expansion-panels v-model="openSections" multiple variant="accordion" class="mb-4">
        <SectionPanel
          value="basics"
          title="Basics"
          :summary="summaries.basics"
          help="Hostname, instance ID, timezone and locale. The instance ID tells cloud-init whether this is a new instance."
          :docs="`${DOCS}/datasources/nocloud.html`"
          :error-count="errorCount('basics')"
        >
          <BasicsSection
            v-model="form!.basics"
            :auto-instance-id="autoInstanceId"
            @manual-instance-id="autoInstanceId = false"
          />
        </SectionPanel>
        <SectionPanel
          value="network"
          title="Network"
          :summary="summaries.network"
          help="Network interfaces and bridges, written to network-config in Netplan version 2 format."
          :docs="`${DOCS}/network-config-format-v2.html`"
          :error-count="errorCount('network')"
        >
          <NetworkSection v-model="form!.network" />
        </SectionPanel>
        <SectionPanel
          value="packages"
          title="Packages"
          :summary="summaries.packages"
          help="Refresh package sources, upgrade the system and install additional Debian packages on first boot."
          :docs="`${DOCS}/modules.html#package-update-upgrade-install`"
          :error-count="errorCount('packages')"
        >
          <PackagesSection v-model="form!.packages" />
        </SectionPanel>
        <SectionPanel
          value="write_files"
          title="Files"
          :summary="summaries.write_files"
          help="Files created on the VM. Use 'defer' for files owned by users that cloud-init creates."
          :docs="`${DOCS}/modules.html#write-files`"
          :error-count="errorCount('write_files')"
        >
          <FilesSection v-model="form!.write_files" />
        </SectionPanel>
        <SectionPanel
          value="commands"
          title="Commands"
          :summary="summaries.commands"
          help="Commands run at boot: runcmd once at the end of the first boot, bootcmd early on every boot."
          :docs="`${DOCS}/modules.html#runcmd`"
          :error-count="errorCount('commands')"
        >
          <CommandsSection v-model="form!.commands" />
        </SectionPanel>
        <SectionPanel
          value="users"
          title="Users and groups"
          :summary="summaries.users"
          help="User accounts with groups, sudo rules, passwords and SSH keys. Passwords are stored only as hashes."
          :docs="`${DOCS}/modules.html#users-and-groups`"
          :error-count="errorCount('users')"
        >
          <UsersSection v-model="form!.users" />
        </SectionPanel>
        <SectionPanel
          value="ssh"
          title="SSH"
          :summary="summaries.ssh"
          help="SSH access. Secure defaults: no password login, no root login."
          :docs="`${DOCS}/modules.html#ssh`"
          :error-count="errorCount('ssh')"
        >
          <SshSection v-model="form!.ssh" />
        </SectionPanel>
        <SectionPanel
          value="disks"
          title="Disks"
          :summary="summaries.disks"
          help="Partition, format and mount additional disks (disk_setup, fs_setup, mounts)."
          :docs="`${DOCS}/modules.html#disk-setup`"
          :error-count="errorCount('disks')"
        >
          <DisksSection v-model="form!.disks" />
        </SectionPanel>
      </v-expansion-panels>

      <YamlPreview
        :files="preview.files.value"
        :errors="preview.errors.value"
        :warnings="preview.warnings.value"
        :failure="preview.failure.value"
        :loading="preview.loading.value"
        @focus="issues.focus"
      />
    </template>

    <v-dialog :model-value="!!leavePending" max-width="460" persistent>
      <v-card title="Discard unsaved changes?">
        <v-card-text>You have unsaved changes. Leaving this page discards them.</v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="leavePending?.(false)">Stay</v-btn>
          <v-btn color="error" @click="leavePending?.(true)">Discard changes</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="conflict" max-width="520" persistent>
      <v-card title="Changed in the meantime">
        <v-card-text>
          Someone else saved this configuration after you opened it. Reload the latest version (your unsaved
          changes are lost) or keep editing and copy your changes first.
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="conflict = false">Keep editing</v-btn>
          <v-btn color="primary" @click="reloadAfterConflict">Reload latest version</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog :model-value="!!downloadPrompt" max-width="460" @update:model-value="downloadPrompt = null">
      <v-card title="Save before downloading?">
        <v-card-text>The image is built from the saved configuration. Save your changes first?</v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="downloadPrompt = null">Cancel</v-btn>
          <v-btn color="primary" @click="saveAndDownload">Save and download</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-snackbar
      :model-value="!!message"
      :color="message?.color"
      timeout="3000"
      @update:model-value="message = null"
    >
      {{ message?.text }}
    </v-snackbar>
  </v-container>
</template>

<style scoped>
.editor {
  max-width: 1400px;
}
.name-field {
  max-width: 28rem;
  min-width: 16rem;
}
</style>
