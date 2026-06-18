import client from './client'

export const chaptersApi = {
  list: (projectId) => client.get(`/projects/${projectId}/chapters`).then((r) => r.data),
  get: (chapterId) => client.get(`/chapters/${chapterId}`).then((r) => r.data),
  create: (projectId, payload) =>
    client.post(`/projects/${projectId}/chapters`, payload).then((r) => r.data),
  update: (chapterId, payload) =>
    client.patch(`/chapters/${chapterId}`, payload).then((r) => r.data),
  remove: (chapterId) => client.delete(`/chapters/${chapterId}`),
  reorder: (projectId, chapterIds) =>
    client
      .post(`/projects/${projectId}/chapters/reorder`, { chapter_ids: chapterIds })
      .then((r) => r.data),
  saveContent: (chapterId, content) =>
    client.put(`/chapters/${chapterId}/content`, { content }).then((r) => r.data),
}
