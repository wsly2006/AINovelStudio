<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { outlineApi } from '../api/outline'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  chapterId: { type: Number, default: null },
  chapterTitle: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const { t } = useI18n()

const loading = ref(false)
const result = ref(null)
const error = ref('')

const STATUS_META = {
  covered: { color: '#00b42a', icon: '✓' },
  partial: { color: '#fa8c16', icon: '⚠' },
  missing: { color: '#f53f3f', icon: '✗' },
}

const statusLabel = (key) => t(`outlineAlign.status${key.charAt(0).toUpperCase()}${key.slice(1)}`)

watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      // 每次打开重置状态,但不自动跑(让用户拍板)
      result.value = null
      error.value = ''
    }
  }
)

async function runCheck() {
  if (!props.chapterId || loading.value) return
  loading.value = true
  error.value = ''
  try {
    result.value = await outlineApi.checkAlignment(props.chapterId)
  } catch (e) {
    const detail = e?.response?.data?.detail
    error.value = detail || e.message || t('outlineAlign.failed')
    ElMessage.error(error.value)
  } finally {
    loading.value = false
  }
}

function close() {
  emit('update:modelValue', false)
}

const counts = computed(() => {
  if (!result.value) return null
  return {
    covered: result.value.covered || 0,
    partial: result.value.partial || 0,
    missing: result.value.missing || 0,
  }
})
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    :title="t('outlineAlign.dialogTitle')"
    width="720px"
    :close-on-click-modal="false"
  >
    <div class="meta">
      <span class="meta-label">{{ t('outlineAlign.chapterLabel') }}</span>
      <span class="meta-title">{{ chapterTitle }}</span>
    </div>

    <div v-if="!result && !loading" class="placeholder">
      <p>{{ t('outline.pageHint') }}</p>
      <el-button type="primary" :loading="loading" @click="runCheck">
        {{ t('outlineAlign.runButton') }}
      </el-button>
    </div>

    <div v-else-if="loading" class="placeholder">
      <p>{{ t('outlineAlign.running') }}</p>
    </div>

    <div v-else-if="result" class="result">
      <div class="counts">
        <span
          class="count-tag"
          :style="{ background: STATUS_META.covered.color }"
        >
          {{ STATUS_META.covered.icon }} {{ statusLabel('covered') }} {{ counts.covered }}
        </span>
        <span
          class="count-tag"
          :style="{ background: STATUS_META.partial.color }"
        >
          {{ STATUS_META.partial.icon }} {{ statusLabel('partial') }} {{ counts.partial }}
        </span>
        <span
          class="count-tag"
          :style="{ background: STATUS_META.missing.color }"
        >
          {{ STATUS_META.missing.icon }} {{ statusLabel('missing') }} {{ counts.missing }}
        </span>
        <span class="spacer" />
        <el-button text :icon="Refresh" :loading="loading" @click="runCheck">
          {{ t('outlineAlign.rerunButton') }}
        </el-button>
      </div>

      <div class="section">
        <div class="section-head">{{ t('outlineAlign.summaryHead') }}</div>
        <div class="row" :class="`row-${result.summary_status}`">
          <span
            class="status-badge"
            :style="{ background: STATUS_META[result.summary_status].color }"
          >
            {{ STATUS_META[result.summary_status].icon }}
            {{ statusLabel(result.summary_status) }}
          </span>
          <span v-if="result.summary_note" class="note">{{ result.summary_note }}</span>
        </div>
      </div>

      <div v-if="result.beats && result.beats.length" class="section">
        <div class="section-head">{{ t('outlineAlign.beatsHead') }}</div>
        <div
          v-for="b in result.beats"
          :key="b.beat_index"
          class="row"
          :class="`row-${b.status}`"
        >
          <span class="idx">{{ b.beat_index + 1 }}</span>
          <span
            class="status-badge"
            :style="{ background: STATUS_META[b.status].color }"
          >
            {{ STATUS_META[b.status].icon }} {{ statusLabel(b.status) }}
          </span>
          <span v-if="b.note" class="note">{{ b.note }}</span>
        </div>
      </div>

      <div v-if="result.overall_note" class="section overall">
        <div class="section-head">{{ t('outlineAlign.overallHead') }}</div>
        <div class="overall-note">{{ result.overall_note }}</div>
      </div>
    </div>

    <template #footer>
      <el-button @click="close">{{ t('outlineAlign.close') }}</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.meta {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid #e5e6eb;
}
.meta-label {
  font-size: 12px;
  color: #86909c;
}
.meta-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2329;
}
.placeholder {
  text-align: center;
  padding: 30px 20px;
  color: #4e5969;
}
.placeholder p {
  margin-bottom: 16px;
  font-size: 13px;
}
.result {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.counts {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.count-tag {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: 12px;
  background: #4080ff;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.spacer {
  flex: 1;
}
.section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.section-head {
  font-size: 13px;
  font-weight: 600;
  color: #1f2329;
}
.row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 6px;
  background: #fafbfc;
  border: 1px solid #e5e6eb;
}
.row-covered {
  border-left: 3px solid #00b42a;
}
.row-partial {
  border-left: 3px solid #fa8c16;
  background: #fff8ef;
}
.row-missing {
  border-left: 3px solid #f53f3f;
  background: #fff5f5;
}
.idx {
  width: 22px;
  height: 22px;
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
.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 10px;
  background: #4080ff;
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
  white-space: nowrap;
  line-height: 1.5;
}
.note {
  font-size: 12px;
  line-height: 1.6;
  color: #4e5969;
  flex: 1;
}
.overall-note {
  font-size: 13px;
  line-height: 1.7;
  color: #1f2329;
  padding: 10px 12px;
  background: #f7f8fa;
  border-radius: 6px;
}
</style>
