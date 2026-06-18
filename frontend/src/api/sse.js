/**
 * 通用 SSE 工具,处理 progress / start / done / error / cancelled / result 等自定义事件。
 *
 * 默认走 POST(老用法,SSE 起步即提交参数);
 * 传 method: 'GET' 时不带 body,用于订阅一个已经在后端运行的任务。
 *
 * @param url 完整 url
 * @param body POST body(GET 时忽略)
 * @param handlers { onStart, onProgress, onDone, onError, onCancelled, onResult, onAny, signal, method }
 */
export async function streamProgressSSE(url, body, handlers = {}) {
  const {
    onStart, onProgress, onDone, onError, onCancelled, onResult, onAny,
    signal,
    method = 'POST',
  } = handlers
  let resp
  try {
    const init = {
      method,
      headers: { Accept: 'text/event-stream' },
      signal,
    }
    if (method === 'POST') {
      init.headers['Content-Type'] = 'application/json'
      init.body = JSON.stringify(body || {})
    }
    resp = await fetch(url, init)
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
    onError?.(detail, resp.status)
    return
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  // SSE 事件分隔符在不同实现里有 \n\n 也有 \r\n\r\n,统一用正则匹配
  const SEP_RE = /\r?\n\r?\n/

  function dispatch(block) {
    const lines = block.split(/\r?\n/)
    let event = 'message'
    const dataLines = []
    for (const line of lines) {
      if (!line) continue
      if (line.startsWith('event:')) event = line.slice(6).trim()
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
    }
    if (!dataLines.length) return
    let data
    try {
      data = JSON.parse(dataLines.join('\n'))
    } catch {
      data = {}
    }
    onAny?.(event, data)
    if (event === 'start') onStart?.(data)
    else if (event === 'progress') onProgress?.(data)
    else if (event === 'result') onResult?.(data)
    else if (event === 'done') onDone?.(data)
    else if (event === 'cancelled') onCancelled?.(data)
    else if (event === 'error') onError?.(data.message || 'error')
  }

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let m
      while ((m = SEP_RE.exec(buffer))) {
        dispatch(buffer.slice(0, m.index))
        buffer = buffer.slice(m.index + m[0].length)
      }
    }
    if (buffer.trim()) dispatch(buffer)
  } catch (e) {
    if (e.name === 'AbortError') return
    onError?.(e.message)
  }
}
