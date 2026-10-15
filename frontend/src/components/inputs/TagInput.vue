<script setup lang="ts">
// FR-007: tag input. Entries are separated by Enter, comma or space (or only Enter),
// shown as removable chips and de-duplicated; pasted lists are split as well.
import { computed, ref } from 'vue'
import { type Path, useField, useIssues } from '../../composables/issues'
import { mergeTags } from '../../form'

const model = defineModel<string[]>({ required: true })
const props = withDefaults(
  defineProps<{
    path: Path
    label: string
    hint?: string
    placeholder?: string
    /** 'whitespace': Enter, comma, space; 'enter': only Enter (values may contain spaces). */
    split?: 'whitespace' | 'enter'
  }>(),
  { hint: undefined, placeholder: undefined, split: 'whitespace' },
)

const issues = useIssues()
const field = useField(() => props.path)
const text = ref('')

const separators = computed(() => (props.split === 'enter' ? /\n+/ : /[\s,]+/))

const errorMessages = computed(() => [
  ...field.value['error-messages'],
  ...issues.itemErrorsAt(props.path).map(({ index, msg }) => `"${model.value[index] ?? index + 1}": ${msg}`),
])
const invalid = computed(() => new Set(issues.itemErrorsAt(props.path).map(({ index }) => index)))

function commit() {
  if (text.value.trim()) model.value = mergeTags(model.value, text.value, separators.value)
  text.value = ''
}

function onInput(value: string) {
  text.value = value
  // A typed or pasted separator commits the entries before it right away.
  if (props.split === 'whitespace' && /[\s,]/.test(value)) {
    const parts = value.split(separators.value)
    const rest = /[\s,]$/.test(value) ? '' : (parts.pop() ?? '')
    model.value = mergeTags(model.value, parts, separators.value)
    text.value = rest
  }
}

function onPaste(event: ClipboardEvent) {
  const pasted = event.clipboardData?.getData('text') ?? ''
  if (/[\n,]/.test(pasted) || (props.split === 'whitespace' && /\s/.test(pasted))) {
    event.preventDefault()
    model.value = mergeTags(model.value, text.value + pasted, props.split === 'enter' ? /\n+/ : /[\s,]+/)
    text.value = ''
  }
}

/** Backspace in an empty input puts the last entry back into the input for editing. */
function onBackspace(event: KeyboardEvent) {
  if (text.value || !model.value.length) return
  event.preventDefault()
  text.value = model.value[model.value.length - 1]!
  model.value = model.value.slice(0, -1)
}

function remove(index: number) {
  model.value = model.value.filter((_, i) => i !== index)
}

function onBlur() {
  commit()
  field.value.onBlur()
}
</script>

<template>
  <div class="tag-input">
    <v-text-field
      :id="field.id"
      :model-value="text"
      :label="label"
      :hint="hint"
      :persistent-hint="!!hint"
      :placeholder="placeholder"
      :error-messages="errorMessages"
      :messages="field.messages"
      :class="field.class"
      autocomplete="off"
      spellcheck="false"
      @update:model-value="onInput"
      @keydown.enter.prevent="commit"
      @keydown.backspace="onBackspace"
      @paste="onPaste"
      @blur="onBlur"
    >
      <template v-if="model.length" #prepend-inner>
        <div class="d-flex flex-wrap ga-1 py-1 chips">
          <v-chip
            v-for="(value, index) in model"
            :key="value"
            size="small"
            closable
            :color="invalid.has(index) ? 'error' : undefined"
            :close-label="`Remove ${value}`"
            @click:close="remove(index)"
          >
            {{ value }}
          </v-chip>
        </div>
      </template>
    </v-text-field>
  </div>
</template>

<style scoped>
.chips {
  max-width: 70%;
}
.tag-input :deep(.v-field__prepend-inner) {
  align-items: center;
}
</style>
