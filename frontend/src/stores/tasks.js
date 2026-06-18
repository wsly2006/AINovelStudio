import { defineStore } from 'pinia'
import { ref } from 'vue'
import { tasksApi } from '../api/tasks'

export const useTasksStore = defineStore('tasks', () => {
  const items = ref([])
  const loading = ref(false)
  const projectId = ref(null)

  async function load(pid) {
    projectId.value = pid
    loading.value = true
    try {
      items.value = await tasksApi.list(pid)
    } finally {
      loading.value = false
    }
  }

  async function create(payload) {
    const t = await tasksApi.create(projectId.value, payload)
    items.value = [...items.value, t]
    await load(projectId.value)  // 重排序
    return t
  }

  async function update(id, payload) {
    const t = await tasksApi.update(id, payload)
    const i = items.value.findIndex((x) => x.id === id)
    if (i >= 0) items.value[i] = t
    await load(projectId.value)  // 状态变化会影响排序
    return t
  }

  async function remove(id) {
    await tasksApi.remove(id)
    items.value = items.value.filter((t) => t.id !== id)
  }

  function reset() {
    items.value = []
    projectId.value = null
  }

  return { items, loading, projectId, load, create, update, remove, reset }
})
