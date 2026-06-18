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
  check: (projectId) => client.post(`/projects/${projectId}/plot/check`).then((r) => r.data),
}
