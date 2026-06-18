<script setup>
import { ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Document, Delete, MagicStick } from '@element-plus/icons-vue'
import { projectsApi } from '../api/projects'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
})
const emit = defineEmits(['update:modelValue', 'imported', 'ai-create'])

const { t } = useI18n()

const GENRE_KEYS = [
  'fantasy', 'eastern_fantasy', 'wuxia', 'xianxia',
  'urban', 'history', 'scifi', 'game',
  'mystery', 'romance', 'other',
]
const COLORS = ['#5b8def', '#7c3aed', '#ec4899', '#f59e0b', '#10b981', '#06b6d4', '#ef4444', '#6b7280']

const CHANNEL_OPTIONS = [
  { key: 'male', tKey: 'channelMale' },
  { key: 'female', tKey: 'channelFemale' },
  { key: 'danmei', tKey: 'channelDanmei' },
  { key: 'general', tKey: 'channelGeneral' },
]

// 标签预设(key 与后端 ladder_service.TAG_TO_SYSTEM 中的 key 一致)
const TAG_PRESETS = [
  'apocalypse', 'rebirth', 'transmigration', 'system', 'infinite',
  'esper', 'cultivation', 'martial', 'mecha', 'interstellar',
  'palace', 'farming', 'fastWear', 'abo', 'sweet', 'tragedy',
  'schoolLife', 'workplace', 'detective', 'horror',
]

const PROGRESSION_GENRES = ['xianxia', 'wuxia', 'fantasy', 'eastern_fantasy']
const PROGRESSION_TAGS = ['esper', 'apocalypse', 'evolution', 'cultivation', 'martial', 'mecha']

const PROGRESSION_OPTIONS = [
  { key: 'xianxia', tKey: 'progressionXianxia' },
  { key: 'wuxia', tKey: 'progressionWuxia' },
  { key: 'fantasy', tKey: 'progressionFantasy' },
  { key: 'eastern_fantasy', tKey: 'progressionEastern' },
  { key: 'esper', tKey: 'progressionEsper' },
  { key: '', tKey: 'progressionNone' },
]

const TAG_TO_SYSTEM = {
  esper: 'esper', apocalypse: 'esper', evolution: 'esper', mecha: 'esper',
  cultivation: 'xianxia', martial: 'wuxia',
}

const MAX_UPLOAD = 50 * 1024 * 1024

const genreOptions = computed(() =>
  GENRE_KEYS.map((key) => ({ key, label: t(`genre.${key}`) }))
)

const showProgression = computed(() => {
  if (PROGRESSION_GENRES.includes(form.value.genre)) return true
  return form.value.tags.some((tag) => PROGRESSION_TAGS.includes(tag))
})

const form = ref({
  name: '',
  description: '',
  channel: 'general',
  genre: '',
  tags: [],
  cover_color: COLORS[0],
  progression_system: '',
  target_word_count: 80000,
  words_per_chapter: 4000,
})
const formRef = ref(null)
const submitting = ref(false)
// 顶部 tab:'ai' = AI 一键开书,'import' = 仅导入原稿不走 AI
const activeTab = ref('ai')

// AI 起书名 / 生简介:都是同步一次性调用,本地保留 loading + 起名候选列表
const titleSuggesting = ref(false)
const descSuggesting = ref(false)
const titleCandidates = ref([])      // 候选书名,空数组 = 不显示候选区

// 章节数完全由总字数 / 每章字数算出来,不让用户手动改,避免三个数字互相打架
const chapterCount = computed(() => {
  const words = Number(form.value.target_word_count) || 0
  const per = Number(form.value.words_per_chapter) || 1
  return Math.max(1, Math.min(200, Math.round(words / per)))
})

// 导入小说原稿状态
const fileInput = ref(null)
const novelFile = ref(null)            // 选中的 File 对象
const detecting = ref(false)            // 正在调预览接口
const detectResult = ref(null)         // {chapter_count, total_chars, preview}
const detectError = ref('')

const rules = computed(() => ({
  name: [{ required: true, message: t('projectDialog.nameRequired'), trigger: 'blur' }],
}))

watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      form.value = {
        name: '',
        description: '',
        channel: 'general',
        genre: '',
        tags: [],
        cover_color: COLORS[Math.floor(Math.random() * COLORS.length)],
        progression_system: '',
        target_word_count: 80000,
        words_per_chapter: 4000,
      }
      novelFile.value = null
      detectResult.value = null
      detectError.value = ''
      titleCandidates.value = []
      titleSuggesting.value = false
      descSuggesting.value = false
      activeTab.value = 'ai'
    }
  }
)

function pickDefaultSystem() {
  if (PROGRESSION_GENRES.includes(form.value.genre)) {
    return form.value.genre
  }
  for (const tag of form.value.tags) {
    if (TAG_TO_SYSTEM[tag]) return TAG_TO_SYSTEM[tag]
  }
  return ''
}
watch(
  () => [form.value.genre, form.value.tags.slice()],
  () => {
    if (showProgression.value) {
      form.value.progression_system = pickDefaultSystem()
    } else {
      form.value.progression_system = ''
    }
  }
)

function toggleTag(tag) {
  const idx = form.value.tags.indexOf(tag)
  if (idx >= 0) form.value.tags.splice(idx, 1)
  else form.value.tags.push(tag)
}

// AI 起书名 / 生简介共用的入参,所有字段都按当前表单填了什么传什么
function buildSuggestPayload() {
  return {
    name: form.value.name?.trim() || null,
    description: form.value.description?.trim() || null,
    channel: form.value.channel || null,
    genre: form.value.genre || null,
    tags: form.value.tags.slice(),
  }
}

async function onSuggestTitle() {
  if (titleSuggesting.value) return
  titleSuggesting.value = true
  titleCandidates.value = []
  try {
    const data = await projectsApi.suggestTitle(buildSuggestPayload())
    const list = Array.isArray(data?.titles) ? data.titles.filter(Boolean) : []
    if (!list.length) {
      ElMessage.warning(t('projectDialog.aiTitleEmpty'))
    } else {
      titleCandidates.value = list
    }
  } catch (e) {
    ElMessage.error(e.message || t('projectDialog.aiTitleFailed'))
  } finally {
    titleSuggesting.value = false
  }
}

function pickTitle(title) {
  form.value.name = title
  titleCandidates.value = []
}

async function onSuggestDescription() {
  if (descSuggesting.value) return
  descSuggesting.value = true
  try {
    const data = await projectsApi.suggestDescription(buildSuggestPayload())
    const text = (data?.description || '').trim()
    if (!text) {
      ElMessage.warning(t('projectDialog.aiDescEmpty'))
    } else {
      form.value.description = text
    }
  } catch (e) {
    ElMessage.error(e.message || t('projectDialog.aiDescFailed'))
  } finally {
    descSuggesting.value = false
  }
}

function pickFile() {
  fileInput.value?.click()
}

async function onFileChosen(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file) return
  if (file.size > MAX_UPLOAD) {
    detectError.value = t('projectDialog.importTooBig')
    return
  }
  novelFile.value = file
  detectResult.value = null
  detectError.value = ''
  detecting.value = true
  // 没填名字时,用文件名(去扩展名)填进去
  if (!form.value.name.trim()) {
    form.value.name = file.name.replace(/\.[^.]+$/, '')
  }
  try {
    const fd = new FormData()
    fd.append('file', file)
    const resp = await fetch('/api/projects/import-novel/preview', {
      method: 'POST',
      body: fd,
    })
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}))
      throw new Error(data.detail || `HTTP ${resp.status}`)
    }
    const data = await resp.json()
    if (!data.chapter_count) {
      detectError.value = t('projectDialog.importEmpty')
    } else {
      detectResult.value = data
    }
  } catch (err) {
    detectError.value = `${t('projectDialog.importFailed')}: ${err.message}`
    novelFile.value = null
  } finally {
    detecting.value = false
  }
}

function clearFile() {
  novelFile.value = null
  detectResult.value = null
  detectError.value = ''
}

