<script setup lang="ts">
// FR-011: SSH settings with secure defaults.
import type { HostKeyType, Ssh } from '../../api/types'
import { useBinder } from '../../composables/issues'
import LineListInput from '../inputs/LineListInput.vue'

const ssh = defineModel<Ssh>({ required: true })
const bind = useBinder()
const KEY_TYPES: HostKeyType[] = ['ed25519', 'ecdsa', 'rsa']
</script>

<template>
  <v-row dense>
    <v-col cols="12" md="6">
      <v-switch
        v-model="ssh.password_authentication"
        label="Allow password login (ssh_pwauth)"
        v-bind="bind(['ssh', 'password_authentication'])"
      />
    </v-col>
    <v-col cols="12" md="6">
      <v-switch v-model="ssh.disable_root" label="Disable root login" v-bind="bind(['ssh', 'disable_root'])" />
    </v-col>
    <v-col cols="12" md="6">
      <v-switch
        v-model="ssh.delete_host_keys"
        label="Regenerate host keys (ssh_deletekeys)"
        v-bind="bind(['ssh', 'delete_host_keys'])"
      />
    </v-col>
    <v-col cols="12" md="6">
      <v-select
        v-model="ssh.host_key_types"
        :items="KEY_TYPES"
        label="Host key types"
        multiple
        chips
        v-bind="bind(['ssh', 'host_key_types'])"
      />
    </v-col>
    <v-col cols="12">
      <LineListInput
        v-model="ssh.authorized_keys"
        :path="['ssh', 'authorized_keys']"
        label="Authorized keys for the default user (one per line)"
        placeholder="ssh-ed25519 AAAA... user@host"
      />
    </v-col>
  </v-row>
</template>
