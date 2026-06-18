import { ref, watch, onBeforeUnmount } from 'vue'

/**
 * 自动保存状态机:idle → dirty → saving → saved (or error)
 * 用法:
 *   const { state, savedAt, flush } = useAutoSave(contentRef, async (content) => { ... }, { delay: 1500 })
 *
 * - contentRef 任意变更 → state 'dirty',防抖后调用 saveFn
 * - saveFn 抛错 → state 'error',留下 lastError 给调用方读取
 * - flush() 立刻触发保存,返回 Promise,用于切换章节前 flush
 * - 组件卸载前自动 flush 一次(fire-and-forget)
 */
export function useAutoSave(contentRef, saveFn, { delay = 1500 } = {}) {
  const state = ref('idle')
  const savedAt = ref(null)
  const lastError = ref(null)

  let timer = null
  let inflight = null
  // 第一次 watch 触发是初始化赋值,跳过它
  let primed = false

  function clearTimer() {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  async function doSave() {
    clearTimer()
    if (state.value === 'saving') return inflight
    state.value = 'saving'
    const snapshot = contentRef.value
    inflight = (async () => {
      try {
        await saveFn(snapshot)
        // 期间又有变更,保持 dirty;否则 saved
        if (contentRef.value === snapshot) {
          state.value = 'saved'
          savedAt.value = new Date()
          lastError.value = null
        } else {
          state.value = 'dirty'
          schedule()
        }
      } catch (e) {
        lastError.value = e
        state.value = 'error'
        // 简易退避重试:5 秒后再试一次
        timer = setTimeout(doSave, 5000)
      } finally {
        inflight = null
      }
    })()
    return inflight
  }

  function schedule() {
    clearTimer()
    timer = setTimeout(doSave, delay)
  }

  watch(contentRef, () => {
    if (!primed) {
      primed = true
      return
    }
    state.value = 'dirty'
    schedule()
  })

  async function flush() {
    if (inflight) await inflight
    if (state.value === 'dirty' || state.value === 'error') {
      await doSave()
    }
  }

  onBeforeUnmount(() => {
    if (state.value === 'dirty' || state.value === 'error') {
      // fire-and-forget,不阻塞卸载
      doSave().catch(() => {})
    }
    clearTimer()
  })

  return { state, savedAt, lastError, flush }
}
