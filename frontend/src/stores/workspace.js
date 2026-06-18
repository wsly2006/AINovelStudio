import { defineStore } from 'pinia'
import { ref } from 'vue'
import { projectsApi } from '../api/projects'
import { chaptersApi } from '../api/chapters'

export const useWorkspaceStore = defineStore('workspace', () => {
  const project = ref(null)
  const chapters = ref([])
  const selectedId = ref(null)
  const loading = ref(false)

  async function loadProject(projectId) {
    loading.value = true
    try {
      const [p, list] = await Promise.all([
        projectsApi.get(projectId),
        chaptersApi.list(projectId),
      ])
      project.value = p
      chapters.value = list
      // 默认选中第一章(若存在)
      if (list.length > 0 && !list.some((c) => c.id === selectedId.value)) {
        selectedId.value = list[0].id
      } else if (list.length === 0) {
        selectedId.value = null
      }
    } finally {
      loading.value = false
    }
  }

  async function createChapter(payload) {
    const body = typeof payload === 'string' ? { title: payload } : payload
    const created = await chaptersApi.create(project.value.id, body)
    chapters.value = [...chapters.value, created]
    selectedId.value = created.id
    return created
  }

  async function renameChapter(chapterId, title) {
    const updated = await chaptersApi.update(chapterId, { title })
    const i = chapters.value.findIndex((c) => c.id === chapterId)
    if (i >= 0) {
      // 仅更新元字段,避免覆盖列表项 schema 中可能不存在的 content
      chapters.value[i] = {
        ...chapters.value[i],
        title: updated.title,
        updated_at: updated.updated_at,
      }
    }
  }

  async function updateChapterMeta(chapterId, payload) {
    const updated = await chaptersApi.update(chapterId, payload)
    const i = chapters.value.findIndex((c) => c.id === chapterId)
    if (i >= 0) {
      chapters.value[i] = {
        ...chapters.value[i],
        title: updated.title,
        summary: updated.summary,
        updated_at: updated.updated_at,
      }
    }
  }

  async function removeChapter(chapterId) {
    await chaptersApi.remove(chapterId)
    chapters.value = chapters.value.filter((c) => c.id !== chapterId)
    if (selectedId.value === chapterId) {
      selectedId.value = chapters.value[0]?.id ?? null
    }
  }

  async function reorder(newList) {
    // 乐观更新:先改本地,失败则恢复
    const prev = chapters.value
    chapters.value = newList
    try {
      const updated = await chaptersApi.reorder(
        project.value.id,
        newList.map((c) => c.id)
      )
      chapters.value = updated
    } catch (e) {
      chapters.value = prev
      throw e
    }
  }

  function select(chapterId) {
    selectedId.value = chapterId
  }

  function applyContentSaved(chapterId, savedMeta) {
    const i = chapters.value.findIndex((c) => c.id === chapterId)
    if (i >= 0) {
      chapters.value[i] = {
        ...chapters.value[i],
        word_count: savedMeta.word_count,
        updated_at: savedMeta.updated_at,
      }
    }
  }

  function reset() {
    project.value = null
    chapters.value = []
    selectedId.value = null
  }

  return {
    project,
    chapters,
    selectedId,
    loading,
    loadProject,
    createChapter,
    renameChapter,
    updateChapterMeta,
    removeChapter,
    reorder,
    select,
    applyContentSaved,
    reset,
  }
})
