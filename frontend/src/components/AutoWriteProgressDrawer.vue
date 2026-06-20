<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { streamProgressSSE } from '../api/sse'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  taskId: { type: String, default: '' },
  // 启动时拿到的初始数据
  initialChapterIds: { type: Array, default: () => [] },
  initialMode: { type: String, default: 'auto_fix' },
  initialThreshold: { type: Number, default: 70 },
})
const emit = defineEmits(['update:modelValue', 'finished', 'cancelled'])

// state.chapters 是按顺序的章节进度卡:每个 chapter 对应一项,边写边更新
const state = reactive({
  status: 'idle', // idle | running | done | cancelled | error
  errorMsg: '',
  startedAt: 0,
  total: 0,
  current: null, // 当前章节 id
  // chapter_id -> { chapter_index, order_index, title, attempt,
  //                 phase, chars, word_count, events_count,
  //                 covered, partial, missing, score, decision, reason }
  chapters: {},
  order: [],
  carryMissing: 0,
  carryPartial: 0,
  retryCount: 0,
  stoppedReason: '',
})

const ordered = computed(() => state.order.map((id) => state.chapters[id]).filter(Boolean))

const overallPercent = computed(() => {
  const done = ordered.value.filter((c) => c?.decision).length
  if (!state.total) return 0
  return Math.min(100, Math.round((done / state.total) * 100))
})

let abortCtrl = null

watch(
  () => [props.modelValue, props.taskId],
  ([visible, taskId]) => {
    if (!visible || !taskId) return
    resetState()
    state.status = 'running'
    state.startedAt = Date.now()
    state.total = props.initialChapterIds.length || 0
    subscribe(taskId)
  }
)

function resetState() {
  state.status = 'idle'
  state.errorMsg = ''
  state.total = 0
  state.current = null
  state.chapters = {}
  state.order = []
  state.carryMissing = 0
  state.carryPartial = 0
  state.retryCount = 0
  state.stoppedReason = ''
}

function ensureChapter(id) {
  if (!state.chapters[id]) {
    state.chapters[id] = {
      chapter_id: id,
      chapter_index: state.order.length + 1,
      order_index: null,
      title: '',
      attempt: 1,
      phase: 'pending',
      chars: 0,
      word_count: 0,
      events_count: 0,
      covered: 0,
      partial: 0,
      missing: 0,
      score: null,
      feedback: '',
      decision: null,
      reason: '',
    }
    state.order.push(id)
  }
  return state.chapters[id]
}

