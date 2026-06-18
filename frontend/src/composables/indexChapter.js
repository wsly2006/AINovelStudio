// 索引本章:把当前章一次性喂给 5 个 AI 抽取接口(人物 / 世界观 / 物品 / 关系 / 情节),
// 全部走 merge,串行执行避免后端 SQLite 写入冲突。
// 调用方传 onProgress 监听每一步,onDone 拿到聚合结果。
import { streamProgressSSE } from '../api/sse'

const STEPS = [
  {
    key: 'characters',
    url: (pid) => `/api/projects/${pid}/characters/extract`,
    body: (chapterId) => ({ chapter_ids: [chapterId], mode: 'merge' }),
  },
  {
    key: 'world',
    url: (pid) => `/api/projects/${pid}/world/extract`,
    body: (chapterId) => ({ chapter_ids: [chapterId], mode: 'merge' }),
  },
  {
    key: 'items',
    url: (pid) => `/api/projects/${pid}/items/extract`,
    body: (chapterId) => ({ chapter_ids: [chapterId], mode: 'merge' }),
  },
  {
    key: 'relations',
    url: (pid) => `/api/projects/${pid}/relations/extract`,
    body: (chapterId) => ({ chapter_ids: [chapterId] }),
  },
  {
    key: 'plot',
    url: (pid) => `/api/projects/${pid}/plot/extract`,
    body: (chapterId) => ({ chapter_ids: [chapterId] }),
  },
]

/**
 * @param projectId 工程 id
 * @param chapterId 章节 id
 * @param handlers { onStepStart, onStepDone, onStepError, signal }
 *   - onStepStart(key) 进入某一步时回调,UI 用来高亮 / 显示 loading
 *   - onStepDone(key, { extracted }) 成功完成
 *   - onStepError(key, message) 单步失败,会继续下一步,不中断整体
 */
export async function indexChapter(projectId, chapterId, handlers = {}) {
  const { onStepStart, onStepDone, onStepError, signal } = handlers
  const summary = {}
  for (const step of STEPS) {
    if (signal?.aborted) break
    onStepStart?.(step.key)
    let extracted = 0
    let failed = false
    let errorMsg = ''
    await streamProgressSSE(step.url(projectId), step.body(chapterId), {
      signal,
      onDone: (data) => {
        extracted = Number(data?.extracted) || 0
      },
      onError: (msg) => {
        failed = true
        errorMsg = msg || 'error'
      },
    })
    if (failed) {
      summary[step.key] = { error: errorMsg }
      onStepError?.(step.key, errorMsg)
    } else {
      summary[step.key] = { extracted }
      onStepDone?.(step.key, { extracted })
    }
  }
  return summary
}

export const INDEX_STEPS = STEPS.map((s) => s.key)
