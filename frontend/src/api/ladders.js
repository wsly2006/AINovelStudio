import client from './client'

export const laddersApi = {
  list: (projectId) => client.get(`/projects/${projectId}/ladders`).then((r) => r.data),
  get: (id) => client.get(`/ladders/${id}`).then((r) => r.data),
  create: (projectId, payload) =>
    client.post(`/projects/${projectId}/ladders`, payload).then((r) => r.data),
  update: (id, payload) => client.patch(`/ladders/${id}`, payload).then((r) => r.data),
  remove: (id) => client.delete(`/ladders/${id}`),
}
