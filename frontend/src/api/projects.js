import client from './client'

export const projectsApi = {
  list: () => client.get('/projects').then((r) => r.data),
  get: (id) => client.get(`/projects/${id}`).then((r) => r.data),
  create: (payload) => client.post('/projects', payload).then((r) => r.data),
  update: (id, payload) => client.patch(`/projects/${id}`, payload).then((r) => r.data),
  remove: (id) => client.delete(`/projects/${id}`),
  suggestTitle: (payload) =>
    client.post('/projects/ai-suggest/title', payload, { timeout: 60000 }).then((r) => r.data),
  suggestDescription: (payload) =>
    client
      .post('/projects/ai-suggest/description', payload, { timeout: 60000 })
      .then((r) => r.data),
}
