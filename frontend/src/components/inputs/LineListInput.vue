<script setup lang="ts">
// A list edited as text, one entry per line (e.g. SSH public keys, FR-010, FR-011).
import { computed, ref, watch } from 'vue'
import { type Path, useField, useIssues } from '../../composables/issues'

const model = defineModel<string[]>({ required: true })
const props = defineProps<{ path: Path; label: string; hint?: string; placeholder?: string }>()

const issues = useIssues()
const field = useField(() => props.path)
const text = ref(model.value.join('\n'))

watch(model, (value) => {
  if (value.join('\n') !== text.value.split('\n').filter((l) => l.trim()).join('\n')) text.value = value.join('\n')
})

function update(value: string) {
  text.value = value
  model.value = value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

const errorMessages = computed(() => [
  ...field.value['error-messages'],
  ...issues.itemErrorsAt(props.path).map(({ index, msg }) => `Line ${index + 1}: ${msg}`),
])
</script>

<template>
  <v-textarea
    :id="field.id"
    :model-value="text"
    :label="label"
    :hint="hint"
    :persistent-hint="!!hint"
    :placeholder="placeholder"
    :error-messages="errorMessages"
    :messages="field.messages"
    :class="['monospace', field.class]"
    rows="2"
    auto-grow
    spellcheck="false"
    @update:model-value="update"
    @blur="field.onBlur"
  />
</template>

<style scoped>
.monospace :deep(textarea) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.8125rem;
}
</style>
