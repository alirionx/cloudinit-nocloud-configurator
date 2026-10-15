<script setup lang="ts">
// FR-012: partition, format and mount additional disks.
import { Plus, Trash2 } from '@lucide/vue'
import { ref } from 'vue'
import type { Disk } from '../../api/types'
import { useBinder } from '../../composables/issues'
import { moveItem, useTemplates } from '../../form'
import ItemCard from '../inputs/ItemCard.vue'

const disks = defineModel<Disk[]>({ required: true })
const template = useTemplates()
const bind = useBinder()

/** Disk waiting for the data-loss confirmation (FR-012). */
const confirmOverwrite = ref<Disk | null>(null)
/** Re-renders the switches after a cancelled confirmation (the model did not change). */
const switchKey = ref(0)

function cancelOverwrite() {
  confirmOverwrite.value = null
  switchKey.value++
}

const FILESYSTEMS = [
  { title: 'ext4', value: 'ext4' },
  { title: 'xfs', value: 'xfs' },
  { title: 'btrfs', value: 'btrfs' },
  { title: 'None (do not format)', value: null },
]

function addDisk() {
  const letter = String.fromCharCode('b'.charCodeAt(0) + disks.value.length)
  disks.value.push({ ...template('disk'), device: `/dev/vd${letter}` })
}

function setOverwrite(disk: Disk, value: boolean | null) {
  if (value) confirmOverwrite.value = disk
  else disk.overwrite = false
}

const total = (disk: Disk) => disk.partitions.reduce((sum, p) => sum + (Number(p.size_percent) || 0), 0)
</script>

<template>
  <p v-if="!disks.length" class="text-body-2 text-medium-emphasis mb-3">No additional disks.</p>
  <ItemCard
    v-for="(disk, d) in disks"
    :key="d"
    :title="disk.device || `Disk #${d + 1}`"
    :index="d"
    :count="disks.length"
    @move="(to) => moveItem(disks, d, to)"
    @remove="disks.splice(d, 1)"
  >
    <v-row dense>
      <v-col cols="12" md="6">
        <v-text-field v-model="disk.device" label="Device" placeholder="/dev/vdb or /dev/disk/by-id/..." v-bind="bind(['disks', d, 'device'])" />
      </v-col>
      <v-col cols="6" md="2">
        <v-select v-model="disk.table_type" :items="['gpt', 'mbr']" label="Partition table" v-bind="bind(['disks', d, 'table_type'])" />
      </v-col>
      <v-col cols="6" md="4">
        <v-switch
          :key="`overwrite-${d}-${switchKey}`"
          :model-value="disk.overwrite"
          label="Force overwrite"
          color="error"
          v-bind="bind(['disks', d, 'overwrite'])"
          @update:model-value="(value) => setOverwrite(disk, value)"
        />
      </v-col>
    </v-row>
    <v-table density="compact" class="mb-2">
      <thead>
        <tr>
          <th>#</th>
          <th>Size (%)</th>
          <th>Filesystem</th>
          <th>Label</th>
          <th>Mount point</th>
          <th>Mount options</th>
          <th><span class="d-sr-only">Actions</span></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(partition, p) in disk.partitions" :key="p">
          <td>{{ p + 1 }}</td>
          <td style="width: 7rem">
            <v-text-field v-model.number="partition.size_percent" type="number" aria-label="Size in percent" hide-details="auto" v-bind="bind(['disks', d, 'partitions', p, 'size_percent'])" />
          </td>
          <td style="width: 12rem">
            <v-select v-model="partition.filesystem" :items="FILESYSTEMS" aria-label="Filesystem" hide-details="auto" v-bind="bind(['disks', d, 'partitions', p, 'filesystem'])" />
          </td>
          <td>
            <v-text-field v-model="partition.label" aria-label="Label" placeholder="data" hide-details="auto" v-bind="bind(['disks', d, 'partitions', p, 'label'])" />
          </td>
          <td>
            <v-text-field v-model="partition.mount_point" aria-label="Mount point" placeholder="/srv/data" hide-details="auto" v-bind="bind(['disks', d, 'partitions', p, 'mount_point'])" />
          </td>
          <td>
            <v-text-field v-model="partition.mount_options" aria-label="Mount options" hide-details="auto" v-bind="bind(['disks', d, 'partitions', p, 'mount_options'])" />
          </td>
          <td>
            <v-btn
              :icon="Trash2"
              size="small"
              variant="text"
              color="error"
              :disabled="disk.partitions.length === 1"
              :aria-label="`Remove partition ${p + 1}`"
              @click="disk.partitions.splice(p, 1)"
            />
          </td>
        </tr>
      </tbody>
    </v-table>
    <div class="d-flex align-center ga-3">
      <v-btn :prepend-icon="Plus" size="small" variant="tonal" @click="disk.partitions.push(template('partition'))">Add partition</v-btn>
      <span :class="['text-body-2', total(disk) > 100 ? 'text-error' : 'text-medium-emphasis']" :id="`field-disks-${d}-partitions`" tabindex="-1">
        {{ total(disk) }}% of the disk used
      </span>
    </div>
  </ItemCard>
  <v-btn :prepend-icon="Plus" variant="tonal" @click="addDisk">Add disk</v-btn>

  <v-dialog :model-value="!!confirmOverwrite" max-width="520" persistent>
    <v-card title="Destroy existing data?">
      <v-card-text>
        With "force overwrite", cloud-init repartitions and formats <strong>{{ confirmOverwrite?.device }}</strong> even if it
        already contains partitions or filesystems. <strong>All data on this disk will be lost.</strong>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="cancelOverwrite">Cancel</v-btn>
        <v-btn
          color="error"
          variant="flat"
          @click="
            confirmOverwrite!.overwrite = true;
            confirmOverwrite = null
          "
        >
          Overwrite, I accept data loss
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
