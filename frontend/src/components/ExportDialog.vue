<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Download, Warning } from '@element-plus/icons-vue'
import { platformsApi } from '../api/platforms'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  project: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'go-publish'])

const { t } = useI18n()

const platforms = ref([])
const loading = ref(false)
const selectedCode = ref(null)
const selectedFormats = ref([])
const selectedEncoding = ref('utf-8')
const includeSidecars = ref(true)

const FORMAT_LABELS = {
  json: { label: '工程 JSON', hint: '完整数据备份,可重新导入' },
  md: { label: 'Markdown', hint: '正文 + 章节,适合阅读分享' },
  epub: { label: 'EPUB', hint: 'KDP / Apple Books / Calibre 通用电子书' },
  docx: { label: 'Word docx', hint: 'KDP 接受的稿件格式' },
  txt: { label: '整本 TXT', hint: '中文连载平台主流上传格式' },
  txt_chapters: { label: '章节包 (zip)', hint: '每章一个 txt,按章上传用' },
}

const FIELD_LABELS = {
  pen_name: '笔名',
  series_name: '系列',
  series_index: '系列序号',
  blurb: '长简介',
  keywords: '关键词',
  categories: '分类',
}

const selected = computed(() =>
  platforms.value.find((p) => p.code === selectedCode.value) || null
)

const groupedPlatforms = computed(() => {
  const cn = []
  const global = []
  const other = []
  for (const p of platforms.value) {
    if (p.region === 'cn') cn.push(p)
    else if (p.region === 'global') global.push(p)
    else other.push(p)
  }
  return { cn, global, other }
})

const missingFields = computed(() => {
  if (!selected.value || !props.project) return []
  const out = []
  for (const f of selected.value.metadata_schema || []) {
    if (!f.required) continue
    const v = props.project[f.key]
    const empty =
      v === null ||
      v === undefined ||
      (typeof v === 'string' && !v.trim()) ||
      (Array.isArray(v) && v.length === 0)
    if (empty) {
      out.push(f)
      continue
    }
    if (f.max_count && Array.isArray(v) && v.length > f.max_count) {
      out.push({ ...f, label: `${f.label}(超过上限 ${f.max_count})` })
    }
  }
  return out
})

const presentFields = computed(() => {
  if (!selected.value || !props.project) return []
  const out = []
  for (const f of selected.value.metadata_schema || []) {
    const v = props.project[f.key]
    if (v === null || v === undefined) continue
    if (typeof v === 'string' && !v.trim()) continue
    if (Array.isArray(v) && v.length === 0) continue
    let display
    if (Array.isArray(v)) display = v.join(' / ')
    else if (typeof v === 'string') display = v.length > 40 ? v.slice(0, 40) + '…' : v
    else display = String(v)
    out.push({ ...f, display })
  }
  return out
})

const canExport = computed(
  () => selectedFormats.value.length > 0 && missingFields.value.length === 0
)

watch(
  () => props.modelValue,
  async (visible) => {
    if (!visible) return
    if (!platforms.value.length) await load()
    // 默认选中工程已配置的第一个目标平台,否则选 generic
    const targets = props.project?.target_platform_codes || []
    const fallback = platforms.value.find((p) => p.code === 'generic')
    const matched = platforms.value.find((p) => targets.includes(p.code))
    pickPlatform((matched || fallback || platforms.value[0])?.code || null)
  }
)

async function load() {
  loading.value = true
  try {
    platforms.value = await platformsApi.list()
  } catch (e) {
    ElMessage.error(e.message || '加载平台列表失败')
  } finally {
    loading.value = false
  }
}

function pickPlatform(code) {
  selectedCode.value = code
  if (selected.value) {
    // 默认勾上推荐格式(数组首项)
    const first = selected.value.formats?.[0]
    selectedFormats.value = first ? [first] : []
    selectedEncoding.value = selected.value.encoding || 'utf-8'
  } else {
    selectedFormats.value = []
  }
}

function toggleFormat(fmt) {
  const idx = selectedFormats.value.indexOf(fmt)
  if (idx >= 0) selectedFormats.value.splice(idx, 1)
  else selectedFormats.value.push(fmt)
}

function buildUrl(fmt) {
  if (!props.project) return null
  const pid = props.project.id
  if (fmt === 'txt') {
    const enc = encodeURIComponent(selectedEncoding.value)
    return `/api/projects/${pid}/export.txt?mode=whole&encoding=${enc}`
  }
  if (fmt === 'txt_chapters') {
    const enc = encodeURIComponent(selectedEncoding.value)
    return `/api/projects/${pid}/export.txt?mode=chapters&encoding=${enc}`
  }
  return `/api/projects/${pid}/export.${fmt}`
}

