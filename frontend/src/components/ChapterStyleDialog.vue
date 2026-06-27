<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, MagicStick, Refresh, Aim } from '@element-plus/icons-vue'
import { chapterStyleChecksApi } from '../api/chapterStyleChecks'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  chapterId: { type: Number, default: null },
  chapterTitle: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'changed', 'jumpRewrite'])

const loading = ref(false)
const checking = ref(false)
const items = ref([])
const selectedId = ref(null)
const activeIssueIdx = ref(0)

const selected = computed(
  () => items.value.find((s) => s.id === selectedId.value) || items.value[0] || null
)

const activeIssue = computed(() => {
  const s = selected.value
  if (!s || !s.issues?.length) return null
  return s.issues[Math.min(activeIssueIdx.value, s.issues.length - 1)] || null
})

const signals = computed(() => selected.value?.signals || {})
const hasSignals = computed(() => {
  const s = signals.value
  // 旧记录没 signals 字段,或字段空对象时不显示
  return s && typeof s === 'object' && (s.char_count ?? 0) > 0
})

function fmtRatio(v) {
  if (v == null) return '—'
  return `${(v * 100).toFixed(1)}%`
}

async function loadList() {
  if (!props.chapterId) return
  loading.value = true
  try {
    items.value = await chapterStyleChecksApi.list(props.chapterId)
    selectedId.value = items.value[0]?.id || null
    activeIssueIdx.value = 0
  } catch (e) {
    ElMessage.error(e.message || '加载历史失败')
  } finally {
    loading.value = false
  }
}

watch(
  () => props.modelValue,
  (v) => {
    if (v) loadList()
    else {
      items.value = []
      selectedId.value = null
      activeIssueIdx.value = 0
    }
  }
)

watch(selectedId, () => {
  activeIssueIdx.value = 0
})

async function onCheck() {
  if (checking.value || !props.chapterId) return
  checking.value = true
  try {
    const created = await chapterStyleChecksApi.create(props.chapterId)
    items.value = [created, ...items.value]
    selectedId.value = created.id
    activeIssueIdx.value = 0
    emit('changed', { chapterId: props.chapterId, latestIssueCount: created.issues.length })
    ElMessage.success(
      created.issues.length
        ? `检查完成,发现 ${created.issues.length} 处需要重写`
        : '检查完成,未发现明显的 AI 味段落'
    )
  } catch (e) {
    const detail = e?.response?.data?.detail || e.message || '检查失败'
    ElMessage.error(detail)
  } finally {
    checking.value = false
  }
}

