import client from './client'

export const stateEventsApi = {
  list: (projectId, { characterId = null, chapterId = null } = {}) => {
    const params = {}
    if (characterId) params.character_id = characterId
    if (chapterId) params.chapter_id = chapterId
    return client.get(`/projects/${projectId}/state-events`, { params }).then((r) => r.data)
  },
  create: (characterId, payload) =>
    client.post(`/characters/${characterId}/state-events`, payload).then((r) => r.data),
  update: (id, payload) => client.patch(`/state-events/${id}`, payload).then((r) => r.data),
  remove: (id) => client.delete(`/state-events/${id}`),
  snapshot: (characterId, asOfChapterId = null) => {
    const params = asOfChapterId ? { as_of_chapter_id: asOfChapterId } : {}
    return client.get(`/characters/${characterId}/snapshot`, { params }).then((r) => r.data)
  },
}
