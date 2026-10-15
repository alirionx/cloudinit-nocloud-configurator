<script setup lang="ts">
// FR-009: bootcmd (every boot, very early) and runcmd (once, end of first boot).
import type { Commands } from '../../api/types'
import CommandList from './CommandList.vue'

const commands = defineModel<Commands>({ required: true })
</script>

<template>
  <v-alert type="warning" variant="tonal" density="compact" class="mb-4">
    <strong>bootcmd</strong> runs very early on <strong>every</strong> boot, before the network may be up.
    <strong>runcmd</strong> runs only once, at the end of the first boot (after packages and files).
  </v-alert>
  <h3 class="text-subtitle-1 mb-2">runcmd (first boot only)</h3>
  <CommandList v-model="commands.runcmd" :path="['commands', 'runcmd']" name="runcmd" />
  <h3 class="text-subtitle-1 mt-6 mb-2">bootcmd (every boot)</h3>
  <CommandList v-model="commands.bootcmd" :path="['commands', 'bootcmd']" name="bootcmd" />
</template>
