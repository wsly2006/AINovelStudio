<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { MagicStick, Delete } from '@element-plus/icons-vue'
import { outlineApi } from '../api/outline'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  projectId: { type: Number, default: null },
  // 已有章节列表(传入避免重复 fetch),用于「插入位置」选择
  chapters: { type: Array, default: () => [] },
  defaultTargetWordCount: { type: Number, default: 4000 },
})
const emit = defineEmits(['update:modelValue', 'created'])

const { t } = useI18n()

// 步骤:'config' = 配置 + 草拟,'preview' = 预览/编辑/确认
const stage = ref('config')
const count = ref(10)
// 起始位置:null = 末尾追加;否则填 order_index
const startOrderIndex = ref(null)
const extraInstruction = ref('')
const targetWordCount = ref(props.defaultTargetWordCount)

const suggesting = ref(false)
const creating = ref(false)
const drafts = ref([])

const insertOptions = computed(() => {
  // 末尾追加 + 在「第 N 章」之前插入(本期只支持末尾追加,简单;占位预留)
  return [{ value: null, label: t('outline.insertAtEnd') }]
})

watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      stage.value = 'config'
      count.value = 10
      startOrderIndex.value = null
      extraInstruction.value = ''
      targetWordCount.value = props.defaultTargetWordCount || 4000
      drafts.value = []
    }
  }
)

async function onSuggest() {
  if (!props.projectId || suggesting.value) return
  suggesting.value = true
  try {
    const data = await outlineApi.batchSuggest(props.projectId, {
      count: count.value,
      start_order_index: startOrderIndex.value,
      extra_instruction: extraInstruction.value || null,
      target_word_count: targetWordCount.value,
    })
    drafts.value = (data.drafts || []).map((d) => ({
      title: d.title || '',
      summary: d.summary || '',
      beats: Array.isArray(d.beats) ? d.beats.slice() : [],
    }))
    if (drafts.value.length === 0) {
      ElMessage.warning(t('outline.suggestEmpty'))
      return
    }
    stage.value = 'preview'
    ElMessage.success(t('outline.suggestDone', { n: drafts.value.length }))
  } catch (e) {
    const detail = e?.response?.data?.detail
    ElMessage.error(detail || e.message || t('outline.suggestFailed'))
  } finally {
    suggesting.value = false
  }
}

function removeDraft(i) {
  drafts.value.splice(i, 1)
}

async function onConfirm() {
  if (!props.projectId || creating.value || drafts.value.length === 0) return
  creating.value = true
  try {
    // 后端会过滤,但前端先把空 title + 空 summary + 空 beats 的草稿丢掉
    const payload = drafts.value
      .map((d) => ({
        title: (d.title || '').trim(),
        summary: (d.summary || '').trim() || null,
        beats: Array.isArray(d.beats) ? d.beats : [],
      }))
      .filter((d) => d.title || d.summary || (d.beats && d.beats.length))
    if (!payload.length) {
      ElMessage.warning(t('outline.allEmpty'))
      return
    }
    const data = await outlineApi.batchCreate(props.projectId, payload)
    ElMessage.success(t('outline.createDone', { n: data.chapters.length }))
    emit('created', data.chapters)
    emit('update:modelValue', false)
  } catch (e) {
    const detail = e?.response?.data?.detail
    ElMessage.error(detail || e.message || t('common.failed'))
  } finally {
    creating.value = false
  }
}