async function onSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      if (activeTab.value === 'import') {
        if (!novelFile.value || !detectResult.value) return
        await submitWithNovel()
      } else {
        emit('ai-create', buildAIPayload())
      }
      emit('update:modelValue', false)
    } finally {
      submitting.value = false
    }
  })
}

function buildAIPayload() {
  const project = {
    name: form.value.name,
    description: form.value.description || null,
    channel: form.value.channel || null,
    genre: form.value.genre || null,
    tags: form.value.tags,
    cover_color: form.value.cover_color,
    words_per_chapter: Number(form.value.words_per_chapter) || 4000,
  }
  if (showProgression.value) {
    project.progression_system = form.value.progression_system
  }
  return {
    project,
    target_word_count: Number(form.value.target_word_count) || 80000,
    chapter_count: chapterCount.value,
  }
}

async function submitWithNovel() {
  const fd = new FormData()
  fd.append('file', novelFile.value)
  fd.append('name', form.value.name)
  if (form.value.description) fd.append('description', form.value.description)
  if (form.value.channel) fd.append('channel', form.value.channel)
  if (form.value.genre) fd.append('genre', form.value.genre)
  if (form.value.tags.length) fd.append('tags', JSON.stringify(form.value.tags))
  if (form.value.cover_color) fd.append('cover_color', form.value.cover_color)
  if (showProgression.value) {
    fd.append('progression_system', form.value.progression_system)
  }
  fd.append('words_per_chapter', String(Number(form.value.words_per_chapter) || 4000))

  const resp = await fetch('/api/projects/import-novel', { method: 'POST', body: fd })
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}))
    const msg = data.detail || `HTTP ${resp.status}`
    ElMessage.error(msg)
    throw new Error(msg)
  }
  const data = await resp.json()
  emit('imported', data)
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    :title="t('projectDialog.title')"
    width="580px"
  >
    <el-tabs v-model="activeTab" class="mode-tabs">
      <el-tab-pane :label="t('projectDialog.tabAI')" name="ai" />
      <el-tab-pane :label="t('projectDialog.tabImport')" name="import" />
    </el-tabs>
    <div class="mode-hint">
      {{ activeTab === 'ai' ? t('projectDialog.tabAIHint') : t('projectDialog.tabImportHint') }}
    </div>
    <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
      <el-form-item :label="t('projectDialog.nameLabel')" prop="name">
        <div class="field-with-ai">
          <el-input
            v-model="form.name"
            :placeholder="t('projectDialog.namePlaceholder')"
            maxlength="120"
            show-word-limit
            class="field-input"
          />
          <el-button
            class="ai-suggest-btn"
            :icon="MagicStick"
            :loading="titleSuggesting"
            @click="onSuggestTitle"
          >
            {{ t('projectDialog.aiSuggestTitle') }}
          </el-button>
        </div>
        <div v-if="titleCandidates.length" class="title-candidates">
          <div class="hint" style="margin-top: 6px; margin-bottom: 4px">
            {{ t('projectDialog.aiTitleCandidates') }}
          </div>
          <div class="title-chips">
            <el-tag
              v-for="title in titleCandidates"
              :key="title"
              type="primary"
              effect="plain"
              class="title-chip"
              @click="pickTitle(title)"
            >
              {{ title }}
            </el-tag>
          </div>
        </div>
      </el-form-item>
      <el-form-item :label="t('projectDialog.descLabel')">
        <div class="field-with-ai field-with-ai-block">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="4"
            :placeholder="t('projectDialog.aiDescPlaceholder')"
            maxlength="2000"
            class="field-input"
          />
          <el-button
            class="ai-suggest-btn"
            :icon="MagicStick"
            :loading="descSuggesting"
            @click="onSuggestDescription"
          >
            {{ t('projectDialog.aiSuggestDesc') }}
          </el-button>
        </div>
      </el-form-item>

      <el-form-item v-if="activeTab === 'ai'" :label="t('projectDialog.aiScaleLabel')">
        <div class="ai-scale">
          <el-input-number
            v-model="form.target_word_count"
            :min="2000"
            :max="2000000"
            :step="10000"
            :step-strictly="false"
            controls-position="right"
            style="width: 160px"
          />
          <span class="ai-scale-unit">{{ t('projectDialog.aiScaleWordsUnit') }}</span>
          <span class="ai-scale-sep">/</span>
          <el-input-number
            v-model="form.words_per_chapter"
            :min="500"
            :max="20000"
            :step="500"
            :step-strictly="false"
            controls-position="right"
            style="width: 140px"
          />
          <span class="ai-scale-unit">{{ t('projectDialog.aiScaleWordsPerChapterUnit') }}</span>
          <span class="ai-scale-sep">=</span>
          <span class="ai-scale-result">
            {{ t('projectDialog.aiScaleChaptersResult', { n: chapterCount }) }}
          </span>
        </div>
        <div class="hint">{{ t('projectDialog.aiScaleHint') }}</div>
      </el-form-item>

      <el-form-item :label="t('projectDialog.channelLabel')">
        <div class="channel-block">
          <el-radio-group v-model="form.channel" size="default">
            <el-radio-button
              v-for="opt in CHANNEL_OPTIONS"
              :key="opt.key"
              :value="opt.key"
            >
              {{ t(`projectDialog.${opt.tKey}`) }}
            </el-radio-button>
          </el-radio-group>
          <div class="hint">{{ t('projectDialog.channelHint') }}</div>
        </div>
      </el-form-item>

      <el-form-item :label="t('projectDialog.genreLabel')">
        <el-select
          v-model="form.genre"
          :placeholder="t('projectDialog.genrePlaceholder')"
          clearable
          style="width: 100%"
        >
          <el-option
            v-for="opt in genreOptions"
            :key="opt.key"
            :label="opt.label"
            :value="opt.key"
          />
        </el-select>
      </el-form-item>

      <el-form-item :label="t('projectDialog.tagsLabel')">
        <div class="tags-block">
          <div class="tag-grid">
            <el-tag
              v-for="tag in TAG_PRESETS"
              :key="tag"
              :type="form.tags.includes(tag) ? 'primary' : 'info'"
              :effect="form.tags.includes(tag) ? 'dark' : 'plain'"
              class="tag-chip"
              @click="toggleTag(tag)"
            >
              {{ t(`tags.${tag}`) }}
            </el-tag>
          </div>
          <div class="hint">{{ t('projectDialog.tagsHint') }}</div>
        </div>
      </el-form-item>

      <el-form-item v-if="showProgression" :label="t('projectDialog.progressionLabel')">
        <div class="progression-block">
          <div class="hint">{{ t('projectDialog.progressionHint') }}</div>
          <el-radio-group v-model="form.progression_system" class="progression-group">
            <el-radio
              v-for="opt in PROGRESSION_OPTIONS"
              :key="opt.key || 'none'"
              :value="opt.key"
              class="progression-item"
            >
              {{ t(`projectDialog.${opt.tKey}`) }}
            </el-radio>
          </el-radio-group>
        </div>
      </el-form-item>

      <el-form-item v-if="activeTab === 'import'" :label="t('projectDialog.importLabel')">
        <div class="import-block">
          <div class="hint" style="margin-top: 0; margin-bottom: 8px">
            {{ t('projectDialog.importHint') }}
          </div>

          <div v-if="!novelFile" class="import-empty">
            <el-button :icon="Document" @click="pickFile">
              {{ t('projectDialog.importPick') }}
            </el-button>
          </div>

          <div v-else class="import-file">
            <div class="import-file-row">
              <el-icon class="import-file-icon"><Document /></el-icon>
              <span class="import-file-name">{{ novelFile.name }}</span>
              <el-button text :icon="Delete" size="small" @click="clearFile">
                {{ t('projectDialog.importClear') }}
              </el-button>
            </div>
            <div v-if="detecting" class="import-status">
              {{ t('projectDialog.importDetecting') }}
            </div>
            <div v-else-if="detectError" class="import-status import-error">
              {{ detectError }}
            </div>
            <div v-else-if="detectResult" class="import-status import-ok">
              {{
                t('projectDialog.importDetected', {
                  n: detectResult.chapter_count,
                  chars: detectResult.total_chars,
                })
              }}
              <el-button text size="small" @click="pickFile">
                {{ t('projectDialog.importChange') }}
              </el-button>
              <details v-if="detectResult.preview?.length" class="import-preview">
                <summary>{{ t('projectDialog.importPreviewTitle') }}</summary>
                <ul>
                  <li v-for="(p, i) in detectResult.preview" :key="i">
                    {{ t('projectDialog.importPreviewItem', { title: p.title, chars: p.char_count }) }}
                  </li>
                </ul>
              </details>
            </div>
          </div>

          <input
            ref="fileInput"
            type="file"
            accept=".txt,.md,.markdown,text/plain,text/markdown"
            style="display: none"
            @change="onFileChosen"
          />
        </div>
      </el-form-item>

      <el-form-item :label="t('projectDialog.coverColorLabel')">
        <div class="color-picker">
          <span
            v-for="c in COLORS"
            :key="c"
            class="color-dot"
            :class="{ active: form.cover_color === c }"
            :style="{ background: c }"
            @click="form.cover_color = c"
          />
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">{{ t('common.cancel') }}</el-button>
      <el-button
        type="primary"
        :loading="submitting || detecting"
        :disabled="activeTab === 'import' && !detectResult"
        @click="onSubmit"
      >
        <template v-if="activeTab === 'import'">{{ t('projectDialog.importCreateAction') }}</template>
        <template v-else>{{ t('projectDialog.aiCreateAction') }}</template>
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.mode-tabs {
  margin-top: -8px;
  margin-bottom: 4px;
}
.mode-tabs :deep(.el-tabs__header) {
  margin-bottom: 0;
}
.mode-hint {
  font-size: 12px;
  color: #86909c;
  margin-bottom: 12px;
  line-height: 1.5;
}
.color-picker {
  display: flex;
  gap: 8px;
}
.color-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  cursor: pointer;
  border: 2px solid transparent;
  transition: transform 0.1s;
}
.color-dot:hover {
  transform: scale(1.1);
}
.color-dot.active {
  border-color: #1f2329;
}

