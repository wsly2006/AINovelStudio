import { ref, watch, onBeforeUnmount } from 'vue'

/**
 * 自动保存状态机:idle → dirty → saving → saved (or error)
 * 用法:
 *   const { state, savedAt, flush } = useAutoSave(contentRef, async (content) => { ... }, { delay: 1500 })
 *
 * - contentRef 任意变更 → state 'dirty',防抖后调用 saveFn
 * - saveFn 抛错 → state 'error',按 RETRY_BACKOFF 退避重试,用尽后停下来等下次手动 flush 或内容再变
 * - flush() 立刻把当前内容保存上去,只要跟最近一次成功保存的快照不一致就一定会发请求
 * - 组件卸载前自动 flush 一次(fire-and-forget)
 */
// 失败退避序列(毫秒)。后端短暂抖动 5s 内能恢复,真挂了不应该死循环刷请求。
const RETRY_BACKOFF = [5_000, 15_000, 60_000]

export function useAutoSave(contentRef, saveFn, { delay = 1500 } = {}) {
  const state = ref('idle')
  const savedAt = ref(null)
  const lastError = ref(null)

  let timer = null
  let inflight = null
  // 最近一次成功保存的内容快照。用它判断是否真的有未落库的改动,
  // 而不是依赖「watcher 触发过没」—— 后者会被 Vue 的初始化时机坑掉。
  let lastSaved = contentRef.value
  // 当前内容连续失败次数;成功或内容变化重置为 0
  let retryCount = 0

  function clearTimer() {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  async function doSave() {
    clearTimer()
    if (state.value === 'saving') return inflight
    const snapshot = contentRef.value
    if (snapshot === lastSaved) {
      // 已经一致,不再发请求
      state.value = 'saved'
      return
    }
    state.value = 'saving'
    inflight = (async () => {
      try {
        await saveFn(snapshot)
        lastSaved = snapshot
        retryCount = 0
        // 期间又有变更,保持 dirty 继续排队;否则 saved
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
        // 退避重试:5s → 15s → 60s。用尽后停下来,等下次内容变化或手动 flush 重启
        if (retryCount < RETRY_BACKOFF.length) {
          const wait = RETRY_BACKOFF[retryCount]
          retryCount += 1
          timer = setTimeout(doSave, wait)
        }
        // else: 静默停在 error 状态,不再自动重试,避免后端长期不可用时刷爆请求
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

  watch(contentRef, (val) => {
    if (val === lastSaved) {
      // 程序化把内容设回上次保存值(切章 reload),不算 dirty
      return
    }
    // 用户重新输入 → 给重试预算清零,新内容值得再试
    retryCount = 0
    state.value = 'dirty'
    schedule()
  })

  async function flush() {
    if (inflight) await inflight
    // 只要当前内容跟最近成功保存的不一致,就 doSave —— 不管 state 是什么。
    // 这能挡住 watcher 还没来得及把 state 标 dirty 的竞争。
    if (contentRef.value !== lastSaved || state.value === 'error') {
      // 用户主动调 flush(切章 / 手动快照 / unmount 前),也算一次重置
      retryCount = 0
      await doSave()
    }
  }

  /**
   * 切换到新章节时调:把基线重置成新章节的初始内容,
   * 这样首次 watch 触发不会把当前章节的内容当成 dirty 写到新章节里。
   */
  function reset(newContent) {
    clearTimer()
    lastSaved = newContent
    retryCount = 0
    state.value = 'idle'
    lastError.value = null
  }

  onBeforeUnmount(() => {
    if (contentRef.value !== lastSaved) {
      // fire-and-forget,不阻塞卸载
      doSave().catch(() => {})
    }
    clearTimer()
  })

  return { state, savedAt, lastError, flush, reset }
}