function subscribe(taskId) {
  abortCtrl = new AbortController()
  streamProgressSSE(`/api/ai-tasks/${taskId}/stream`, null, {
    method: 'GET',
    signal: abortCtrl.signal,
    onStart: ({ total }) => {
      if (total) state.total = total
    },
    onAny: (event, data) => {
      if (event === 'chapter_start') {
        const c = ensureChapter(data.chapter_id)
        c.chapter_index = data.chapter_index
        c.order_index = data.order_index
        c.title = data.title || ''
        c.attempt = data.attempt
        c.phase = 'generating'
        state.current = data.chapter_id
        if (data.attempt > 1) state.retryCount += 1
      } else if (event === 'generating') {
        const c = ensureChapter(data.chapter_id)
        c.chars = data.chars || 0
        c.phase = 'generating'
      } else if (event === 'generated') {
        const c = ensureChapter(data.chapter_id)
        c.word_count = data.word_count || 0
        c.phase = 'generated'
      } else if (event === 'indexing') {
        const c = ensureChapter(data.chapter_id)
        c.phase = 'indexing'
      } else if (event === 'indexed') {
        const c = ensureChapter(data.chapter_id)
        c.events_count = data.events_count || 0
        c.phase = 'indexed'
      } else if (event === 'aligning') {
        const c = ensureChapter(data.chapter_id)
        c.phase = 'aligning'
      } else if (event === 'aligned') {
        const c = ensureChapter(data.chapter_id)
        c.covered = data.covered || 0
        c.partial = data.partial || 0
        c.missing = data.missing || 0
        c.phase = 'aligned'
      } else if (event === 'scoring') {
        const c = ensureChapter(data.chapter_id)
        c.phase = 'scoring'
      } else if (event === 'scored') {
        const c = ensureChapter(data.chapter_id)
        c.score = typeof data.overall === 'number' ? data.overall : null
        c.feedback = data.feedback || ''
        c.phase = 'scored'
      } else if (event === 'chapter_done') {
        const c = ensureChapter(data.chapter_id)
        c.decision = data.decision
        c.reason = data.reason || ''
        c.phase = data.decision === 'retry' ? 'retrying' : 'done'
      }
    },
    onResult: (data) => {
      // result 在 done 之前到,把汇总记下来
      state.stoppedReason = data.stopped_reason || ''
    },
    onDone: () => {
      state.status = 'done'
      ElMessage.success(
        `自动连写完成,处理 ${ordered.value.filter((c) => c.decision).length} 章` +
          (state.stoppedReason ? ` · 已停下:${state.stoppedReason}` : '')
      )
      emit('finished', { chapterIds: state.order.slice() })
    },
    onCancelled: () => {
      state.status = 'cancelled'
      ElMessage.warning('自动连写已取消')
      emit('cancelled')
    },
    onError: (msg, statusCode) => {
      state.status = 'error'
      state.errorMsg = msg
      if (statusCode === 404) {
        ElMessage.warning('任务已过期或不存在')
      } else {
        ElMessage.error(`自动连写失败:${msg}`)
      }
    },
  })
}

async function onCancel() {
  if (!props.taskId || state.status !== 'running') return
  try {
    await ElMessageBox.confirm('确认中断自动连写?当前章节会保留已生成内容', '中断确认', {
      type: 'warning',
      confirmButtonText: '中断',
      cancelButtonText: '继续',
    })
  } catch {
    return
  }
  try {
    await fetch(`/api/ai-tasks/${props.taskId}`, { method: 'DELETE' })
  } catch {
    // 取消失败也不阻塞:服务器最终会通过 SSE 推 cancelled 帧
  }
}

function close() {
  if (state.status === 'running') {
    ElMessage.warning('任务仍在运行,关闭抽屉不会停止任务,可随时再次打开查看进度')
  }
  if (abortCtrl) {
    abortCtrl.abort()
    abortCtrl = null
  }
  emit('update:modelValue', false)
}

const PHASE_LABEL = {
  pending: '排队中',
  generating: '生成中',
  generated: '已生成',
  indexing: '索引中',
  indexed: '已索引',
  aligning: '节拍对账中',
  aligned: '已对账',
  scoring: '评分中',
  scored: '已评分',
  retrying: '重试中',
  done: '完成',
}

function phaseTag(phase) {
  if (['done'].includes(phase)) return 'success'
  if (phase === 'retrying') return 'warning'
  if (['pending'].includes(phase)) return 'info'
  return 'primary'
}

