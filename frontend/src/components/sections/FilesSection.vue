<script setup lang="ts">
// FR-008: file editor for write_files with code editor, upload and permission presets.
import { FileUp, Plus } from '@lucide/vue'
import { ref } from 'vue'
import type { WriteFile } from '../../api/types'
import { useBinder } from '../../composables/issues'
import { fieldId } from '../../composables/issues'
import { clone, moveItem, useTemplates } from '../../form'
import CodeEditor from '../CodeEditor.vue'
import ItemCard from '../inputs/ItemCard.vue'
import { languageForPath } from '../languages'
import { decodeUpload } from '../upload'

const files = defineModel<WriteFile[]>({ required: true })
const template = useTemplates()
const bind = useBinder()
const uploadInput = ref<HTMLInputElement>()
const uploadTarget = ref<number | null>(null)

const PRESETS = [
  { title: 'Script', value: '0755' },
  { title: 'Config', value: '0644' },
  { title: 'Secret', value: '0600' },
]

function add() {
  files.value.push(template('write_file'))
}

function duplicate(index: number) {
  files.value.splice(index + 1, 0, clone(files.value[index]!))
}

function startUpload(index: number) {
  uploadTarget.value = index
  uploadInput.value?.click()
}

async function onUpload(event: Event) {
  const input = event.target as HTMLInputElement
  const upload = input.files?.[0]
  const index = uploadTarget.value
  input.value = ''
  if (!upload || index === null) return
  const file = files.value[index]!
  const { content, encoding } = decodeUpload(new Uint8Array(await upload.arrayBuffer()))
  file.content = content
  file.encoding = encoding
  if (!file.path) file.path = `/opt/${upload.name}`
}

function editAsText(file: WriteFile) {
  file.encoding = 'text'
  file.content = ''
}

const size = (base64: string) => Math.floor((base64.length * 3) / 4 - (base64.match(/=+$/)?.[0].length ?? 0))
</script>

<template>
  <input ref="uploadInput" type="file" hidden @change="onUpload" />
  <p v-if="!files.length" class="text-body-2 text-medium-emphasis mb-3">No files.</p>
  <ItemCard
    v-for="(file, index) in files"
    :key="index"
    :title="file.path || `File #${index + 1}`"
    :index="index"
    :count="files.length"
    duplicable
    @move="(to) => moveItem(files, index, to)"
    @duplicate="duplicate(index)"
    @remove="files.splice(index, 1)"
  >
    <v-row dense>
      <v-col cols="12" md="6">
        <v-text-field v-model="file.path" label="Target path" placeholder="/etc/app/config.yaml" v-bind="bind(['write_files', index, 'path'])" />
      </v-col>
      <v-col cols="6" md="2">
        <v-text-field v-model="file.owner" label="Owner" placeholder="root:root" v-bind="bind(['write_files', index, 'owner'])" />
      </v-col>
      <v-col cols="6" md="4">
        <v-text-field v-model="file.permissions" label="Permissions" placeholder="0644" v-bind="bind(['write_files', index, 'permissions'])">
          <template #append-inner>
            <v-menu>
              <template #activator="{ props: menuProps }">
                <v-btn v-bind="menuProps" size="x-small" variant="tonal">Presets</v-btn>
              </template>
              <v-list density="compact">
                <v-list-item
                  v-for="preset in PRESETS"
                  :key="preset.value"
                  :title="`${preset.title} ${preset.value}`"
                  @click="file.permissions = preset.value"
                />
              </v-list>
            </v-menu>
          </template>
        </v-text-field>
      </v-col>
      <v-col cols="12" class="d-flex flex-wrap align-center ga-4">
        <v-checkbox v-model="file.append" label="Append to an existing file" v-bind="bind(['write_files', index, 'append'])" />
        <v-checkbox
          v-model="file.defer"
          label="Defer (write after users are created)"
          v-bind="bind(['write_files', index, 'defer'])"
        />
        <v-spacer />
        <v-btn :prepend-icon="FileUp" variant="tonal" size="small" @click="startUpload(index)">Upload file</v-btn>
      </v-col>
      <v-col cols="12">
        <v-alert v-if="file.encoding === 'b64'" type="info" variant="tonal" density="compact">
          Binary file ({{ size(file.content) }} bytes), included Base64-encoded.
          <template #append>
            <v-btn variant="text" size="small" @click="editAsText(file)">Replace with text</v-btn>
          </template>
        </v-alert>
        <CodeEditor
          v-else
          v-model="file.content"
          :language="languageForPath(file.path)"
          :id="fieldId(['write_files', index, 'content'])"
          :label="`Content of ${file.path || 'file'}`"
          min-height="6rem"
          max-height="24rem"
        />
      </v-col>
    </v-row>
  </ItemCard>
  <v-btn :prepend-icon="Plus" variant="tonal" @click="add">Add file</v-btn>
</template>
