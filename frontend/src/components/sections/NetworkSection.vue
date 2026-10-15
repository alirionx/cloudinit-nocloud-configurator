<script setup lang="ts">
// FR-006: NICs (matched by name or MAC) and bridges, rendered as Netplan v2.
import { Plus } from '@lucide/vue'
import { computed } from 'vue'
import type { Network } from '../../api/types'
import { useBinder } from '../../composables/issues'
import { moveItem, useTemplates } from '../../form'
import ItemCard from '../inputs/ItemCard.vue'
import AddressFields from './AddressFields.vue'

const network = defineModel<Network>({ required: true })
const template = useTemplates()

const nicNames = computed(() => network.value.ethernets.map((nic) => nic.name).filter(Boolean))
const memberOf = (name: string) => network.value.bridges.find((bridge) => bridge.interfaces.includes(name))?.name

function addNic() {
  network.value.ethernets.push({ ...template('ethernet'), name: `eth${network.value.ethernets.length}` })
}
function addBridge() {
  network.value.bridges.push({ ...template('bridge'), name: `br${network.value.bridges.length}` })
}

const bind = useBinder()
const nicField = (index: number, name: string) => bind(['network', 'ethernets', index, name])
const bridgeField = (index: number, name: string) => bind(['network', 'bridges', index, name])

const STP = [
  { title: 'Default', value: null },
  { title: 'On', value: true },
  { title: 'Off', value: false },
]
</script>

<template>
  <h3 class="text-subtitle-1 mb-2">Network interfaces (NICs)</h3>
  <p v-if="!network.ethernets.length" class="text-body-2 text-medium-emphasis mb-3">
    No interfaces configured: no network-config is generated and cloud-init uses DHCP on the first interface.
  </p>
  <ItemCard
    v-for="(nic, index) in network.ethernets"
    :key="index"
    :title="nic.name || `NIC #${index + 1}`"
    :index="index"
    :count="network.ethernets.length"
    @move="(to) => moveItem(network.ethernets, index, to)"
    @remove="network.ethernets.splice(index, 1)"
  >
    <v-row dense>
      <v-col cols="12" md="4">
        <v-text-field v-model="nic.name" label="Name" placeholder="eth0" v-bind="nicField(index, 'name')" />
      </v-col>
      <v-col cols="12" md="8">
        <v-text-field
          v-model="nic.match_mac"
          label="Match by MAC address (optional)"
          placeholder="52:54:00:12:34:56"
          hint="If set, the NIC with this MAC address is renamed to the name above (set-name)."
          persistent-hint
          v-bind="nicField(index, 'match_mac')"
        />
      </v-col>
    </v-row>
    <v-alert v-if="memberOf(nic.name)" type="info" variant="tonal" density="compact" class="my-2">
      Member of bridge {{ memberOf(nic.name) }}: configure addresses on the bridge.
    </v-alert>
    <AddressFields v-else v-model="network.ethernets[index]!" :path="['network', 'ethernets', index]" />
  </ItemCard>
  <v-btn :prepend-icon="Plus" variant="tonal" class="mb-6" @click="addNic">Add NIC</v-btn>

  <h3 class="text-subtitle-1 mb-2">Bridges</h3>
  <ItemCard
    v-for="(bridge, index) in network.bridges"
    :key="index"
    :title="bridge.name || `Bridge #${index + 1}`"
    :index="index"
    :count="network.bridges.length"
    @move="(to) => moveItem(network.bridges, index, to)"
    @remove="network.bridges.splice(index, 1)"
  >
    <v-row dense>
      <v-col cols="12" md="3">
        <v-text-field v-model="bridge.name" label="Name" placeholder="br0" v-bind="bridgeField(index, 'name')" />
      </v-col>
      <v-col cols="12" md="5">
        <v-select
          v-model="bridge.interfaces"
          :items="nicNames"
          label="Member NICs"
          multiple
          chips
          no-data-text="Add a NIC first"
          v-bind="bridgeField(index, 'interfaces')"
        />
      </v-col>
      <v-col cols="6" md="2">
        <v-select v-model="bridge.stp" :items="STP" label="STP" v-bind="bridgeField(index, 'stp')" />
      </v-col>
      <v-col cols="6" md="2">
        <v-text-field
          v-model.number="bridge.forward_delay"
          type="number"
          label="Forward delay (s)"
          v-bind="bridgeField(index, 'forward_delay')"
        />
      </v-col>
    </v-row>
    <AddressFields v-model="network.bridges[index]!" :path="['network', 'bridges', index]" />
  </ItemCard>
  <v-btn :prepend-icon="Plus" variant="tonal" @click="addBridge">Add bridge</v-btn>
  <p class="text-body-2 text-medium-emphasis mt-3">Bonds and VLANs can be added by editing the YAML.</p>
</template>
