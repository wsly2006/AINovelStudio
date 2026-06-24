<script setup>
import { ref, watch, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete } from '@element-plus/icons-vue'
import { diffLines } from 'diff'
import { chapterVersionsApi } from '../api/chapterVersions'
import { chaptersApi } from '../api/chapters'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  chapterId: { type: Number, default: null },
  // 打开后默认选中的语种过滤;'' 表示混排所有语种
  initialLang: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'restored'])

const loading = ref(false)
const versions = ref([])
const selected = ref(null)
const detailContent = ref('')
const detailLoading = ref(false)
// 'content' | 'diff' :右侧视图模式
const viewMode = ref('content')
// 当前章节正文,用于"版本 vs 当前"对比
const currentContent = ref('')
// 语种过滤:''=全部, 'zh-CN', 'en-US', ...
const langFilter = ref('')
const LANG_OPTIONS = [
  { value: '', label: '全部' },
  { value: 'zh-CN', label: '中文' },
  { value: 'en-US', label: 'English' },
  { value: 'es-ES', label: 'Español' },
  { value: 'id-ID', label: 'Indonesia' },
  { value: 'ja-JP', label: '日本語' },
  { value: 'ko-KR', label: '한국어' },
  { value: 'vi-VN', label: 'Tiếng Việt' },
]

const REASON_LABEL = {
  ai_overwrite: 'AI 覆盖前',
  manual: '手动保存',
  restore: '还原前',
  translated: 'AI 翻译',
}

const REASON_TYPE = {
  ai_overwrite: 'warning',
  manual: 'success',
  restore: 'info',
  translated: 'primary',
}

async function loadList() {
  if (!props.chapterId) return
  loading.value = true
  try {
    const params = langFilter.value ? { lang: langFilter.value } : {}
    const [list, current] = await Promise.all([
      chapterVersionsApi.list(props.chapterId, params),
      chaptersApi.get(props.chapterId),
    ])
    versions.value = list
    currentContent.value = current.content || ''
    selected.value = list[0] || null
    if (selected.value) await loadDetail(selected.value.id)
    else detailContent.value = ''
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
    if (v) {
      viewMode.value = 'content'
      langFilter.value = props.initialLang || ''
      loadList()
    } else {
      versions.value = []
      selected.value = null
      detailContent.value = ''
      currentContent.value = ''
    }
  }
)

// 切换 lang 过滤要重新拉
watch(langFilter, () => {
  if (props.modelValue) loadList()
})

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

