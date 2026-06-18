<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, MagicStick, Refresh } from '@element-plus/icons-vue'
import { chapterScoresApi } from '../api/chapterScores'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  chapterId: { type: Number, default: null },
  chapterTitle: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const loading = ref(false)
const scoring = ref(false)
const items = ref([])
const selectedId = ref(null)

const selected = computed(() =>
  items.value.find((s) => s.id === selectedId.value) || items.value[0] || null
)

async function loadList() {
  if (!props.chapterId) return
  loading.value = true
  try {
    items.value = await chapterScoresApi.list(props.chapterId)
    selectedId.value = items.value[0]?.id || null
  } catch (e) {
    ElMessage.error(e.message || '加载评分历史失败')
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
    }
  }
)

async function onScore() {
  if (scoring.value || !props.chapterId) return
  scoring.value = true
  try {
    const created = await chapterScoresApi.create(props.chapterId)
    items.value = [created, ...items.value]
    selectedId.value = created.id
    ElMessage.success('评分完成')
  } catch (e) {
    const detail = e?.response?.data?.detail || e.message || '评分失败'
    ElMessage.error(detail)
  } finally {
    scoring.value = false
  }
}

async function onDelete(s) {
  try {
    await ElMessageBox.confirm(
      `删除这条评分?此操作不可撤销。`,
      '删除评分',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await chapterScoresApi.remove(props.chapterId, s.id)
    const wasSelected = selectedId.value === s.id
    items.value = items.value.filter((x) => x.id !== s.id)
    if (wasSelected) selectedId.value = items.value[0]?.id || null
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

function scoreColor(n) {
  if (n >= 9) return '#00b42a'
  if (n >= 7) return '#4080ff'
  if (n >= 5) return '#ff7d00'
  return '#f53f3f'
}

// 综合分趋势 sparkline:历史按时间正序,SVG 路径
const sparkline = computed(() => {
  const list = [...items.value].reverse() // 老 → 新
  if (list.length < 2) return null
  const W = 200
  const H = 40
  const pad = 4
  const min = 1
  const max = 10
  const xStep = (W - pad * 2) / (list.length - 1)
  const points = list.map((s, i) => {
    const x = pad + i * xStep
    const y = H - pad - ((s.overall - min) / (max - min)) * (H - pad * 2)
    return [x, y]
  })
  const d = points.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  return { d, points, W, H }
})
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    title="AI 章节评分"
    width="780px"
    :close-on-click-modal="false"
  >
    <div class="meta-row">
      <span class="meta-title">{{ chapterTitle }}</span>
      <el-button
        type="primary"
        :icon="items.length === 0 ? MagicStick : Refresh"
        :loading="scoring"
        @click="onScore"
      >
        {{ items.length === 0 ? '开始评分' : '重新评分' }}
      </el-button>
    </div>

    <div v-loading="loading">
      <div v-if="!selected && !loading && !scoring" class="empty">
        <div class="empty-emoji">✨</div>
        <p>还没有评分。点上方「开始评分」让 AI 给本章打分。</p>
        <p class="empty-hint">分文笔 / 情节 / 人物 / 综合 4 项,每项 1-10。</p>
      </div>

      <template v-if="selected">
        <!-- 当前(最新)分数 -->
        <div class="score-grid">
          <div class="score-tile">
            <div class="dim">文笔</div>
            <div class="num" :style="{ color: scoreColor(selected.writing) }">{{ selected.writing }}</div>
          </div>
          <div class="score-tile">
            <div class="dim">情节</div>
            <div class="num" :style="{ color: scoreColor(selected.plot) }">{{ selected.plot }}</div>
          </div>
          <div class="score-tile">
            <div class="dim">人物</div>
            <div class="num" :style="{ color: scoreColor(selected.characters) }">{{ selected.characters }}</div>
          </div>
          <div class="score-tile primary">
            <div class="dim">综合</div>
            <div class="num" :style="{ color: scoreColor(selected.overall) }">{{ selected.overall }}</div>
          </div>
        </div>

        <div class="feedback">
          <div class="section-label">
            AI 反馈
            <span class="model-tag" v-if="selected.model">· {{ selected.model }}</span>
            <span class="model-tag">· {{ fmtDate(selected.created_at) }}</span>
            <span class="model-tag">· {{ selected.word_count }} 字</span>
          </div>
          <p v-if="selected.feedback" class="feedback-text">{{ selected.feedback }}</p>
          <p v-else class="feedback-empty">(本次评分未给出文字反馈)</p>
        </div>

        <!-- 历史 -->
        <div class="history" v-if="items.length > 1">
          <div class="section-label">历史评分 ({{ items.length }} 次)</div>

          <div v-if="sparkline" class="trend">
            <span class="trend-label">综合分趋势</span>
            <svg :viewBox="`0 0 ${sparkline.W} ${sparkline.H}`" class="trend-svg">
              <path :d="sparkline.d" stroke="#4080ff" stroke-width="1.5" fill="none" />
              <circle
                v-for="(p, i) in sparkline.points"
                :key="i"
                :cx="p[0]"
                :cy="p[1]"
                r="2.5"
                fill="#4080ff"
              />
            </svg>
          </div>

          <div class="hist-list">
            <div
              v-for="s in items"
              :key="s.id"
              class="hist-row"
              :class="{ active: selectedId === s.id }"
              @click="selectedId = s.id"
            >
              <span class="hist-time">{{ fmtDate(s.created_at) }}</span>
              <span class="hist-cells">
                <span>文 {{ s.writing }}</span>
                <span>情 {{ s.plot }}</span>
                <span>人 {{ s.characters }}</span>
                <span class="hist-overall" :style="{ color: scoreColor(s.overall) }">综 {{ s.overall }}</span>
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
  margin-bottom: 16px;
}
.meta-title {
  font-size: 14px;
  color: #4e5969;
}
.empty {
  text-align: center;
  padding: 48px 12px;
  color: #86909c;
}
.empty-emoji {
  font-size: 40px;
  opacity: 0.5;
  margin-bottom: 8px;
}
.empty-hint {
  font-size: 12px;
  color: #c9cdd4;
  margin-top: 4px;
}
.score-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}
.score-tile {
  background: #f7f8fa;
  border-radius: 10px;
  padding: 18px 12px;
  text-align: center;
  border: 1px solid transparent;
}
.score-tile.primary {
  background: #ecf5ff;
  border-color: #b3d3ff;
}
.dim {
  font-size: 12px;
  color: #86909c;
  margin-bottom: 6px;
}
.num {
  font-size: 36px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}
.feedback {
  background: #fafbfc;
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 20px;
}
.section-label {
  font-size: 12px;
  color: #86909c;
  margin-bottom: 8px;
}
.model-tag {
  margin-left: 4px;
  color: #c9cdd4;
}
.feedback-text {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  color: #1f2329;
  white-space: pre-wrap;
}
.feedback-empty {
  margin: 0;
  color: #c9cdd4;
  font-size: 13px;
}
.trend {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  font-size: 12px;
  color: #86909c;
}
.trend-svg {
  height: 36px;
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
.hist-cells {
  flex: 1;
  display: flex;
  gap: 14px;
  font-variant-numeric: tabular-nums;
  color: #4e5969;
}
.hist-overall {
  font-weight: 600;
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
</style>
