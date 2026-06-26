import client from './client'

export const glossaryApi = {
  list: (projectId, params = {}) =>
    client
      .get(`/projects/${projectId}/glossary`, { params })
      .then((r) => r.data),
  get: (id) => client.get(`/glossary/${id}`).then((r) => r.data),
  create: (projectId, payload) =>
    client.post(`/projects/${projectId}/glossary`, payload).then((r) => r.data),
  update: (id, payload) =>
    client.patch(`/glossary/${id}`, payload).then((r) => r.data),
  remove: (id) => client.delete(`/glossary/${id}`),
  // 从工程现有人物 / 物品 / 世界观批量灌入
  seed: (projectId, payload) =>
    client
      .post(`/projects/${projectId}/glossary/seed`, payload)
      .then((r) => r.data),
  // M4:跨章一致性报告
  checkConsistency: (projectId, targetLang = 'en-US') =>
    client
      .get(`/projects/${projectId}/translation-consistency`, {
        params: { target_lang: targetLang },
      })
      .then((r) => r.data),
}
