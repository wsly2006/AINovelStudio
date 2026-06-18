import { defineStore } from 'pinia'
import { ref } from 'vue'
import { projectsApi } from '../api/projects'

export const useProjectsStore = defineStore('projects', () => {
  const items = ref([])
  const loading = ref(false)

  async function refresh() {
    loading.value = true
    try {
      items.value = await projectsApi.list()
    } finally {
      loading.value = false
    }
  }

  async function remove(id) {
    await projectsApi.remove(id)
    items.value = items.value.filter((p) => p.id !== id)
  }

  return { items, loading, refresh, remove }
})
