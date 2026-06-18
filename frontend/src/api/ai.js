import client from './client'

export const aiApi = {
  info: () => client.get('/ai/info').then((r) => r.data),
  // 流式接口走 streamSSE,不在此处包装
}

/**
 * 通过 fetch 流式消费后端的 SSE 响应。
 * 原因:浏览器原生 EventSource 不支持 POST + 自定义 body。
 *
 * @param {string} url 相对 url(如 '/api/chapters/1/ai/generate')
 * @param {object} body POST 请求体
 * @param {object} handlers
 *   - onDelta(text): 收到一段增量
 *   - onDone(): 流正常结束
 *   - onError(message): 服务端 event:error 或网络异常
 *   - signal?: AbortSignal,用于停止
 */
export async function streamSSE(url, body, { onDelta, onDone, onError, signal } = {}) {
  // url 用相对路径,走 vite 代理
  const fullUrl = url.startsWith('/api/') ? url : `/api${url.startsWith('/') ? '' : '/'}${url}`

  let resp
  try {
    resp = await fetch(fullUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify(body || {}),
      signal,
    })
  } catch (e) {
    if (e.name === 'AbortError') return
    onError?.(e.message)
    return
  }

  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`
    try {
      const data = await resp.json()
      if (data?.detail) detail = data.detail
    } catch {}
    onError?.(detail)
    return
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  // SSE 事件分隔符在不同实现里有 \n\n 也有 \r\n\r\n,统一用正则匹配
  const SEP_RE = /\r?\n\r?\n/

  function flushBlock(block) {
    const lines = block.split(/\r?\n/)
    let event = 'message'
    const dataLines = []
    for (const line of lines) {
      if (!line) continue
      if (line.startsWith('event:')) event = line.slice(6).trim()
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
    }
    if (!dataLines.length) return
    const dataStr = dataLines.join('\n')
    let parsed
    try {
      parsed = JSON.parse(dataStr)
    } catch {
      parsed = { text: dataStr }
    }
    if (event === 'delta') onDelta?.(parsed.text || '')
    else if (event === 'done') onDone?.()
    else if (event === 'error') onError?.(parsed.message || 'AI error')
  }

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let m
      while ((m = SEP_RE.exec(buffer))) {
        const block = buffer.slice(0, m.index)
        buffer = buffer.slice(m.index + m[0].length)
        flushBlock(block)
      }
    }
    if (buffer.trim()) flushBlock(buffer)
  } catch (e) {
    if (e.name === 'AbortError') return
    onError?.(e.message)
  }
}