async function onDelete(s) {
  try {
    await ElMessageBox.confirm('删除这条检查记录?此操作不可撤销。', '删除', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await chapterStyleChecksApi.remove(props.chapterId, s.id)
    const wasSelected = selectedId.value === s.id
    items.value = items.value.filter((x) => x.id !== s.id)
    if (wasSelected) selectedId.value = items.value[0]?.id || null
    emit('changed', {
      chapterId: props.chapterId,
      latestIssueCount: items.value[0]?.issues.length ?? null,
    })
    ElMessage.success('已删除')
  } catch (e) {
    ElMessage.error(e.message || '删除失败')
  }
}

function close() {
  emit('update:modelValue', false)
}

function fmtDate(s) {
  if (!s) return ''
  const d = new Date(s)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const KIND_COLORS = {
  套语: '#f53f3f',
  排比堆砌: '#ff7d00',
  辞藻冗余: '#ff9a2e',
  模板结构: '#7a4cff',
  对话同质: '#3491fa',
  视角抽离: '#00b42a',
  其他: '#86909c',
}

function kindColor(k) {
  return KIND_COLORS[k] || '#86909c'
}

function onJumpRewrite(issue) {
  if (!issue) return
  emit('jumpRewrite', {
    quote: issue.quote,
    suggestion: issue.suggestion,
    why: issue.why,
    kind: issue.kind,
  })
  close()
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    title="AI 文风检查"
    width="900px"
    :close-on-click-modal="false"
  >
    <div class="meta-row">
      <span class="meta-title">{{ chapterTitle }}</span>
      <el-button
        type="primary"
        :icon="items.length === 0 ? MagicStick : Refresh"
        :loading="checking"
        @click="onCheck"
      >
        {{ items.length === 0 ? '开始检查' : '重新检查' }}
      </el-button>
    </div>

    <div v-loading="loading">
      <div v-if="!selected && !loading && !checking" class="empty">
        <div class="empty-emoji">🪞</div>
        <p>还没有检查记录。点上方「开始检查」让 AI 挑出读起来「像 AI 写」的段落。</p>
        <p class="empty-hint">每条命中包含原文片段、问题原因与重写方向,点「去改写」直接定位到编辑器。</p>
      </div>

      <template v-if="selected">
        <div class="meta-bar">
          <span class="model-tag" v-if="selected.model">{{ selected.model }}</span>
          <span class="model-tag">{{ fmtDate(selected.created_at) }}</span>
          <span class="model-tag">{{ selected.word_count }} 字</span>
          <span class="model-tag count-pill" :class="{ clean: selected.issues.length === 0 }">
            {{ selected.issues.length === 0 ? '无明显 AI 味' : `${selected.issues.length} 处需重写` }}
          </span>
        </div>

        <p v-if="selected.summary" class="summary">{{ selected.summary }}</p>

        <!-- 客观风格信号(本地统计,不依赖 LLM)。默认折叠,作为知情参考 -->
        <details v-if="hasSignals" class="signals-panel">
          <summary class="signals-summary">
            <span class="signals-title">客观风格信号</span>
            <span class="signals-hint">本地统计,作者知情参考</span>
          </summary>
          <div class="signals-grid">
            <div class="sig-cell">
              <div class="sig-label">句长方差</div>
              <div class="sig-value">{{ signals.sentence?.stdev_len ?? '—' }}</div>
              <div class="sig-meta">
                均 {{ signals.sentence?.mean_len ?? '—' }} · p10/50/90
                {{ signals.sentence?.p10 ?? '—' }}/{{ signals.sentence?.p50 ?? '—' }}/{{ signals.sentence?.p90 ?? '—' }}
              </div>
            </div>
            <div class="sig-cell">
              <div class="sig-label">段长方差</div>
              <div class="sig-value">{{ signals.paragraph?.stdev_len ?? '—' }}</div>
              <div class="sig-meta">
                {{ signals.paragraph?.count ?? 0 }} 段 · 均
                {{ signals.paragraph?.mean_len ?? '—' }} 字
              </div>
            </div>
            <div class="sig-cell">
              <div class="sig-label">词汇丰富度</div>
              <div class="sig-value">{{ fmtRatio(signals.vocab_richness) }}</div>
              <div class="sig-meta">去重字符 / 非空白字符</div>
            </div>
            <div class="sig-cell">
              <div class="sig-label">对白占比</div>
              <div class="sig-value">{{ fmtRatio(signals.dialogue_ratio) }}</div>
              <div class="sig-meta">引号开头段 / 总段数</div>
            </div>
            <div class="sig-cell">
              <div class="sig-label">标点密度</div>
              <div class="sig-value">{{ fmtRatio(signals.punctuation_ratio) }}</div>
              <div class="sig-meta">标点字符 / 总字符</div>
            </div>
            <div class="sig-cell">
              <div class="sig-label">总字符</div>
              <div class="sig-value">{{ signals.char_count ?? 0 }}</div>
              <div class="sig-meta">{{ signals.sentence?.count ?? 0 }} 句</div>
            </div>
          </div>
          <p class="signals-note">
            这些是统计参考,不是"AI 痕迹分"。句长方差太低、词汇丰富度太低,
            往往意味着行文偏机械;具体改不改、怎么改,作者自己定。
          </p>
        </details>

        <div v-if="selected.issues.length > 0" class="issue-layout">
          <!-- 左:命中列表 -->
          <div class="issue-list">
            <div
              v-for="(it, i) in selected.issues"
              :key="i"
              class="issue-row"
              :class="{ active: activeIssueIdx === i }"
              @click="activeIssueIdx = i"
            >
              <span class="kind-dot" :style="{ background: kindColor(it.kind) }">{{ it.kind }}</span>
              <span class="quote-preview">{{ it.quote }}</span>
            </div>
          </div>

          <!-- 右:命中详情 + 改写入口 -->
          <div class="issue-detail" v-if="activeIssue">
            <div class="kind-tag" :style="{ background: kindColor(activeIssue.kind) }">
              {{ activeIssue.kind }}
            </div>
            <div class="section-label">原文片段</div>
            <p class="quote-text">{{ activeIssue.quote }}</p>
            <div class="section-label">为什么像 AI</div>
            <p class="reason-text">{{ activeIssue.why || '(未给出)' }}</p>
            <div class="section-label">重写方向</div>
            <p class="reason-text">{{ activeIssue.suggestion || '(未给出)' }}</p>
            <div class="actions">
              <el-button type="primary" :icon="Aim" @click="onJumpRewrite(activeIssue)">
                去改写
              </el-button>
            </div>
          </div>
        </div>

        <!-- 历史 -->
        <div class="history" v-if="items.length > 1">
          <div class="section-label hist-title">历史检查 ({{ items.length }} 次)</div>
          <div class="hist-list">
            <div
              v-for="s in items"
              :key="s.id"
              class="hist-row"
              :class="{ active: selectedId === s.id }"
              @click="selectedId = s.id"
            >
              <span class="hist-time">{{ fmtDate(s.created_at) }}</span>
              <span class="hist-count" :class="{ clean: s.issues.length === 0 }">
                {{ s.issues.length === 0 ? '过关' : `${s.issues.length} 处` }}
              </span>
              <el-button
                text
                size="small"
                :icon="Delete"
                class="hist-del"
                @click.stop="onDelete(s)"
              />
            </div>
          </div>
        </div>
      </template>
    </div>

    <template #footer>
      <el-button @click="close">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.meta-title {
  font-size: 14px;
  color: #4e5969;
}
.meta-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #86909c;
  margin-bottom: 8px;
}
.model-tag {
  background: #f7f8fa;
  padding: 2px 8px;
  border-radius: 4px;
}
.count-pill {
  margin-left: auto;
  background: #fff1f0;
  color: #f53f3f;
  font-weight: 600;
}
.count-pill.clean {
  background: #e8fff0;
  color: #00b42a;
}
.summary {
  margin: 0 0 16px;
  font-size: 13px;
  line-height: 1.7;
  color: #4e5969;
  background: #fafbfc;
  padding: 12px 14px;
  border-radius: 8px;
  border-left: 3px solid #4080ff;
}
.empty {
  text-align: center;
  padding: 48px 12px;
  color: #86909c;
}
.empty-emoji {
  font-size: 40px;
  opacity: 0.6;
  margin-bottom: 8px;
}
.empty-hint {
  font-size: 12px;
  color: #c9cdd4;
  margin-top: 4px;
}
.section-label {
  font-size: 12px;
  color: #86909c;
  margin-top: 12px;
  margin-bottom: 6px;
}
.section-label:first-child {
  margin-top: 0;
}

.issue-layout {
  display: grid;
  grid-template-columns: minmax(260px, 320px) 1fr;
  gap: 12px;
  border: 1px solid #e5e6eb;
  border-radius: 10px;
  overflow: hidden;
  min-height: 320px;
  max-height: 50vh;
}
.issue-list {
  border-right: 1px solid #e5e6eb;
  overflow-y: auto;
  background: #fafbfc;
}
.issue-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border-bottom: 1px solid #f2f3f5;
  cursor: pointer;
  transition: background 0.12s;
}
.issue-row:last-child {
  border-bottom: none;
}
.issue-row:hover {
  background: #f2f3f5;
}
.issue-row.active {
  background: #e8f0ff;
}
.kind-dot {
  display: inline-flex;
  align-items: center;
  align-self: flex-start;
  height: 18px;
  padding: 0 8px;
  font-size: 11px;
  color: #fff;
  border-radius: 4px;
  font-weight: 500;
}
.quote-preview {
  font-size: 13px;
  color: #4e5969;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.issue-detail {
  padding: 16px;
  overflow-y: auto;
}
.kind-tag {
  display: inline-block;
  height: 22px;
  padding: 0 10px;
  line-height: 22px;
  font-size: 12px;
  color: #fff;
  border-radius: 4px;
  font-weight: 500;
  margin-bottom: 12px;
}
.quote-text {
  margin: 0;
  font-size: 14px;
  line-height: 1.8;
  color: #1f2329;
  background: #fff8e1;
  padding: 10px 12px;
  border-radius: 6px;
  border-left: 3px solid #ff9a2e;
  white-space: pre-wrap;
}
.reason-text {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: #4e5969;
}
.actions {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.history {
  margin-top: 16px;
}
.hist-title {
  margin-top: 0;
}
.hist-list {
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  overflow: hidden;
}
.hist-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  border-bottom: 1px solid #f2f3f5;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.12s;
}
.hist-row:last-child {
  border-bottom: none;
}
.hist-row:hover {
  background: #f7f8fa;
}
.hist-row.active {
  background: #ecf5ff;
}
.hist-time {
  font-variant-numeric: tabular-nums;
  color: #86909c;
  font-size: 12px;
  flex-shrink: 0;
  width: 130px;
}
.hist-count {
  flex: 1;
  color: #f53f3f;
  font-weight: 600;
}
.hist-count.clean {
  color: #00b42a;
}
.hist-del {
  opacity: 0;
  color: #86909c !important;
}
.hist-row:hover .hist-del,
.hist-row.active .hist-del {
  opacity: 1;
}
.hist-del:hover {
  color: #f53f3f !important;
}

/* 客观信号面板:默认折叠的 details/summary */
.signals-panel {
  margin: 0 0 16px;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  background: #fafbfc;
  padding: 0;
}
.signals-summary {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 8px 14px;
  cursor: pointer;
  list-style: none;
  user-select: none;
}
.signals-summary::-webkit-details-marker {
  display: none;
}
.signals-summary::before {
  content: '▸';
  font-size: 11px;
  color: #86909c;
  transition: transform 0.15s;
  margin-right: 4px;
}
.signals-panel[open] .signals-summary::before {
  transform: rotate(90deg);
}
.signals-title {
  font-size: 13px;
  font-weight: 600;
  color: #1f2329;
}
.signals-hint {
  font-size: 11px;
  color: #86909c;
}
.signals-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 10px;
  padding: 4px 14px 12px;
}
.sig-cell {
  background: #fff;
  padding: 8px 10px;
  border-radius: 6px;
  border: 1px solid #f2f3f5;
}
.sig-label {
  font-size: 11px;
  color: #86909c;
  margin-bottom: 2px;
}
.sig-value {
  font-size: 18px;
  font-weight: 600;
  color: #1f2329;
  font-variant-numeric: tabular-nums;
}
.sig-meta {
  font-size: 11px;
  color: #c9cdd4;
  margin-top: 2px;
  font-variant-numeric: tabular-nums;
}
.signals-note {
  margin: 0;
  padding: 0 14px 12px;
  font-size: 11px;
  line-height: 1.6;
  color: #86909c;
}
</style>
