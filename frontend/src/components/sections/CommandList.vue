<script setup lang="ts">
// FR-009: an ordered list of commands; reorder by drag & drop or with the arrow buttons.
import { GripVertical, Plus } from '@lucide/vue'
import { ref } from 'vue'
import type { Command } from '../../api/types'
import { type Path, useBinder } from '../../composables/issues'
import { moveItem } from '../../form'
import ItemCard from '../inputs/ItemCard.vue'
import TagInput from '../inputs/TagInput.vue'

const commands = defineModel<Command[]>({ required: true })
const props = defineProps<{ path: Path; name: string }>()
const bind = useBinder()

const dragging = ref<number | null>(null)
const over = ref<number | null>(null)

function onDragStart(event: DragEvent, index: number) {
  dragging.value = index
  // Some browsers only start a drag when data is set.
  event.dataTransfer?.setData('text/plain', String(index))
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move'
}

function onDrop(index: number) {
  if (dragging.value !== null) moveItem(commands.value, dragging.value, index)
  dragging.value = null
  over.value = null
}

function setKind(index: number, kind: 'shell' | 'args') {
  const current = commands.value[index]!
  if (kind === 'args' && typeof current === 'string') {
    commands.value[index] = current.trim() ? current.trim().split(/\s+/) : []
  } else if (kind === 'shell' && Array.isArray(current)) {
    commands.value[index] = current.join(' ')
  }
}

const title = (command: Command, index: number) => {
  const text = Array.isArray(command) ? command.join(' ') : command.split('\n')[0]
  return `#${index + 1} ${text ?? ''}`.trim()
}
</script>

<template>
  <div
    v-for="(command, index) in commands"
    :key="index"
    :class="{ 'drop-target': over === index && dragging !== index }"
    @dragover.prevent="over = index"
    @dragleave="over = null"
    @drop.prevent="onDrop(index)"
  >
    <ItemCard
      :title="title(command, index)"
      :index="index"
      :count="commands.length"
      @move="(to) => moveItem(commands, index, to)"
      @remove="commands.splice(index, 1)"
    >
      <template #handle>
        <span
          class="drag-handle mr-2"
          draggable="true"
          :aria-label="`Drag ${name} entry ${index + 1}`"
          title="Drag to reorder"
          @dragstart="onDragStart($event, index)"
          @dragend="dragging = null"
        >
          <GripVertical :size="18" />
        </span>
      </template>
      <v-btn-toggle
        :model-value="Array.isArray(command) ? 'args' : 'shell'"
        density="compact"
        variant="outlined"
        mandatory
        class="mb-2"
        @update:model-value="(kind: string) => setKind(index, kind as 'shell' | 'args')"
      >
        <v-btn value="shell" size="small">Shell line</v-btn>
        <v-btn value="args" size="small">Command with arguments</v-btn>
      </v-btn-toggle>
      <TagInput
        v-if="Array.isArray(command)"
        v-model="commands[index] as string[]"
        :path="[...path, index]"
        label="Command and arguments"
        split="enter"
        hint="Press Enter after each argument; arguments may contain spaces. No shell is involved."
      />
      <v-textarea
        v-else
        v-model="commands[index] as string"
        label="Shell command"
        rows="1"
        auto-grow
        spellcheck="false"
        class="monospace"
        v-bind="bind([...path, index])"
      />
    </ItemCard>
  </div>
  <v-btn :prepend-icon="Plus" variant="tonal" size="small" @click="commands.push('')">Add {{ name }} entry</v-btn>
</template>

<style scoped>
.drag-handle {
  cursor: grab;
  display: inline-flex;
  padding: 4px;
}
/* The handle itself must be the drag source, not the icon inside it. */
.drag-handle :deep(svg) {
  pointer-events: none;
}
.drop-target {
  outline: 2px dashed rgb(var(--v-theme-primary));
  border-radius: 4px;
}
.monospace :deep(textarea) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.8125rem;
}
</style>
