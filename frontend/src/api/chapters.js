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
  // AI 草拟章节节拍。返回 {beats: [...]},不直接落库。
  suggestBeats: (chapterId, payload = {}) =>
    client
      .post(`/chapters/${chapterId}/ai/suggest-beats`, payload, { timeout: 90000 })
      .then((r) => r.data),
  // 单章自动索引:AI 写完正文落地后调,把这章的 plot_events 全删重抽,
  // 避免下次生成漏掉刚发生的事(沉默失败)。
  autoIndex: (chapterId) =>
    client
      .post(`/chapters/${chapterId}/auto-index`, {}, { timeout: 90000 })
      .then((r) => r.data),
  // 节拍-事件对账:写完 + 索引后调,逐拍判断 covered/partial/missing,
  // 结果落 chapter.beats_alignment。
  checkBeats: (chapterId) =>
    client
      .post(`/chapters/${chapterId}/ai/check-beats`, {}, { timeout: 90000 })
      .then((r) => r.data),
}
