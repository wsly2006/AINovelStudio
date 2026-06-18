<script setup>
import { ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { MagicStick } from '@element-plus/icons-vue'
import { projectsApi } from '../api/projects'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  project: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'saved'])

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

const TAG_PRESETS = [
  'apocalypse', 'rebirth', 'transmigration', 'system', 'infinite',
  'esper', 'cultivation', 'martial', 'mecha', 'interstellar',
  'palace', 'farming', 'fastWear', 'abo', 'sweet', 'tragedy',
  'schoolLife', 'workplace', 'detective', 'horror',
]

const genreOptions = computed(() =>
  GENRE_KEYS.map((key) => ({ key, label: t(`genre.${key}`) }))
)

const form = ref({
  name: '',
  description: '',
  synopsis: '',
  channel: 'general',
  genre: '',
  tags: [],
  cover_color: COLORS[0],
  words_per_chapter: 4000,
})
const formRef = ref(null)
const submitting = ref(false)

const titleSuggesting = ref(false)
const descSuggesting = ref(false)
const titleCandidates = ref([])

const rules = computed(() => ({
  name: [{ required: true, message: t('projectDialog.nameRequired'), trigger: 'blur' }],
}))

// 打开时把工程数据填进表单;关闭时不重置,避免动画期间字段闪烁
watch(
  () => [props.modelValue, props.project],
  ([visible, project]) => {
    if (!visible || !project) return
    form.value = {
      name: project.name || '',
      description: project.description || '',
      synopsis: project.synopsis || '',
      channel: project.channel || 'general',
      genre: project.genre || '',
      tags: Array.isArray(project.tags) ? project.tags.slice() : [],
      cover_color: project.cover_color || COLORS[0],
      words_per_chapter: project.words_per_chapter || 4000,
    }
    titleCandidates.value = []
  },
  { immediate: true }
)

function toggleTag(tag) {
  const idx = form.value.tags.indexOf(tag)
  if (idx >= 0) form.value.tags.splice(idx, 1)
  else form.value.tags.push(tag)
}

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

async function onSubmit() {
  if (!formRef.value || !props.project) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      const payload = {
        name: form.value.name.trim(),
        description: form.value.description?.trim() || null,
        synopsis: form.value.synopsis?.trim() || null,
        channel: form.value.channel || null,
        genre: form.value.genre || null,
        tags: form.value.tags,
        cover_color: form.value.cover_color,
        words_per_chapter: Number(form.value.words_per_chapter) || 4000,
      }
      const updated = await projectsApi.update(props.project.id, payload)
      ElMessage.success(t('common.success'))
      emit('saved', updated)
      emit('update:modelValue', false)
    } catch (e) {
      ElMessage.error(e.message || t('common.failed'))
    } finally {
      submitting.value = false
    }
  })
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    :title="t('projectEdit.title')"
    width="580px"
  >
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

      <el-form-item :label="t('projectEdit.synopsisLabel')">
        <el-input
          v-model="form.synopsis"
          type="textarea"
          :autosize="{ minRows: 6, maxRows: 16 }"
          :placeholder="t('projectEdit.synopsisPlaceholder')"
          maxlength="20000"
          show-word-limit
          resize="vertical"
        />
        <div class="hint">{{ t('projectEdit.synopsisHint') }}</div>
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

      <el-form-item :label="t('projectEdit.wordsPerChapterLabel')">
        <el-input-number
          v-model="form.words_per_chapter"
          :min="500"
          :max="20000"
          :step="500"
          controls-position="right"
          style="width: 160px"
        />
        <span class="ai-scale-unit" style="margin-left: 6px">
          {{ t('projectDialog.aiScaleWordsPerChapterUnit') }}
        </span>
        <div class="hint">{{ t('projectEdit.wordsPerChapterHint') }}</div>
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
      <el-button type="primary" :loading="submitting" @click="onSubmit">
        {{ t('common.save') }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
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
.tags-block {
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
.ai-scale-unit {
  font-size: 13px;
  color: #5b6471;
}
</style>
