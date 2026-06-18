import client from './client'

export const relationsApi = {
  list: (projectId) => client.get(`/projects/${projectId}/relations`).then((r) => r.data),
  create: (projectId, payload) =>
    client.post(`/projects/${projectId}/relations`, payload).then((r) => r.data),
  update: (id, payload) => client.patch(`/relations/${id}`, payload).then((r) => r.data),
  remove: (id) => client.delete(`/relations/${id}`),
  extractUrl: (projectId) => `/api/projects/${projectId}/relations/extract`,
}

export const plotApi = {
  listEvents: (projectId) => client.get(`/projects/${projectId}/plot/events`).then((r) => r.data),
  createEvent: (projectId, payload) =>
    client.post(`/projects/${projectId}/plot/events`, payload).then((r) => r.data),
  updateEvent: (id, payload) => client.patch(`/plot/events/${id}`, payload).then((r) => r.data),
  removeEvent: (id) => client.delete(`/plot/events/${id}`),
  extractUrl: (projectId) => `/api/projects/${projectId}/plot/extract`,
  // 一致性扫描:返回 {run_id, issues, open_count},新发现的 issue 已落库
  check: (projectId) =>
    client.post(`/projects/${projectId}/plot/check`, {}, { timeout: 120000 }).then((r) => r.data),
}

// 一致性问题(持久化):跨次扫描追踪还没解决的矛盾 / 伏笔未收
export const issuesApi = {
  list: (projectId, status) => {
    const url = status
      ? `/projects/${projectId}/issues?status=${encodeURIComponent(status)}`
      : `/projects/${projectId}/issues`
    return client.get(url).then((r) => r.data)
  },
  openCount: (projectId) =>
    client.get(`/projects/${projectId}/issues/open-count`).then((r) => r.data),
  setStatus: (issueId, status) =>
    client.patch(`/issues/${issueId}`, { status }).then((r) => r.data),
  remove: (issueId) => client.delete(`/issues/${issueId}`),
}

