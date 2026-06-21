import client from './client'

export const platformsApi = {
  list: () => client.get('/platforms').then((r) => r.data),
  get: (id) => client.get(`/platforms/${id}`).then((r) => r.data),
  create: (payload) => client.post('/platforms', payload).then((r) => r.data),
  update: (id, payload) => client.patch(`/platforms/${id}`, payload).then((r) => r.data),
  remove: (id) => client.delete(`/platforms/${id}`),
}
