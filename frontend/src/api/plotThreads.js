import client from './client'

// 主线(PlotThread)API:跨章节情节线管理 + AI 草拟主线
export const plotThreadsApi = {
  list: (projectId) => client.get(`/projects/${projectId}/threads`).then((r) => r.data),
  create: (projectId, payload) =>
    client.post(`/projects/${projectId}/threads`, payload).then((r) => r.data),
  update: (threadId, payload) =>
    client.patch(`/threads/${threadId}`, payload).then((r) => r.data),
  remove: (threadId) => client.delete(`/threads/${threadId}`),
  // AI 基于工程总纲 + 简介 草拟 3-5 条主线,直接落库
  suggest: (projectId) =>
    client
      .post(`/projects/${projectId}/threads/suggest`, {}, { timeout: 90000 })
      .then((r) => r.data),
  // 这条主线相关的事件,按章节顺序铺开
  listEvents: (threadId) =>
    client.get(`/threads/${threadId}/events`).then((r) => r.data),
}
