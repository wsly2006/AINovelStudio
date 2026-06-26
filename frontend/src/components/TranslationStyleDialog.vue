<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { projectsApi } from '../api/projects'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  projectId: { type: Number, default: null },
  // 父级当前的工程对象,避免每次开都重新拉一遍
  initialGuide: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const { t } = useI18n()

// 预设模板:作者点击 → 追加到文本框末尾。文案直接是「让 AI 看到就懂」的祈使句,
// 避免按 key/i18n 翻译再插入(M5 暂不做多语 UI,作者写的是中文 prompt)
const PRESETS = [
  {
    label: 'Webnovel 风',
    snippet: 'Webnovel 短句风:平均句长偏短,多用分句,避免长定语从句。',
  },
  {
    label: '对白密集',
    snippet: '对话比例至少占 1/3;对白前后给情绪 / 动作小注,避免大段引号悬空。',
  },
  {
    label: '东方称谓直译',
    snippet:
      '保留东方称谓的文化感:师父译 Master、师兄/师姐译 Senior Brother/Senior Sister、前辈译 Senior,首次出现可加 (lit. ...) 简注。',
  },
  {
    label: '修真术语保留拼音',
    snippet:
      '修真 / 武学专有术语保留拼音(qi、jianxin、jindan)首次出现加一句英文注释,后续直用拼音。',
  },
  {
    label: 'Cliffhanger 收尾',
    snippet: '章节结尾保持悬念(cliffhanger):用短句、留白、或一个意料外的转折点收。',
  },
  {
    label: '避免直译成语',
    snippet:
      '中文成语 / 俗语不要逐字直译,改用目标语对应表达或意译说出意思,优先意义传达。',
  },
  {
    label: '拱手礼描述',
    snippet:
      '动作礼节(拱手、作揖、抱拳)用具体动作描述:bowed with cupped hands / clasped fist salute,不要简化成 bowed。',
  },
  {
    label: 'POV 与时态',
    snippet: '默认第三人称限知视角(third-person limited)、过去时,如有切换在新章节里明确标。',
  },
]

const guide = ref(props.initialGuide || '')
const saving = ref(false)

watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      guide.value = props.initialGuide || ''
    }
  }
)
// 父级可能在打开后才拿到 initialGuide,做一次同步
watch(
  () => props.initialGuide,
  (v) => {
    if (props.modelValue) guide.value = v || ''
  }
)

const charCount = computed(() => (guide.value || '').length)
const dirty = computed(() => (guide.value || '') !== (props.initialGuide || ''))

function insertPreset(snippet) {
  const cur = (guide.value || '').trimEnd()
  guide.value = cur ? `${cur}\n${snippet}` : snippet
}

async function save() {
  if (!props.projectId) return
  saving.value = true
  try {
    const updated = await projectsApi.update(props.projectId, {
      translation_style_guide: guide.value || null,
    })
    ElMessage.success(t('glossary.styleSaved'))
    emit('saved', updated.translation_style_guide || '')
    emit('update:modelValue', false)
  } catch (e) {
    ElMessage.error(
      e?.response?.data?.detail || e.message || t('glossary.styleSaveFailed'),
    )
  } finally {
    saving.value = false
  }
}

function close() {
  emit('update:modelValue', false)
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    :title="t('glossary.styleDialogTitle')"
    width="780px"
    :close-on-click-modal="false"
  >
    <div class="layout">
      <div class="left">
        <p class="hint">{{ t('glossary.styleDialogHint') }}</p>
        <el-input
          v-model="guide"
          type="textarea"
          :rows="14"
          maxlength="8000"
          show-word-limit
          :placeholder="t('glossary.stylePlaceholder')"
        />
        <div class="footer-meta">
          <span>{{ charCount }} / 8000</span>
        </div>
      </div>
      <aside class="right">
        <div class="presets-head">{{ t('glossary.stylePresetsLabel') }}</div>
        <div class="presets">
          <el-button
            v-for="p in PRESETS"
            :key="p.label"
            size="small"
            class="preset-btn"
            @click="insertPreset(p.snippet)"
          >
            + {{ p.label }}
          </el-button>
        </div>
        <p class="presets-hint">{{ t('glossary.stylePresetsHint') }}</p>
      </aside>
    </div>

    <template #footer>
      <el-button @click="close">{{ t('common.cancel') }}</el-button>
      <el-button
        type="primary"
        :loading="saving"
        :disabled="!dirty"
        @click="save"
      >
        {{ t('common.save') }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.layout {
  display: grid;
  grid-template-columns: 1fr 220px;
  gap: 16px;
}
.left {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.hint {
  margin: 0 0 4px;
  font-size: 13px;
  color: #4e5969;
  line-height: 1.6;
}
.footer-meta {
  font-size: 12px;
  color: #86909c;
  text-align: right;
}
.right {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: #f5f7fa;
  border-radius: 8px;
  padding: 12px;
}
.presets-head {
  font-size: 13px;
  font-weight: 600;
  color: #1f2329;
}
.presets {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.preset-btn {
  justify-content: flex-start;
  text-align: left;
  white-space: normal;
  height: auto;
  padding: 6px 10px;
  line-height: 1.4;
}
.presets-hint {
  margin: 4px 0 0;
  font-size: 11px;
  color: #86909c;
  line-height: 1.6;
}
</style>
