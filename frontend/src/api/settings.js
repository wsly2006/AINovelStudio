import client from './client'

export const settingsApi = {
  getAI: () => client.get('/settings/ai').then((r) => r.data),
  updateAI: (payload) => client.put('/settings/ai', payload).then((r) => r.data),
  updateReview: (payload) =>
    client.put('/settings/ai/review', payload).then((r) => r.data),
  // role: 'writing' | 'review',默认 writing
  testAI: (role = 'writing') =>
    client.post('/settings/ai/test', null, { params: { role } }).then((r) => r.data),
}
