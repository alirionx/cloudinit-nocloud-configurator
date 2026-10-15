<script setup lang="ts">
// FR-007: package sources, upgrades and additional packages (Debian / apt).
import type { Packages } from '../../api/types'
import { useBinder } from '../../composables/issues'
import TagInput from '../inputs/TagInput.vue'

const packages = defineModel<Packages>({ required: true })
const bind = useBinder()
</script>

<template>
  <v-row dense>
    <v-col cols="12" md="4">
      <v-switch v-model="packages.update" label="Update package sources (apt update)" v-bind="bind(['packages', 'update'])" />
    </v-col>
    <v-col cols="12" md="4">
      <v-switch v-model="packages.upgrade" label="Upgrade installed packages" v-bind="bind(['packages', 'upgrade'])" />
    </v-col>
    <v-col cols="12" md="4">
      <v-switch
        v-model="packages.reboot_if_required"
        label="Reboot if an upgrade requires it"
        v-bind="bind(['packages', 'reboot_if_required'])"
      />
    </v-col>
    <v-col cols="12">
      <TagInput
        v-model="packages.packages"
        :path="['packages', 'packages']"
        label="Packages"
        placeholder="git, wget docker.io"
        hint="Debian package names, separated by Enter, comma or space. Names are not checked against the repositories: a typo only shows up at boot."
      />
    </v-col>
  </v-row>
</template>
