import client from './client'

export const itemsApi = {
  list: (projectId) =>
    client.get(`/projects/${projectId}/items`).then((r) => r.data),
  get: (id) => client.get(`/items/${id}`).then((r) => r.data),
  create: (projectId, payload) =>
    client.post(`/projects/${projectId}/items`, payload).then((r) => r.data),
  update: (id, payload) => client.patch(`/items/${id}`, payload).then((r) => r.data),
  remove: (id) => client.delete(`/items/${id}`),
  extractUrl: (projectId) => `/api/projects/${projectId}/items/extract`,
}
