import { defineStore } from 'pinia'
import { ref } from 'vue'
import { glossaryApi } from '../api/glossary'

export const useGlossaryStore = defineStore('glossary', () => {
  const items = ref([])
  const loading = ref(false)
  const projectId = ref(null)

  async function load(pid, params = {}) {
    projectId.value = pid
    loading.value = true
    try {
      items.value = await glossaryApi.list(pid, params)
    } finally {
      loading.value = false
    }
  }

  async function create(payload) {
    const e = await glossaryApi.create(projectId.value, payload)
    items.value = [...items.value, e]
    return e
  }

  async function update(id, payload) {
    const e = await glossaryApi.update(id, payload)
    const i = items.value.findIndex((x) => x.id === id)
    if (i >= 0) items.value[i] = e
    return e
  }

  async function remove(id) {
    await glossaryApi.remove(id)
    items.value = items.value.filter((e) => e.id !== id)
  }

  // seed 完之后强制 reload —— 服务端可能跳过/合并/新增,本地无法精算
  async function seed(payload) {
    const result = await glossaryApi.seed(projectId.value, payload)
    await load(projectId.value, { target_lang: payload.target_lang })
    return result
  }

  function reset() {
    items.value = []
    projectId.value = null
  }

  return { items, loading, projectId, load, create, update, remove, seed, reset }
})