function onClose() {
  emit('update:modelValue', false)
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    :title="t('outline.batchDialogTitle')"
    width="780px"
    :close-on-click-modal="false"
    :close-on-press-escape="!suggesting && !creating"
  >
    <!-- 配置阶段 -->
    <div v-if="stage === 'config'" class="config">
      <el-form label-width="100px" label-position="left">
        <el-form-item :label="t('outline.fieldCount')">
          <el-input-number v-model="count" :min="1" :max="30" :step="1" />
          <span class="hint">{{ t('outline.countHint') }}</span>
        </el-form-item>
        <el-form-item :label="t('outline.fieldInsertAt')">
          <el-select v-model="startOrderIndex" style="width: 240px">
            <el-option
              v-for="opt in insertOptions"
              :key="String(opt.value)"
              :value="opt.value"
              :label="opt.label"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('outline.fieldTargetWords')">
          <el-input-number v-model="targetWordCount" :min="500" :max="20000" :step="500" />
          <span class="hint">{{ t('outline.targetWordsHint') }}</span>
        </el-form-item>
        <el-form-item :label="t('outline.fieldExtra')">
          <el-input
            v-model="extraInstruction"
            type="textarea"
            :autosize="{ minRows: 3, maxRows: 6 }"
            :placeholder="t('outline.extraPlaceholder')"
            maxlength="2000"
            show-word-limit
          />
        </el-form-item>
      </el-form>
    </div>

    <!-- 预览阶段 -->
    <div v-else class="preview">
      <div class="preview-head">
        <span class="head-title">{{ t('outline.previewTitle', { n: drafts.length }) }}</span>
        <span class="head-hint">{{ t('outline.previewHint') }}</span>
      </div>
      <div v-if="drafts.length === 0" class="empty">
        {{ t('outline.previewEmpty') }}
      </div>
      <div v-else class="draft-list">
        <div v-for="(d, i) in drafts" :key="i" class="draft-row">
          <div class="draft-head">
            <span class="idx">{{ i + 1 }}</span>
            <el-input
              v-model="d.title"
              :placeholder="t('outline.draftTitlePlaceholder')"
              maxlength="200"
              class="title-input"
            />
            <el-button text type="danger" :icon="Delete" @click="removeDraft(i)" />
          </div>
          <el-input
            v-model="d.summary"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 5 }"
            :placeholder="t('outline.draftSummaryPlaceholder')"
            maxlength="4000"
            class="summary-input"
          />
          <div v-if="d.beats && d.beats.length" class="beats-preview">
            <div class="beats-head">
              {{ t('outline.draftBeatsCount', { n: d.beats.length }) }}
            </div>
            <ol class="beats-list">
              <li v-for="(b, j) in d.beats" :key="j">
                <span class="beat-title">{{ b.title }}</span>
                <span v-if="b.detail" class="beat-detail">— {{ b.detail }}</span>
              </li>
            </ol>
          </div>
          <div v-else class="beats-empty">
            {{ t('outline.draftNoBeats') }}
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <template v-if="stage === 'config'">
        <el-button @click="onClose">{{ t('common.cancel') }}</el-button>
        <el-button
          type="primary"
          :icon="MagicStick"
          :loading="suggesting"
          @click="onSuggest"
        >
          {{ t('outline.startSuggest') }}
        </el-button>
      </template>
      <template v-else>
        <el-button @click="stage = 'config'" :disabled="creating">
          {{ t('outline.backToConfig') }}
        </el-button>
        <el-button
          type="primary"
          :loading="creating"
          :disabled="drafts.length === 0"
          @click="onConfirm"
        >
          {{ t('outline.confirmCreate', { n: drafts.length }) }}
        </el-button>
      </template>
    </template>
  </el-dialog>
</template>

<style scoped>
.config .hint {
  margin-left: 12px;
  color: #86909c;
  font-size: 12px;
}
.preview-head {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e5e6eb;
}
.head-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2329;
}
.head-hint {
  font-size: 12px;
  color: #86909c;
}
.empty {
  text-align: center;
  color: #c9cdd4;
  padding: 30px;
}
.draft-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 60vh;
  overflow-y: auto;
}
.draft-row {
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.draft-row:hover {
  border-color: #c9d2ff;
}
.draft-head {
  display: flex;
  align-items: center;
  gap: 6px;
}
.idx {
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #ecf5ff;
  color: #4080ff;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}
.title-input {
  flex: 1;
  min-width: 0;
}
.summary-input :deep(textarea) {
  font-size: 13px;
  line-height: 1.6;
}
.beats-preview {
  background: #fafbfc;
  border-radius: 6px;
  padding: 6px 10px;
}
.beats-head {
  font-size: 12px;
  color: #4e5969;
  font-weight: 500;
  margin-bottom: 4px;
}
.beats-list {
  margin: 0;
  padding-left: 20px;
  font-size: 12px;
  line-height: 1.7;
  color: #4e5969;
}
.beat-title {
  font-weight: 500;
  color: #1f2329;
}
.beat-detail {
  color: #86909c;
}
.beats-empty {
  font-size: 12px;
  color: #c9cdd4;
  font-style: italic;
}
</style>