// 删除单条版本:列表小图标触发,二次确认避免误删
async function onDelete(v, evt) {
  evt?.stopPropagation()
  try {
    await ElMessageBox.confirm(
      `删除「${REASON_LABEL[v.reason] || v.reason}${v.label ? ' · ' + v.label : ''}」?此操作不可撤销。`,
      '删除版本',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await chapterVersionsApi.remove(props.chapterId, v.id)
    ElMessage.success('已删除')
    // 重新加载列表;如果删的就是当前选中的,清掉详情
    const wasSelected = selected.value?.id === v.id
    versions.value = versions.value.filter((x) => x.id !== v.id)
    if (wasSelected) {
      selected.value = versions.value[0] || null
      detailContent.value = ''
      if (selected.value) await loadDetail(selected.value.id)
    }
  } catch (e) {
    ElMessage.error(e.message || '删除失败')
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

const versionCountText = computed(() => {
  const total = versions.value.length
  if (langFilter.value) return `${total} / 5 个版本(${langFilter.value})`
  return `${total} 个版本`
})

// 译版不能 restore 回 chapter.content,UI 层显式禁用
const canRestore = computed(() => {
  if (!selected.value) return false
  const lang = selected.value.lang || 'zh-CN'
  return lang === 'zh-CN'
})

// diff 行:左侧版本(detailContent) → 右侧当前(currentContent)。
// added=当前比版本多的,removed=版本里有但当前没的。语义上读"从这个版本到现在改了什么"。
const diffChunks = computed(() => {
  if (viewMode.value !== 'diff') return []
  if (!selected.value) return []
  const parts = diffLines(detailContent.value || '', currentContent.value || '')
  return parts.flatMap((p) => {
    const lines = (p.value || '').split('\n')
    // diffLines 给的每段末尾常有空字符串,过滤掉,但保留段内的真空行
    if (lines.length > 0 && lines[lines.length - 1] === '') lines.pop()
    return lines.map((line) => ({
      type: p.added ? 'added' : p.removed ? 'removed' : 'context',
      text: line,
    }))
  })
})

const diffSummary = computed(() => {
  let added = 0
  let removed = 0
  for (const c of diffChunks.value) {
    if (c.type === 'added') added++
    else if (c.type === 'removed') removed++
  }
  return { added, removed }
})
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    title="章节历史版本"
    width="900px"
    :close-on-click-modal="false"
  >
    <div class="hint-bar">
      <span>{{ versionCountText }}</span>
      <el-select v-model="langFilter" size="small" class="lang-filter">
        <el-option
          v-for="opt in LANG_OPTIONS"
          :key="opt.value || '__all__'"
          :label="opt.label"
          :value="opt.value"
        />
      </el-select>
      <span class="hint">每个语种各保留 5 条最新版本</span>
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
            <el-tag
              v-if="v.lang && v.lang !== 'zh-CN'"
              size="small"
              type="warning"
              effect="plain"
            >
              {{ v.lang }}
            </el-tag>
            <span class="ver-time">{{ formatTime(v.created_at) }}</span>
            <el-button
              text
              size="small"
              :icon="Delete"
              class="ver-del"
              title="删除此版本"
              @click="onDelete(v, $event)"
            />
          </div>
          <div v-if="v.label" class="ver-label">{{ v.label }}</div>
          <div class="ver-meta">{{ v.word_count }} 字</div>
          <div class="ver-preview">{{ v.preview || '(空内容)' }}</div>
        </div>
      </div>

      <div class="right">
        <div v-if="!selected" class="empty">选择左侧版本查看内容</div>
        <template v-else>
          <div class="right-head">
            <el-radio-group v-model="viewMode" size="small">
              <el-radio-button label="content">内容</el-radio-button>
              <el-radio-button label="diff">对比当前</el-radio-button>
            </el-radio-group>
            <span v-if="viewMode === 'diff'" class="diff-stat">
              <span class="stat-add">+{{ diffSummary.added }}</span>
              <span class="stat-del">-{{ diffSummary.removed }}</span>
            </span>
          </div>

          <div v-if="viewMode === 'content'" v-loading="detailLoading" class="detail">
            <pre v-if="detailContent">{{ detailContent }}</pre>
            <div v-else class="empty">(空内容)</div>
          </div>

          <div v-else class="diff-view" v-loading="detailLoading">
            <div v-if="diffChunks.length === 0" class="empty">两份内容完全一致</div>
            <div
              v-for="(c, i) in diffChunks"
              :key="i"
              class="diff-line"
              :class="`diff-${c.type}`"
            >
              <span class="diff-prefix">{{ c.type === 'added' ? '+' : c.type === 'removed' ? '-' : ' ' }}</span><span class="diff-text">{{ c.text || ' ' }}</span>
            </div>
          </div>
        </template>
      </div>
    </div>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-tooltip
        :disabled="canRestore"
        content="翻译版本不支持还原(中文正文是真相,翻译只读)"
        placement="top"
      >
        <span>
          <el-button
            type="primary"
            :disabled="!selected || !canRestore"
            @click="onRestore"
          >
            还原此版本
          </el-button>
        </span>
      </el-tooltip>
    </template>
  </el-dialog>
</template>

<style scoped>
.hint-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: #86909c;
  margin-bottom: 12px;
}
.hint-bar .lang-filter {
  width: 130px;
}
.hint-bar .hint {
  color: #c9cdd4;
  margin-left: auto;
}
.layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 12px;
  height: 520px;
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
  position: relative;
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
  gap: 8px;
  margin-bottom: 6px;
}
.ver-time {
  font-size: 12px;
  color: #86909c;
  font-variant-numeric: tabular-nums;
  flex: 1;
}
.ver-del {
  opacity: 0;
  color: #86909c !important;
  padding: 2px !important;
  height: auto !important;
}
.ver:hover .ver-del,
.ver.active .ver-del {
  opacity: 1;
}
.ver-del:hover {
  color: #f53f3f !important;
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
  flex-direction: column;
}
.right-head {
  flex-shrink: 0;
  padding: 8px 12px;
  border-bottom: 1px solid #f2f3f5;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.diff-stat {
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.stat-add { color: #00b42a; margin-right: 8px; }
.stat-del { color: #f53f3f; }
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
.diff-view {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
  font-family: ui-monospace, 'Cascadia Code', 'PingFang SC', 'Microsoft YaHei', monospace;
  font-size: 13px;
  line-height: 1.6;
}
.diff-line {
  display: flex;
  padding: 1px 12px;
  white-space: pre-wrap;
  word-wrap: break-word;
}
.diff-prefix {
  flex-shrink: 0;
  width: 16px;
  color: #c9cdd4;
  user-select: none;
}
.diff-text {
  flex: 1;
}
.diff-added {
  background: #f0fdf4;
}
.diff-added .diff-prefix { color: #00b42a; }
.diff-removed {
  background: #fef2f2;
}
.diff-removed .diff-prefix { color: #f53f3f; }
.empty {
  color: #c9cdd4;
  text-align: center;
  padding: 40px 12px;
  font-size: 13px;
  line-height: 1.6;
  margin: auto;
}
</style>
