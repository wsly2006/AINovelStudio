<script setup>
import { ref, watch, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { chapterVersionsApi } from '../api/chapterVersions'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  chapterId: { type: Number, default: null },
})
const emit = defineEmits(['update:modelValue', 'restored'])

const loading = ref(false)
const versions = ref([])
const selected = ref(null)
const detailContent = ref('')
const detailLoading = ref(false)

const REASON_LABEL = {
  ai_overwrite: 'AI 覆盖前',
  manual: '手动保存',
  restore: '还原前',
}

const REASON_TYPE = {
  ai_overwrite: 'warning',
  manual: 'success',
  restore: 'info',
}

async function loadList() {
  if (!props.chapterId) return
  loading.value = true
  try {
    versions.value = await chapterVersionsApi.list(props.chapterId)
    selected.value = versions.value[0] || null
    if (selected.value) await loadDetail(selected.value.id)
  } catch (e) {
    ElMessage.error(e.message || '加载历史失败')
  } finally {
    loading.value = false
  }
}

async function loadDetail(versionId) {
  detailLoading.value = true
  detailContent.value = ''
  try {
    const v = await chapterVersionsApi.get(props.chapterId, versionId)
    detailContent.value = v.content || ''
  } catch (e) {
    ElMessage.error(e.message || '加载版本内容失败')
  } finally {
    detailLoading.value = false
  }
}

watch(
  () => props.modelValue,
  (v) => {
    if (v) loadList()
    else {
      versions.value = []
      selected.value = null
      detailContent.value = ''
    }
  }
)

function onSelect(v) {
  if (selected.value?.id === v.id) return
  selected.value = v
  loadDetail(v.id)
}

async function onRestore() {
  if (!selected.value) return
  try {
    await ElMessageBox.confirm(
      `确定还原到这个版本吗?当前内容会先被自动快照保留,可以再次还原回来。`,
      '还原确认',
      { type: 'warning', confirmButtonText: '还原', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    const updated = await chapterVersionsApi.restore(props.chapterId, selected.value.id)
    ElMessage.success('已还原')
    emit('restored', updated)
    emit('update:modelValue', false)
  } catch (e) {
    ElMessage.error(e.message || '还原失败')
  }
}

function close() {
  emit('update:modelValue', false)
}

function formatTime(s) {
  if (!s) return ''
  const d = new Date(s)
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const versionCountText = computed(() => `${versions.value.length} / 5 个版本`)
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    title="章节历史版本"
    width="780px"
    :close-on-click-modal="false"
  >
    <div class="hint-bar">
      <span>{{ versionCountText }}</span>
      <span class="hint">超过 5 条会自动淘汰最旧的</span>
    </div>

    <div class="layout" v-loading="loading">
      <div class="left">
        <div v-if="versions.length === 0 && !loading" class="empty">
          还没有任何版本。<br />在 AI 生成或手动保存版本后,会出现在这里。
        </div>
        <div
          v-for="v in versions"
          :key="v.id"
          class="ver"
          :class="{ active: selected?.id === v.id }"
          @click="onSelect(v)"
        >
          <div class="ver-head">
            <el-tag :type="REASON_TYPE[v.reason] || 'info'" size="small">
              {{ REASON_LABEL[v.reason] || v.reason }}
            </el-tag>
            <span class="ver-time">{{ formatTime(v.created_at) }}</span>
          </div>
          <div v-if="v.label" class="ver-label">{{ v.label }}</div>
          <div class="ver-meta">{{ v.word_count }} 字</div>
          <div class="ver-preview">{{ v.preview || '(空内容)' }}</div>
        </div>
      </div>

      <div class="right">
        <div v-if="!selected" class="empty">选择左侧版本查看内容</div>
        <div v-else v-loading="detailLoading" class="detail">
          <pre v-if="detailContent">{{ detailContent }}</pre>
          <div v-else class="empty">(空内容)</div>
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :disabled="!selected" @click="onRestore">还原此版本</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.hint-bar {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #86909c;
  margin-bottom: 12px;
}
.hint-bar .hint {
  color: #c9cdd4;
}
.layout {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 12px;
  height: 480px;
}
.left {
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  overflow-y: auto;
  padding: 6px;
}
.ver {
  border-radius: 6px;
  padding: 10px 12px;
  cursor: pointer;
  margin-bottom: 4px;
  border: 1px solid transparent;
  transition: background 0.15s, border-color 0.15s;
}
.ver:hover {
  background: #f7f8fa;
}
.ver.active {
  background: #ecf5ff;
  border-color: #4080ff;
}
.ver-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.ver-time {
  font-size: 12px;
  color: #86909c;
  font-variant-numeric: tabular-nums;
}
.ver-label {
  font-size: 12px;
  color: #1f2329;
  margin-bottom: 4px;
}
.ver-meta {
  font-size: 11px;
  color: #86909c;
  margin-bottom: 4px;
}
.ver-preview {
  font-size: 12px;
  color: #4e5969;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.right {
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
}
.detail {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}
.detail pre {
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  line-height: 1.7;
  font-size: 14px;
}
.empty {
  color: #c9cdd4;
  text-align: center;
  padding: 40px 12px;
  font-size: 13px;
  line-height: 1.6;
  margin: auto;
}
</style>