function onExport() {
  if (!canExport.value) return
  const urls = selectedFormats.value.map(buildUrl).filter(Boolean)
  // 副产物:metadata.json 任何平台都可加;kdp_listing.txt 仅 KDP
  if (includeSidecars.value && props.project) {
    const pid = props.project.id
    urls.push(`/api/projects/${pid}/export.metadata.json`)
    if (selectedCode.value === 'kdp') {
      urls.push(`/api/projects/${pid}/export.kdp-listing.txt`)
    }
  }
  // 浏览器对短时间内多次 window.open 可能拦截,这里用 a.click() 串行触发,
  // 每次间隔 250ms 给浏览器时间处理 Content-Disposition
  urls.forEach((url, i) => {
    setTimeout(() => {
      const a = document.createElement('a')
      a.href = url
      a.download = ''
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
    }, i * 250)
  })
  ElMessage.success(`已触发 ${urls.length} 个文件下载`)
}

function goFillMeta() {
  emit('go-publish')
  emit('update:modelValue', false)
}

function close() {
  emit('update:modelValue', false)
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    title="导出到平台"
    width="780px"
    :close-on-click-modal="false"
    destroy-on-close
  >
    <div v-loading="loading" class="export-dialog">
      <!-- 步骤 1:选平台 -->
      <section class="step">
        <div class="step-title">1. 选择目标平台</div>
        <div v-if="groupedPlatforms.global.length" class="group">
          <div class="group-title">海外</div>
          <div class="grid">
            <button
              v-for="p in groupedPlatforms.global"
              :key="p.code"
              class="card"
              :class="{ active: selectedCode === p.code }"
              @click="pickPlatform(p.code)"
            >
              <div class="card-name">{{ p.name }}</div>
              <div class="card-formats">{{ (p.formats || []).join(' / ') || '-' }}</div>
            </button>
          </div>
        </div>
        <div v-if="groupedPlatforms.cn.length" class="group">
          <div class="group-title">国内</div>
          <div class="grid">
            <button
              v-for="p in groupedPlatforms.cn"
              :key="p.code"
              class="card"
              :class="{ active: selectedCode === p.code }"
              @click="pickPlatform(p.code)"
            >
              <div class="card-name">{{ p.name }}</div>
              <div class="card-formats">{{ (p.formats || []).join(' / ') || '-' }}</div>
            </button>
          </div>
        </div>
        <div v-if="groupedPlatforms.other.length" class="group">
          <div class="group-title">通用</div>
          <div class="grid">
            <button
              v-for="p in groupedPlatforms.other"
              :key="p.code"
              class="card"
              :class="{ active: selectedCode === p.code }"
              @click="pickPlatform(p.code)"
            >
              <div class="card-name">{{ p.name }}</div>
              <div class="card-formats">{{ (p.formats || []).join(' / ') || '-' }}</div>
            </button>
          </div>
        </div>
      </section>

      <!-- 步骤 2:格式 + 元数据校验 -->
      <section v-if="selected" class="step">
        <div class="step-title">2. 选择导出格式</div>

        <div class="formats">
          <label
            v-for="fmt in selected.formats"
            :key="fmt"
            class="format-row"
            :class="{ checked: selectedFormats.includes(fmt) }"
          >
            <el-checkbox
              :model-value="selectedFormats.includes(fmt)"
              @change="toggleFormat(fmt)"
            />
            <div class="format-text">
              <div class="format-name">{{ FORMAT_LABELS[fmt]?.label || fmt }}</div>
              <div class="format-hint">{{ FORMAT_LABELS[fmt]?.hint || '' }}</div>
            </div>
          </label>
        </div>

        <!-- TXT 编码 -->
        <div
          v-if="selectedFormats.some((f) => f === 'txt' || f === 'txt_chapters')"
          class="encoding-row"
        >
          <span class="encoding-label">TXT 编码</span>
          <el-radio-group v-model="selectedEncoding" size="small">
            <el-radio-button value="utf-8">UTF-8</el-radio-button>
            <el-radio-button value="gb18030">GB18030</el-radio-button>
          </el-radio-group>
        </div>

        <!-- 副产物 -->
        <div class="sidecar-row">
          <el-checkbox v-model="includeSidecars">
            附带元数据副产物
          </el-checkbox>
          <span class="sidecar-hint">
            metadata.json{{ selectedCode === 'kdp' ? ' + kdp_listing.txt' : '' }},便于人工对照填上架表单
          </span>
        </div>

        <!-- 平台 notes -->
        <el-collapse v-if="selected.notes" class="notes">
          <el-collapse-item title="平台注意事项" name="notes">
            <pre class="notes-pre">{{ selected.notes }}</pre>
          </el-collapse-item>
        </el-collapse>

        <!-- 元数据状态 -->
        <div v-if="selected.metadata_schema?.length" class="meta-status">
          <div class="meta-status-title">该平台需要的元数据</div>
          <div v-if="missingFields.length" class="meta-missing">
            <el-icon class="warning-icon"><Warning /></el-icon>
            <div class="meta-missing-body">
              <div class="meta-missing-list">
                缺少:
                <span v-for="f in missingFields" :key="f.key" class="missing-pill">
                  {{ f.label || FIELD_LABELS[f.key] || f.key }}
                </span>
              </div>
              <el-button type="primary" size="small" @click="goFillMeta">
                去填写
              </el-button>
            </div>
          </div>
          <div class="meta-rows">
            <div v-for="f in presentFields" :key="f.key" class="meta-row ok">
              <span class="meta-key">{{ FIELD_LABELS[f.key] || f.label || f.key }}</span>
              <span class="meta-val">{{ f.display }}</span>
            </div>
          </div>
        </div>
      </section>
    </div>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button
        type="primary"
        :icon="Download"
        :disabled="!canExport"
        @click="onExport"
      >
        导出 ({{ selectedFormats.length }})
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.export-dialog {
  display: flex;
  flex-direction: column;
  gap: 18px;
  max-height: 64vh;
  overflow: auto;
}
.step-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2329;
  margin-bottom: 8px;
}
.group {
  margin-bottom: 10px;
}
.group-title {
  font-size: 12px;
  color: #86909c;
  margin: 6px 0;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 8px;
}
.card {
  text-align: left;
  padding: 10px 12px;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, transform 0.05s;
  font-family: inherit;
}
.card:hover {
  border-color: #4080ff;
}
.card.active {
  border-color: #4080ff;
  background: #ecf5ff;
}
.card-name {
  font-size: 13px;
  font-weight: 600;
  color: #1f2329;
  margin-bottom: 4px;
}
.card-formats {
  font-size: 11px;
  color: #86909c;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.formats {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.format-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid #e5e6eb;
  border-radius: 6px;
  cursor: pointer;
  background: #fff;
}
.format-row.checked {
  border-color: #4080ff;
  background: #f6faff;
}
.format-text {
  flex: 1;
  min-width: 0;
}
.format-name {
  font-size: 13px;
  color: #1f2329;
  font-weight: 500;
}
.format-hint {
  font-size: 12px;
  color: #86909c;
  margin-top: 2px;
}
.encoding-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
  font-size: 12px;
}
.encoding-label {
  color: #5b6471;
}
.sidecar-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
  font-size: 12px;
}
.sidecar-hint {
  color: #86909c;
}
.notes {
  margin-top: 6px;
}
.notes-pre {
  white-space: pre-wrap;
  font-family: inherit;
  font-size: 12px;
  color: #4e5969;
  margin: 0;
}
.meta-status {
  margin-top: 10px;
  border: 1px solid #e5e6eb;
  border-radius: 6px;
  padding: 10px 12px;
  background: #fafbfc;
}
.meta-status-title {
  font-size: 12px;
  color: #86909c;
  margin-bottom: 8px;
}
.meta-missing {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  background: #fff7e6;
  border: 1px solid #ffd591;
  border-radius: 6px;
  padding: 8px 10px;
  margin-bottom: 8px;
}
.warning-icon {
  color: #d46b08;
  margin-top: 3px;
}
.meta-missing-body {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.meta-missing-list {
  flex: 1;
  font-size: 12px;
  color: #d46b08;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.missing-pill {
  background: #ffe7c2;
  border-radius: 10px;
  padding: 2px 8px;
}
.meta-rows {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.meta-row {
  display: flex;
  font-size: 12px;
  gap: 8px;
}
.meta-key {
  color: #86909c;
  min-width: 64px;
}
.meta-val {
  color: #1f2329;
  word-break: break-all;
}
</style>
