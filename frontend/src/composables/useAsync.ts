import { ref, shallowRef } from 'vue'

/** Chargement / erreur / données d'un appel asynchrone. `data` est un shallowRef. */
export function useAsync<T>(fn: () => Promise<T>, { immediate = true } = {}) {
  const data = shallowRef<T>()
  const error = shallowRef<unknown>()
  const loading = ref(false)

  // Seul le dernier appel est pris en compte.
  let lastCall = 0

  async function run() {
    const call = ++lastCall
    loading.value = true
    error.value = undefined
    try {
      const result = await fn()
      if (call === lastCall) data.value = result
    } catch (e) {
      if (call === lastCall) error.value = e
    } finally {
      if (call === lastCall) loading.value = false
    }
  }

  if (immediate) void run()

  return { data, error, loading, run }
}
