import client from './client'

export const chapterVersionsApi = {
  list: (chapterId) =>
    client.get(`/chapters/${chapterId}/versions`).then((r) => r.data),
  get: (chapterId, versionId) =>
    client.get(`/chapters/${chapterId}/versions/${versionId}`).then((r) => r.data),
  // 手动快照
  createManual: (chapterId, label) =>
    client.post(`/chapters/${chapterId}/versions`, { label: label || null }).then((r) => r.data),
  // AI 覆盖前快照,前端在 replace/append/insert 之前调一次
  snapshotBeforeAI: (chapterId) =>
    client.post(`/chapters/${chapterId}/versions/ai-snapshot`).then((r) => r.data),
  restore: (chapterId, versionId) =>
    client.post(`/chapters/${chapterId}/versions/${versionId}/restore`).then((r) => r.data),
  remove: (chapterId, versionId) =>
    client.delete(`/chapters/${chapterId}/versions/${versionId}`),
}
