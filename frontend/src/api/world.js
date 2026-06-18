import client from './client'

export const worldApi = {
  list: (projectId, kind = null) => {
    const params = kind ? { kind } : {}
    return client.get(`/projects/${projectId}/world`, { params }).then((r) => r.data)
  },
  get: (id) => client.get(`/world/${id}`).then((r) => r.data),
  create: (projectId, payload) =>
    client.post(`/projects/${projectId}/world`, payload).then((r) => r.data),
  update: (id, payload) => client.patch(`/world/${id}`, payload).then((r) => r.data),
  remove: (id) => client.delete(`/world/${id}`),
  extractUrl: (projectId) => `/api/projects/${projectId}/world/extract`,
}
