import client from './client'

export const chapterScoresApi = {
  list: (chapterId) =>
    client.get(`/chapters/${chapterId}/scores`).then((r) => r.data),
  create: (chapterId) =>
    client.post(`/chapters/${chapterId}/scores`).then((r) => r.data),
  remove: (chapterId, scoreId) =>
    client.delete(`/chapters/${chapterId}/scores/${scoreId}`),
}
