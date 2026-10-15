<script setup lang="ts">
// FR-010: users and groups. Passwords are sent once in plain text, hashed by the
// backend and afterwards only shown as "set" (never readable).
import { Plus } from '@lucide/vue'
import { ref } from 'vue'
import type { User, Users } from '../../api/types'
import { useBinder } from '../../composables/issues'
import { moveItem, useTemplates } from '../../form'
import ItemCard from '../inputs/ItemCard.vue'
import LineListInput from '../inputs/LineListInput.vue'
import TagInput from '../inputs/TagInput.vue'

const users = defineModel<Users>({ required: true })
const template = useTemplates()
const bind = useBinder()

const PASSWORDLESS_SUDO = 'ALL=(ALL) NOPASSWD:ALL'
/** Which password input is open per user: a new password or a precomputed hash. */
const passwordMode = ref<Record<number, 'plain' | 'hash' | undefined>>({})
const showPassword = ref(false)

function addUser() {
  users.value.users.push(template('user'))
}

function removeUser(index: number) {
  users.value.users.splice(index, 1)
  passwordMode.value = {}
}

function removePassword(user: User, index: number) {
  user.password = null
  user.password_hash = null
  passwordMode.value[index] = undefined
}

function startPassword(user: User, index: number, mode: 'plain' | 'hash') {
  passwordMode.value[index] = mode
  if (mode === 'plain') user.password = ''
}

function cancelPassword(user: User, index: number) {
  delete user.password
  passwordMode.value[index] = undefined
}

const status = (user: User) =>
  user.password ? 'New password (hashed on save)' : user.password_hash ? 'Password set' : 'No password'
</script>

<template>
  <v-switch
    v-model="users.keep_default_user"
    label="Keep the distribution's default user (e.g. 'debian')"
    v-bind="bind(['users', 'keep_default_user'])"
    class="mb-2"
  />
  <h3 class="text-subtitle-1 mb-2">Users</h3>
  <ItemCard
    v-for="(user, index) in users.users"
    :key="index"
    :title="user.name || `User #${index + 1}`"
    :index="index"
    :count="users.users.length"
    @move="(to) => moveItem(users.users, index, to)"
    @remove="removeUser(index)"
  >
    <v-row dense>
      <v-col cols="12" md="3">
        <v-text-field v-model="user.name" label="User name" placeholder="admin" v-bind="bind(['users', 'users', index, 'name'])" />
      </v-col>
      <v-col cols="12" md="5">
        <v-text-field v-model="user.gecos" label="Display name" v-bind="bind(['users', 'users', index, 'gecos'])" />
      </v-col>
      <v-col cols="12" md="4">
        <v-text-field v-model="user.shell" label="Shell" placeholder="/bin/bash" v-bind="bind(['users', 'users', index, 'shell'])" />
      </v-col>
      <v-col cols="12" md="3">
        <v-text-field
          v-model="user.primary_group"
          label="Primary group"
          v-bind="bind(['users', 'users', index, 'primary_group'])"
        />
      </v-col>
      <v-col cols="12" md="9">
        <TagInput v-model="user.groups" :path="['users', 'users', index, 'groups']" label="Additional groups" placeholder="docker" />
      </v-col>
      <v-col cols="12" md="4">
        <v-checkbox
          v-model="user.admin"
          label="Administrator (group sudo)"
          v-bind="bind(['users', 'users', index, 'admin'])"
        />
      </v-col>
      <v-col cols="12" md="8">
        <v-text-field
          v-model="user.sudo"
          label="sudo rule"
          placeholder="ALL=(ALL) NOPASSWD:ALL"
          v-bind="bind(['users', 'users', index, 'sudo'])"
        >
          <template #append-inner>
            <v-btn size="x-small" variant="tonal" @click="user.sudo = PASSWORDLESS_SUDO">Passwordless</v-btn>
          </template>
        </v-text-field>
      </v-col>
      <v-col cols="12">
        <div class="d-flex align-center flex-wrap ga-2 mb-2" :id="`field-users-users-${index}-password_hash`" tabindex="-1">
          <v-chip :color="user.password || user.password_hash ? 'success' : undefined" variant="tonal" size="small">
            {{ status(user) }}
          </v-chip>
          <template v-if="!passwordMode[index]">
            <v-btn size="small" variant="text" @click="startPassword(user, index, 'plain')">
              {{ user.password_hash ? 'Replace password' : 'Set password' }}
            </v-btn>
            <v-btn size="small" variant="text" @click="startPassword(user, index, 'hash')">Enter hash</v-btn>
            <v-btn v-if="user.password_hash || user.password" size="small" variant="text" color="error" @click="removePassword(user, index)">
              Remove password
            </v-btn>
          </template>
          <v-btn v-else size="small" variant="text" @click="cancelPassword(user, index)">Cancel</v-btn>
        </div>
        <v-text-field
          v-if="passwordMode[index] === 'plain'"
          v-model="user.password"
          label="New password"
          :type="showPassword ? 'text' : 'password'"
          autocomplete="new-password"
          hint="Sent once to the server, hashed immediately (SHA-512-crypt) and discarded."
          persistent-hint
          :append-inner-icon="showPassword ? '$complete' : '$edit'"
          v-bind="bind(['users', 'users', index, 'password'])"
          @click:append-inner="showPassword = !showPassword"
        />
        <v-text-field
          v-if="passwordMode[index] === 'hash'"
          v-model="user.password_hash"
          label="Password hash"
          placeholder="$6$... (mkpasswd -m sha-512)"
          v-bind="bind(['users', 'users', index, 'password_hash'])"
        />
      </v-col>
      <v-col cols="12" md="4">
        <v-switch
          v-model="user.lock_passwd"
          label="Lock password (no password login)"
          v-bind="bind(['users', 'users', index, 'lock_passwd'])"
        />
      </v-col>
      <v-col cols="12" md="4">
        <v-checkbox v-model="user.system" label="System user" v-bind="bind(['users', 'users', index, 'system'])" />
      </v-col>
      <v-col cols="12">
        <LineListInput
          v-model="user.ssh_authorized_keys"
          :path="['users', 'users', index, 'ssh_authorized_keys']"
          label="SSH public keys (one per line)"
          placeholder="ssh-ed25519 AAAA... user@host"
        />
      </v-col>
    </v-row>
  </ItemCard>
  <v-btn :prepend-icon="Plus" variant="tonal" class="mb-6" @click="addUser">Add user</v-btn>

  <h3 class="text-subtitle-1 mb-2">Groups</h3>
  <ItemCard
    v-for="(group, index) in users.groups"
    :key="index"
    :title="group.name || `Group #${index + 1}`"
    :index="index"
    :count="users.groups.length"
    @move="(to) => moveItem(users.groups, index, to)"
    @remove="users.groups.splice(index, 1)"
  >
    <v-row dense>
      <v-col cols="12" md="4">
        <v-text-field v-model="group.name" label="Group name" v-bind="bind(['users', 'groups', index, 'name'])" />
      </v-col>
      <v-col cols="12" md="8">
        <TagInput v-model="group.members" :path="['users', 'groups', index, 'members']" label="Members" />
      </v-col>
    </v-row>
  </ItemCard>
  <v-btn :prepend-icon="Plus" variant="tonal" @click="users.groups.push(template('group'))">Add group</v-btn>
</template>