function decisionTag(d) {
  if (d === 'pass') return { type: 'success', text: '通过' }
  if (d === 'retry') return { type: 'warning', text: '重试' }
  if (d === 'stop') return { type: 'danger', text: '停下' }
  return null
}
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    title="AI 自动连写进度"
    direction="rtl"
    size="640px"
    :before-close="(done) => { close(); done() }"
  >
    <div class="overall">
      <div class="overall-row">
        <el-tag v-if="state.status === 'running'" type="primary">运行中</el-tag>
        <el-tag v-else-if="state.status === 'done'" type="success">已完成</el-tag>
        <el-tag v-else-if="state.status === 'cancelled'" type="warning">已取消</el-tag>
        <el-tag v-else-if="state.status === 'error'" type="danger">出错</el-tag>
        <span class="counter">{{ ordered.filter((c) => c.decision).length }} / {{ state.total }} 章</span>
        <span v-if="state.retryCount" class="retry-hint">已重试 {{ state.retryCount }} 次</span>
        <el-button
          v-if="state.status === 'running'"
          type="danger"
          size="small"
          @click="onCancel"
          style="margin-left: auto"
        >
          中断
        </el-button>
      </div>
      <el-progress :percentage="overallPercent" :stroke-width="8" />
      <div v-if="state.errorMsg" class="error-line">{{ state.errorMsg }}</div>
      <div v-if="state.stoppedReason" class="stop-line">{{ state.stoppedReason }}</div>
    </div>

    <div class="cards">
      <div
        v-for="c in ordered"
        :key="c.chapter_id"
        class="card"
        :class="{ active: state.current === c.chapter_id && state.status === 'running' }"
      >
        <div class="card-head">
          <span class="title">
            第 {{ c.order_index || '?' }} 章 {{ c.title }}
          </span>
          <el-tag size="small" :type="phaseTag(c.phase)">{{ PHASE_LABEL[c.phase] || c.phase }}</el-tag>
          <el-tag v-if="c.attempt > 1" size="small" type="warning" effect="plain">
            第 {{ c.attempt }} 次
          </el-tag>
          <el-tag
            v-if="decisionTag(c.decision)"
            size="small"
            :type="decisionTag(c.decision).type"
            effect="dark"
          >
            {{ decisionTag(c.decision).text }}
          </el-tag>
        </div>
        <div class="metrics">
          <div class="m">
            <span class="m-label">生成</span>
            <span class="m-val">{{ c.word_count || c.chars || 0 }} 字</span>
          </div>
          <div class="m">
            <span class="m-label">事件</span>
            <span class="m-val">{{ c.events_count }}</span>
          </div>
          <div class="m">
            <span class="m-label">节拍</span>
            <span class="m-val">
              <span class="ok">{{ c.covered }}</span> /
              <span class="warn">{{ c.partial }}</span> /
              <span class="bad">{{ c.missing }}</span>
            </span>
          </div>
          <div class="m">
            <span class="m-label">评分</span>
            <span class="m-val">{{ c.score ?? '-' }}</span>
          </div>
        </div>
        <div v-if="c.reason" class="reason">{{ c.reason }}</div>
        <div v-if="c.feedback" class="feedback" :title="c.feedback">{{ c.feedback }}</div>
      </div>
      <div v-if="!ordered.length" class="empty">等待任务启动...</div>
    </div>

    <template #footer>
      <el-button @click="close">{{ state.status === 'running' ? '后台运行' : '关闭' }}</el-button>
    </template>
  </el-drawer>
</template>

<style scoped>
.overall {
  margin-bottom: 16px;
}
.overall-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.counter {
  font-size: 13px;
  color: #4e5969;
}
.retry-hint {
  font-size: 12px;
  color: #ff7d00;
}
.error-line {
  margin-top: 6px;
  color: #f53f3f;
  font-size: 12px;
}
.stop-line {
  margin-top: 6px;
  color: #ff7d00;
  font-size: 12px;
}
.cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.card {
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  padding: 10px 12px;
  background: #fff;
  transition: box-shadow 0.2s;
}
.card.active {
  box-shadow: 0 0 0 2px var(--el-color-primary);
}
.card-head {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}
.title {
  font-weight: 600;
  font-size: 13px;
  color: #1f2329;
  flex: 1;
}
.metrics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
  font-size: 12px;
}
.m {
  background: #f7f8fa;
  border-radius: 4px;
  padding: 4px 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.m-label {
  color: #86909c;
  font-size: 11px;
}
.m-val {
  font-variant-numeric: tabular-nums;
  color: #1f2329;
}
.m-val .ok { color: #00b42a; }
.m-val .warn { color: #ff7d00; }
.m-val .bad { color: #f53f3f; }
.reason {
  margin-top: 6px;
  font-size: 12px;
  color: #ff7d00;
  line-height: 1.5;
}
.feedback {
  margin-top: 4px;
  font-size: 12px;
  color: #86909c;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}
.empty {
  text-align: center;
  color: #c9cdd4;
  padding: 40px 0;
  font-size: 13px;
}
</style>
