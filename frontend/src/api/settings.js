import client from './client'

export const settingsApi = {
  getAI: () => client.get('/settings/ai').then((r) => r.data),
  updateAI: (payload) => client.put('/settings/ai', payload).then((r) => r.data),
  testAI: () => client.post('/settings/ai/test').then((r) => r.data),
}
