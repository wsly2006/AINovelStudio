import { defineStore } from 'pinia'
import { ref } from 'vue'
import { worldApi } from '../api/world'

export const useWorldStore = defineStore('world', () => {
  const items = ref([])
  const loading = ref(false)
  const projectId = ref(null)

  async function load(pid) {
    projectId.value = pid
    loading.value = true
    try {
      items.value = await worldApi.list(pid)
    } finally {
      loading.value = false
    }
  }

  async function create(payload) {
    const e = await worldApi.create(projectId.value, payload)
    items.value = [...items.value, e]
    return e
  }

  async function update(id, payload) {
    const e = await worldApi.update(id, payload)
    const i = items.value.findIndex((x) => x.id === id)
    if (i >= 0) items.value[i] = e
    return e
  }

  async function remove(id) {
    await worldApi.remove(id)
    items.value = items.value.filter((e) => e.id !== id)
  }

  function reset() {
    items.value = []
    projectId.value = null
  }

  return { items, loading, projectId, load, create, update, remove, reset }
})
