<script setup lang="ts">
// UI-01: configuration editor. Collapsible form sections on top, live YAML preview below
// (FR-004, FR-013), explicit save (FR-015) and image download (FR-002, FR-003).
import { ArrowLeft, Download, RotateCcw, Save } from '@lucide/vue'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError, type ImageFormat, api } from '../api/client'
import type { Configuration, FileName, ItemTemplates, StoredConfiguration, YamlError } from '../api/types'
import SectionPanel from '../components/SectionPanel.vue'
import YamlPreview from '../components/YamlPreview.vue'
import AdditionalSection from '../components/sections/AdditionalSection.vue'
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
import { clone, provideTemplates, randomSuffix, suggestInstanceId, toConfiguration, yamlOnlyKeys } from '../form'

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
/** Download waiting for confirmation because of cloud-init schema hints (FR-014). */
const schemaPrompt = ref<ImageFormat | null>(null)
const revertPrompt = ref(false)

// FR-014: editing one file as YAML; the form is locked meanwhile.
const previewPanel = ref<InstanceType<typeof YamlPreview>>()
const editingFile = ref<FileName | null>(null)
const yamlErrors = ref<YamlError[]>([])
const notices = ref<string[]>([])
const applying = ref(false)

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
const dirty = computed(
  () => !!form.value && (JSON.stringify(form.value) !== savedSnapshot.value || editingFile.value !== null),
)
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
    additional: (() => {
      const count =
        Object.keys(f.additional.user_data).length +
        Object.keys(f.additional.meta_data).length +
        Object.keys(f.additional.network).length +
        (f.additional.vendor_data ? 1 : 0)
      return count ? plural(count, 'key') : ''
    })(),
  } as Record<string, string>
})

