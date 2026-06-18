import client from './client'

export const tasksApi = {
  list: (projectId, statusFilter = null) => {
    const params = statusFilter ? { status_filter: statusFilter } : {}
    return client.get(`/projects/${projectId}/tasks`, { params }).then((r) => r.data)
  },
  create: (projectId, payload) =>
    client.post(`/projects/${projectId}/tasks`, payload).then((r) => r.data),
  update: (id, payload) => client.patch(`/tasks/${id}`, payload).then((r) => r.data),
  remove: (id) => client.delete(`/tasks/${id}`),
}
