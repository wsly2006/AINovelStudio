import { defineStore } from 'pinia'
import { ref } from 'vue'
import { laddersApi } from '../api/ladders'

export const useLaddersStore = defineStore('ladders', () => {
  const items = ref([])
  const loading = ref(false)
  const projectId = ref(null)

  async function load(pid) {
    projectId.value = pid
    loading.value = true
    try {
      items.value = await laddersApi.list(pid)
    } finally {
      loading.value = false
    }
  }

  async function create(payload) {
    const l = await laddersApi.create(projectId.value, payload)
    items.value = [...items.value, l]
    return l
  }

  async function update(id, payload) {
    const l = await laddersApi.update(id, payload)
    const i = items.value.findIndex((x) => x.id === id)
    if (i >= 0) items.value[i] = l
    return l
  }

  async function remove(id) {
    await laddersApi.remove(id)
    items.value = items.value.filter((l) => l.id !== id)
  }

  function reset() {
    items.value = []
    projectId.value = null
  }

  return { items, loading, projectId, load, create, update, remove, reset }
})
