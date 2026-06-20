import client from './client'

export const assistantApi = {
  listConversations: (projectId) =>
    client.get(`/projects/${projectId}/ai/conversations`).then((r) => r.data),
  createConversation: (projectId, payload = {}) =>
    client.post(`/projects/${projectId}/ai/conversations`, payload).then((r) => r.data),
  updateConversation: (conversationId, payload) =>
    client.patch(`/ai/conversations/${conversationId}`, payload).then((r) => r.data),
  deleteConversation: (conversationId) =>
    client.delete(`/ai/conversations/${conversationId}`),
  listMessages: (conversationId) =>
    client.get(`/ai/conversations/${conversationId}/messages`).then((r) => r.data),
  previewPrompt: (conversationId, payload) =>
    client.post(`/ai/conversations/${conversationId}/preview-prompt`, payload).then((r) => r.data),
}
