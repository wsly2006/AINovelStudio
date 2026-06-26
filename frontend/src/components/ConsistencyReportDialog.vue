<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { glossaryApi } from '../api/glossary'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  projectId: { type: Number, default: null },
  defaultTargetLang: { type: String, default: 'en-US' },
})
const emit = defineEmits(['update:modelValue'])

const { t } = useI18n()
const router = useRouter()

const LANG_OPTIONS = [
  { value: 'en-US', label: 'English' },
  { value: 'es-ES', label: 'Español' },
  { value: 'id-ID', label: 'Indonesia' },
  { value: 'ja-JP', label: '日本語' },
  { value: 'ko-KR', label: '한국어' },
  { value: 'vi-VN', label: 'Tiếng Việt' },
]

const targetLang = ref(props.defaultTargetLang)
const loading = ref(false)
const report = ref(null)
const errorMsg = ref('')

watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      targetLang.value = props.defaultTargetLang || 'en-US'
      report.value = null
      errorMsg.value = ''
      runCheck()
    }
  }
)

watch(targetLang, () => {
  if (props.modelValue) runCheck()
})

async function runCheck() {
  if (!props.projectId) return
  loading.value = true
  errorMsg.value = ''
  try {
    report.value = await glossaryApi.checkConsistency(
      props.projectId,
      targetLang.value
    )
  } catch (e) {
    errorMsg.value =
      e?.response?.data?.detail || e.message || t('glossary.consistencyFailed')
    ElMessage.error(errorMsg.value)
  } finally {
    loading.value = false
  }
}

function close() {
  emit('update:modelValue', false)
}

function jumpToChapter(issue) {
  // 跳到正文 tab,选中目标章节;翻译版本要用户自己开历史看
  if (!props.projectId) return
  router.push({
    name: 'workspace-content',
    params: { id: String(props.projectId) },
    query: { chapter: String(issue.chapter_id) },
  })
  close()
}

const grouped = computed(() => {
  const all = report.value?.issues || []
  const byChapter = new Map()
  for (const it of all) {
    if (!byChapter.has(it.chapter_id)) {
      byChapter.set(it.chapter_id, {
        chapterId: it.chapter_id,
        chapterOrder: it.chapter_order,
        chapterTitle: it.chapter_title,
        items: [],
      })
    }
    byChapter.get(it.chapter_id).items.push(it)
  }
  return [...byChapter.values()].sort(
    (a, b) => a.chapterOrder - b.chapterOrder
  )
})

const summaryText = computed(() => {
  if (!report.value) return ''
  return t('glossary.consistencySummary', {
    issues: report.value.issues.length,
    chapters: report.value.checked_chapters,
    total: report.value.total_chapters,
    terms: report.value.glossary_size,
  })
})
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    :title="t('glossary.consistencyDialogTitle')"
    width="720px"
    :close-on-click-modal="false"
  >
    <div class="content" v-loading="loading">
      <div class="head">
        <span class="hint">{{ t('glossary.consistencyHint') }}</span>
        <el-select v-model="targetLang" size="small" style="width: 140px">
          <el-option
            v-for="opt in LANG_OPTIONS"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
      </div>

      <div v-if="report" class="summary">{{ summaryText }}</div>

      <div v-if="report && report.issues.length === 0" class="empty">
        <div class="emoji">✓</div>
        <p>{{ t('glossary.consistencyAllGood') }}</p>
      </div>

      <div v-if="grouped.length > 0" class="issues">
        <div v-for="grp in grouped" :key="grp.chapterId" class="grp">
          <div class="grp-head">
            <span class="chap-label">
              {{ t('formats.chapterOrder', { n: grp.chapterOrder }) }}
              <span v-if="grp.chapterTitle" class="chap-sub">
                《{{ grp.chapterTitle }}》
              </span>
            </span>
            <el-button text size="small" @click="jumpToChapter(grp.items[0])">
              {{ t('glossary.consistencyJump') }}
            </el-button>
          </div>
          <div v-for="it in grp.items" :key="it.source" class="issue-row">
            <span class="src">{{ it.source }}</span>
            <span class="arrow">→</span>
            <span class="tgt">{{ it.expected_target }}</span>
            <el-tag size="small" type="info" effect="plain" class="type-tag">
              {{ it.entry_type }}
            </el-tag>
          </div>
        </div>
      </div>

      <div v-if="errorMsg" class="error">{{ errorMsg }}</div>
    </div>

    <template #footer>
      <el-button @click="close">{{ t('common.close') }}</el-button>
      <el-button type="primary" @click="runCheck" :loading="loading">
        {{ t('glossary.consistencyRerun') }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.content {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 200px;
  max-height: 560px;
  overflow: auto;
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.hint {
  color: #4e5969;
  font-size: 13px;
  line-height: 1.6;
}
.summary {
  font-size: 13px;
  color: #1f2329;
  background: #f5f7fa;
  border-radius: 6px;
  padding: 8px 12px;
}
.empty {
  text-align: center;
  color: #00b42a;
  padding: 24px 0;
}
.empty .emoji {
  font-size: 36px;
  margin-bottom: 6px;
}
.issues {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.grp {
  border: 1px solid #fbcfe8;
  background: #fff7fb;
  border-radius: 8px;
  padding: 10px 12px;
}
.grp-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.chap-label {
  font-weight: 600;
  color: #1f2329;
}
.chap-sub {
  color: #4e5969;
  font-weight: 400;
  margin-left: 4px;
}
.issue-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 13px;
}
.src {
  color: #1f2329;
  font-weight: 500;
}
.arrow {
  color: #86909c;
}
.tgt {
  color: #4080ff;
  font-family: ui-monospace, 'Cascadia Code', monospace;
}
.type-tag {
  margin-left: auto;
}
.error {
  color: #f53f3f;
  font-size: 13px;
  background: #fef0f0;
  padding: 8px 12px;
  border-radius: 6px;
}
</style>
