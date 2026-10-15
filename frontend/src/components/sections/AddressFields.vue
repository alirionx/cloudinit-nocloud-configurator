<script setup lang="ts">
// FR-006: address settings shared by NICs and bridges.
import type { AddressSettings } from '../../api/types'
import { type Path, useField } from '../../composables/issues'
import TagInput from '../inputs/TagInput.vue'

const settings = defineModel<AddressSettings>({ required: true })
const props = defineProps<{ path: Path }>()

const field = (name: keyof AddressSettings) => useField(() => [...props.path, name])
const dhcp4 = field('dhcp4')
const dhcp6 = field('dhcp6')
const gateway4 = field('gateway4')
const gateway6 = field('gateway6')
const mtu = field('mtu')
</script>

<template>
  <v-row dense>
    <v-col cols="6" md="2"><v-switch v-model="settings.dhcp4" label="DHCPv4" v-bind="dhcp4" /></v-col>
    <v-col cols="6" md="2"><v-switch v-model="settings.dhcp6" label="DHCPv6" v-bind="dhcp6" /></v-col>
    <v-col cols="12" md="8">
      <TagInput
        v-model="settings.addresses"
        :path="[...path, 'addresses']"
        label="Static addresses (CIDR)"
        placeholder="192.168.1.10/24"
      />
    </v-col>
    <v-col cols="12" md="4">
      <v-text-field v-model="settings.gateway4" label="IPv4 gateway" placeholder="192.168.1.1" v-bind="gateway4" />
    </v-col>
    <v-col cols="12" md="4">
      <v-text-field v-model="settings.gateway6" label="IPv6 gateway" placeholder="fd00::1" v-bind="gateway6" />
    </v-col>
    <v-col cols="12" md="4">
      <v-text-field v-model.number="settings.mtu" label="MTU" type="number" placeholder="1500" v-bind="mtu" />
    </v-col>
    <v-col cols="12" md="6">
      <TagInput v-model="settings.nameservers" :path="[...path, 'nameservers']" label="DNS servers" placeholder="9.9.9.9" />
    </v-col>
    <v-col cols="12" md="6">
      <TagInput v-model="settings.search" :path="[...path, 'search']" label="Search domains" placeholder="example.com" />
    </v-col>
  </v-row>
</template>
