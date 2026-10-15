<script setup lang="ts">
// FR-005: basics and meta-data.
import { computed } from 'vue'
import type { Basics } from '../../api/types'
import { useField } from '../../composables/issues'

const basics = defineModel<Basics>({ required: true })
const props = defineProps<{ autoInstanceId: boolean }>()
const emit = defineEmits<{ 'manual-instance-id': [] }>()

const field = (name: keyof Basics) => useField(() => ['basics', name])
const instanceId = field('instance_id')
const hostname = field('hostname')
const fqdn = field('fqdn')
const timezone = field('timezone')
const locale = field('locale')

const timezones = computed(() => {
  try {
    return ['UTC', ...Intl.supportedValuesOf('timeZone').filter((zone) => zone !== 'UTC')]
  } catch {
    return ['UTC']
  }
})
const LOCALES = ['C.UTF-8', 'en_US.UTF-8', 'en_GB.UTF-8', 'de_DE.UTF-8', 'fr_FR.UTF-8', 'es_ES.UTF-8', 'it_IT.UTF-8', 'nl_NL.UTF-8']

const instanceIdHint = computed(() =>
  props.autoInstanceId
    ? 'Generated from the hostname. Change it to set your own.'
    : 'Changing it makes cloud-init treat the VM as a new instance.',
)
</script>

<template>
  <v-row dense>
    <v-col cols="12" md="6">
      <v-text-field
        v-model="basics.hostname"
        label="Hostname (local-hostname)"
        placeholder="web-01"
        hint="Letters, digits and hyphens (RFC 1123)."
        persistent-hint
        v-bind="hostname"
      />
    </v-col>
    <v-col cols="12" md="6">
      <v-text-field
        v-model="basics.fqdn"
        label="FQDN (optional)"
        placeholder="web-01.example.com"
        v-bind="fqdn"
      />
    </v-col>
    <v-col cols="12" md="6">
      <v-text-field
        v-model="basics.instance_id"
        label="Instance ID"
        :hint="instanceIdHint"
        persistent-hint
        v-bind="instanceId"
        @update:model-value="emit('manual-instance-id')"
      />
    </v-col>
    <v-col cols="12" md="3">
      <v-autocomplete
        v-model="basics.timezone"
        :items="timezones"
        label="Timezone"
        clearable
        v-bind="timezone"
      />
    </v-col>
    <v-col cols="12" md="3">
      <v-combobox v-model="basics.locale" :items="LOCALES" label="Locale" clearable v-bind="locale" />
    </v-col>
  </v-row>
</template>
