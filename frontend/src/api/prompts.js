import client from './client'

export const promptsApi = {
  list: () => client.get('/prompts').then((r) => r.data),
  update: (key, payload) => client.put(`/prompts/${key}`, payload).then((r) => r.data),
  reset: (key) => client.post(`/prompts/${key}/reset`).then((r) => r.data),
}
