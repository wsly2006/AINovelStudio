import client from './client'

export const charactersApi = {
  list: (projectId) => client.get(`/projects/${projectId}/characters`).then((r) => r.data),
  get: (id) => client.get(`/characters/${id}`).then((r) => r.data),
  create: (projectId, payload) =>
    client.post(`/projects/${projectId}/characters`, payload).then((r) => r.data),
  update: (id, payload) => client.patch(`/characters/${id}`, payload).then((r) => r.data),
  remove: (id) => client.delete(`/characters/${id}`),
  // SSE 端点见 streamSSE 工具,直接以路径调用即可
  extractUrl: (projectId) => `/api/projects/${projectId}/characters/extract`,
}