function setLoaded(config: StoredConfiguration | null) {
  stored.value = config
  editingFile.value = null
  yamlErrors.value = []
  notices.value = []
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

function startEditing(file: FileName) {
  editingFile.value = file
  yamlErrors.value = []
  notices.value = []
}

function discardYaml() {
  editingFile.value = null
  yamlErrors.value = []
}

/** FR-014: parse the edited YAML back into the form. Returns false if it has errors. */
async function applyYaml(text: string): Promise<boolean> {
  if (!form.value || !editingFile.value) return true
  applying.value = true
  try {
    const result = await api.parse(form.value, editingFile.value, text)
    form.value = result.configuration
    autoInstanceId.value = false
    notices.value = result.notices
    editingFile.value = null
    yamlErrors.value = []
    return true
  } catch (error) {
    if (error instanceof ApiError && error.yamlErrors.length) {
      yamlErrors.value = error.yamlErrors
    } else if (error instanceof ApiError && error.issues.length) {
      yamlErrors.value = error.issues.map((issue) => ({ line: null, msg: `${issue.loc.join(' › ')}: ${issue.msg}` }))
    } else {
      yamlErrors.value = [{ line: null, msg: (error as Error).message }]
    }
    message.value = { text: 'The YAML contains errors.', color: 'error' }
    return false
  } finally {
    applying.value = false
  }
}

/** FR-014: discard all changes and go back to the last saved state. */
function revertToSaved() {
  revertPrompt.value = false
  setLoaded(stored.value)
  message.value = { text: 'Reverted to the last saved state.', color: 'info' }
}

async function save(): Promise<boolean> {
  if (!form.value) return false
  // Unapplied YAML edits are applied first (FR-014).
  if (editingFile.value && !(await applyYaml(previewPanel.value?.editText ?? ''))) return false
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

/** FR-014: schema violations do not block saving, but the download warns about them. */
function downloadChecked(format: ImageFormat) {
  if (preview.schemaIssues.value.length) schemaPrompt.value = format
  else startDownload(format)
}

function requestDownload(format: ImageFormat) {
  if (isNew.value || dirty.value) downloadPrompt.value = format
  else downloadChecked(format)
}

async function saveAndDownload() {
  const format = downloadPrompt.value!
  downloadPrompt.value = null
  if (await save()) downloadChecked(format)
}

function confirmSchemaDownload() {
  const format = schemaPrompt.value!
  schemaPrompt.value = null
  startDownload(format)
}

const yamlNotice = (section: string) => {
  const keys = form.value ? yamlOnlyKeys(form.value, section) : []
  return keys.length
    ? `Kept as YAML in the additional settings (the form cannot show all of it): ${keys.join(', ')}`
    : undefined
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
        <v-btn v-if="dirty && stored" variant="text" :prepend-icon="RotateCcw" @click="revertPrompt = true">
          Revert to saved
        </v-btn>
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

      <v-alert v-if="editingFile" type="info" variant="tonal" density="compact" class="mb-2">
        The form is locked while {{ editingFile }} is edited as YAML below.
      </v-alert>
      <v-expansion-panels
        v-model="openSections"
        multiple
        variant="accordion"
        class="mb-4"
        :class="{ locked: !!editingFile }"
        :inert="!!editingFile"
      >
        <SectionPanel
          value="basics"
          title="Basics"
          :summary="summaries.basics"
          help="Hostname, instance ID, timezone and locale. The instance ID tells cloud-init whether this is a new instance."
          :docs="`${DOCS}/datasources/nocloud.html`"
          :error-count="errorCount('basics')"
          :notice="yamlNotice('basics')"
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
          :notice="yamlNotice('network')"
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
          :notice="yamlNotice('packages')"
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
          :notice="yamlNotice('write_files')"
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
          :notice="yamlNotice('commands')"
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
          :notice="yamlNotice('users')"
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
          :notice="yamlNotice('ssh')"
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
          :notice="yamlNotice('disks')"
        >
          <DisksSection v-model="form!.disks" />
        </SectionPanel>
        <SectionPanel
          value="additional"
          title="Additional settings (YAML only)"
          :summary="summaries.additional"
          help="Settings the form does not cover, e.g. further cloud-init modules or bonds and VLANs. They are kept unchanged and can only be edited with 'Edit as YAML' in the preview."
          :docs="`${DOCS}/modules.html`"
          :error-count="errorCount('additional')"
        >
          <AdditionalSection v-model="form!.additional" @edit="startEditing" />
        </SectionPanel>
      </v-expansion-panels>

      <YamlPreview
        ref="previewPanel"
        :files="preview.files.value"
        :errors="preview.errors.value"
        :warnings="preview.warnings.value"
        :schema-issues="preview.schemaIssues.value"
        :failure="preview.failure.value"
        :loading="preview.loading.value"
        :editing="editingFile"
        :yaml-errors="yamlErrors"
        :notices="notices"
        :applying="applying"
        @focus="issues.focus"
        @edit="startEditing"
        @apply="applyYaml"
        @discard="discardYaml"
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

    <v-dialog :model-value="!!schemaPrompt" max-width="560" @update:model-value="schemaPrompt = null">
      <v-card title="Configuration does not match the cloud-init schema">
        <v-card-text>
          cloud-init reports {{ preview.schemaIssues.value.length }} schema
          {{ preview.schemaIssues.value.length === 1 ? 'violation' : 'violations' }}. cloud-init may ignore or reject
          these settings at boot:
          <ul class="mt-2 ml-4">
            <li v-for="(issue, index) in preview.schemaIssues.value.slice(0, 5)" :key="index">
              {{ issue.file }}{{ issue.line ? `, line ${issue.line}` : '' }}: {{ issue.msg }}
            </li>
          </ul>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="schemaPrompt = null">Cancel</v-btn>
          <v-btn color="warning" variant="flat" @click="confirmSchemaDownload">Download anyway</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="revertPrompt" max-width="460">
      <v-card title="Revert to the last saved state?">
        <v-card-text>All unsaved changes in the form and in the YAML editor are discarded.</v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="revertPrompt = false">Cancel</v-btn>
          <v-btn color="error" @click="revertToSaved">Revert</v-btn>
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
.locked {
  opacity: 0.6;
}
.name-field {
  max-width: 28rem;
  min-width: 16rem;
}
</style>
