// 在 chapter content 中模糊定位 quote 片段。
// 模型偶尔会改字 / 合并标点 / 漏字,精确 indexOf 失败时退化为最长公共子串(LCS)兜底。
// 返回 [from, to](包含 from,不包含 to)或 null。

const MIN_MATCH_LEN = 12

export function locateQuote(content, quote) {
  if (!content || !quote) return null
  const q = quote.trim()
  if (!q) return null

  // 1) 精确匹配:大多数情况能命中
  const direct = content.indexOf(q)
  if (direct >= 0) return [direct, direct + q.length]

  // 2) 去标点 / 空白后再尝试一次:模型把"…"改成"……"之类的小差异
  const stripped = q.replace(/[\s　\p{P}]/gu, '')
  if (stripped.length >= MIN_MATCH_LEN) {
    const map = []
    let plain = ''
    for (let i = 0; i < content.length; i++) {
      const ch = content[i]
      if (/[\s　\p{P}]/u.test(ch)) continue
      plain += ch
      map.push(i)
    }
    const idx = plain.indexOf(stripped)
    if (idx >= 0 && idx + stripped.length - 1 < map.length) {
      const from = map[idx]
      const to = map[idx + stripped.length - 1] + 1
      return [from, to]
    }
  }

  // 3) 兜底:在 quote 上滑动取最长能命中的连续子串(粗暴但够用)
  const span = longestSubstringMatch(content, q)
  if (span && span.length >= MIN_MATCH_LEN) return [span.from, span.to]
  return null
}

// 在 quote 中找一段最长连续子串,使其在 content 中也连续出现;返回该串在 content 中的位置。
function longestSubstringMatch(content, quote) {
  const n = content.length
  const m = quote.length
  if (n === 0 || m === 0) return null

  // DP 太重,实际 quote 通常 30~120 字。
  // 用滚动行的 LCS-substring,内存 O(min(n,m))。
  // 这里逐行处理 quote(短),列扫 content(长)。
  let prev = new Uint16Array(n + 1)
  let curr = new Uint16Array(n + 1)
  let best = 0
  let bestEndContent = 0
  for (let i = 1; i <= m; i++) {
    const qi = quote.charCodeAt(i - 1)
    for (let j = 1; j <= n; j++) {
      if (qi === content.charCodeAt(j - 1)) {
        const v = prev[j - 1] + 1
        curr[j] = v
        if (v > best) {
          best = v
          bestEndContent = j
        }
      } else {
        curr[j] = 0
      }
    }
    const tmp = prev
    prev = curr
    curr = tmp
    curr.fill(0)
  }
  if (best === 0) return null
  return {
    from: bestEndContent - best,
    to: bestEndContent,
    length: best,
  }
}
