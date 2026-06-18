import { defineStore } from 'pinia'
import { ref } from 'vue'
import { itemsApi } from '../api/items'

export const useItemsStore = defineStore('items', () => {
  const items = ref([])
  const loading = ref(false)
  const projectId = ref(null)

  async function load(pid) {
    projectId.value = pid
    loading.value = true
    try {
      items.value = await itemsApi.list(pid)
    } finally {
      loading.value = false
    }
  }

  async function create(payload) {
    const e = await itemsApi.create(projectId.value, payload)
    items.value = [...items.value, e]
    return e
  }

  async function update(id, payload) {
    const e = await itemsApi.update(id, payload)
    const i = items.value.findIndex((x) => x.id === id)
    if (i >= 0) items.value[i] = e
    return e
  }

  async function remove(id) {
    await itemsApi.remove(id)
    items.value = items.value.filter((e) => e.id !== id)
  }

  function reset() {
    items.value = []
    projectId.value = null
  }

  return { items, loading, projectId, load, create, update, remove, reset }
})
