import client from './client'

export const voiceProfileApi = {
  get: (projectId) =>
    client.get(`/projects/${projectId}/voice-profile`).then((r) => r.data),
  upsert: (projectId, payload) =>
    client.put(`/projects/${projectId}/voice-profile`, payload).then((r) => r.data),
  remove: (projectId) => client.delete(`/projects/${projectId}/voice-profile`),
}
