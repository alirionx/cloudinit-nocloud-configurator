// FR-015: ask before leaving the editor with unsaved changes.
import { type Ref, onBeforeUnmount, onMounted, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'

export function useUnsavedGuard(dirty: Ref<boolean>) {
  /** Pending navigation waiting for the user's decision. */
  const pending = ref<((leave: boolean) => void) | null>(null)

  onBeforeRouteLeave(() => {
    if (!dirty.value) return true
    return new Promise<boolean>((resolve) => {
      pending.value = (leave) => {
        pending.value = null
        resolve(leave)
      }
    })
  })

  // Browser reload/close: the browser shows its own confirmation.
  function onBeforeUnload(event: BeforeUnloadEvent) {
    if (dirty.value) event.preventDefault()
  }
  onMounted(() => window.addEventListener('beforeunload', onBeforeUnload))
  onBeforeUnmount(() => window.removeEventListener('beforeunload', onBeforeUnload))

  return { pending }
}
