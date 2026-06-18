import client from './client'

export const chapterStyleChecksApi = {
  list: (chapterId) =>
    client.get(`/chapters/${chapterId}/style-checks`).then((r) => r.data),
  create: (chapterId) =>
    client.post(`/chapters/${chapterId}/style-checks`).then((r) => r.data),
  remove: (chapterId, checkId) =>
    client.delete(`/chapters/${chapterId}/style-checks/${checkId}`),
}
