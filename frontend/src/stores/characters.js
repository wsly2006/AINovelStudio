import { defineStore } from 'pinia'
import { ref } from 'vue'
import { charactersApi } from '../api/characters'

export const useCharactersStore = defineStore('characters', () => {
  const items = ref([])
  const loading = ref(false)
  const projectId = ref(null)

  async function load(pid) {
    projectId.value = pid
    loading.value = true
    try {
      items.value = await charactersApi.list(pid)
    } finally {
      loading.value = false
    }
  }

  async function create(payload) {
    const c = await charactersApi.create(projectId.value, payload)
    items.value = [...items.value, c]
    return c
  }

  async function update(id, payload) {
    const c = await charactersApi.update(id, payload)
    const i = items.value.findIndex((x) => x.id === id)
    if (i >= 0) items.value[i] = c
    return c
  }

  async function remove(id) {
    await charactersApi.remove(id)
    items.value = items.value.filter((c) => c.id !== id)
  }

  function reset() {
    items.value = []
    projectId.value = null
  }

  return { items, loading, projectId, load, create, update, remove, reset }
})
