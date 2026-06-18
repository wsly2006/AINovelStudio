import client from './client'

export const statsApi = {
  // date 形如 YYYY-MM-DD,留空表示今天
  tokens: (date) =>
    client.get('/stats/tokens', { params: date ? { date } : {} }).then((r) => r.data),
}
