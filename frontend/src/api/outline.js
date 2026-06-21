import client from './client'

export const outlineApi = {
  // 让 AI 一次性草拟连续 N 章大纲。返回 { drafts: [{title, summary, beats}] }。
  // 不落库,前端预览/调整后再调 batchCreate。
  batchSuggest: (projectId, payload) =>
    client
      .post(`/projects/${projectId}/outline/batch-suggest`, payload, {
        timeout: 180000,
      })
      .then((r) => r.data),
  // 把草稿数组追加到工程末尾(status='outlined')。
  batchCreate: (projectId, drafts) =>
    client
      .post(`/projects/${projectId}/outline/batch-create`, { drafts })
      .then((r) => r.data),
  // 章节正文 vs 大纲对账。返回 { summary_status, summary_note, beats, overall_note, covered, partial, missing }
  checkAlignment: (chapterId) =>
    client
      .post(`/chapters/${chapterId}/outline-alignment`, {}, { timeout: 90000 })
      .then((r) => r.data),
}