.channel-block,
.tags-block,
.progression-block,
.import-block {
  width: 100%;
}
.field-with-ai {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}
.field-with-ai-block {
  align-items: flex-start;
}
.field-with-ai .field-input {
  flex: 1;
  min-width: 0;
}
.ai-suggest-btn {
  flex-shrink: 0;
}
.title-candidates {
  width: 100%;
}
.title-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.title-chip {
  cursor: pointer;
  user-select: none;
  font-size: 13px;
  padding: 0 12px;
  height: 28px;
  line-height: 26px;
}
.title-chip:hover {
  background: #ecf5ff;
}
.hint {
  font-size: 12px;
  color: #86909c;
  margin-top: 6px;
  line-height: 1.5;
}
.tag-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.tag-chip {
  cursor: pointer;
  user-select: none;
}
.progression-group {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
  margin-top: 4px;
}
.progression-item {
  margin-right: 0 !important;
}

.import-empty {
  display: flex;
}
.import-file {
  background: #f7f8fa;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  padding: 10px 12px;
}
.import-file-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.import-file-icon {
  color: #5b8def;
  font-size: 16px;
}
.import-file-name {
  flex: 1;
  font-size: 13px;
  color: #1f2329;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.import-status {
  margin-top: 8px;
  font-size: 12px;
  color: #5b6471;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.import-ok {
  color: #10b981;
}
.import-error {
  color: #ef4444;
}
.import-preview {
  width: 100%;
  margin-top: 6px;
  font-size: 12px;
  color: #5b6471;
}
.import-preview ul {
  margin: 6px 0 0;
  padding-left: 20px;
}
.import-preview summary {
  cursor: pointer;
  user-select: none;
}
.ai-scale {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.ai-scale-unit {
  font-size: 13px;
  color: #5b6471;
}
.ai-scale-sep {
  color: #c9cdd4;
  margin: 0 4px;
}
.ai-scale-result {
  font-size: 14px;
  font-weight: 600;
  color: #1f2329;
}
</style>
