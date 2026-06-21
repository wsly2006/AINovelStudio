<script setup>
import { ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  mode: { type: String, default: 'create' }, // 'create' | 'rename' | 'edit'
  orderIndex: { type: Number, default: 1 },
  title: { type: String, default: '' },
  summary: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'submit'])

const { t } = useI18n()

const form = ref({ title: '', summary: '', count: 1 })
const formRef = ref(null)
const submitting = ref(false)

const prefix = computed(() => t('chapterDialog.orderPrefix', { n: props.orderIndex }))

watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      form.value = {
        title: props.title || '',
        summary: props.summary || '',
        count: 1,
      }
    }
  }
)

const dialogTitle = computed(() => {
  if (props.mode === 'rename') return t('chapterDialog.renameTitle')
  if (props.mode === 'edit') return t('chapterDialog.editTitle')
  return t('chapterDialog.createTitle')
})

const submitText = computed(() =>
  props.mode === 'create' ? t('common.create') : t('common.save')
)

const showSummary = computed(() => props.mode !== 'rename')
// 仅在新建时显示数量字段;批量创建只追加空白章节,跳过副标题/大纲输入
const showCount = computed(() => props.mode === 'create')
const isBatch = computed(() => showCount.value && form.value.count > 1)

const batchRangeText = computed(() => {
  const n = form.value.count
  if (n <= 1) return ''
  return t('chapterDialog.batchRangePreview', {
    from: props.orderIndex,
    to: props.orderIndex + n - 1,
    count: n,
  })
})

async function onSubmit() {
  if (!formRef.value) return
  submitting.value = true
  try {
    const count = isBatch.value ? Math.max(1, Math.min(50, form.value.count)) : 1
    const payload = {
      title: count > 1 ? '' : form.value.title.trim(),
      summary: count > 1 ? null : form.value.summary.trim() || null,
      count,
    }
    await emit('submit', payload)
    emit('update:modelValue', false)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    :title="dialogTitle"
    width="480px"
  >
    <el-form ref="formRef" :model="form" label-width="72px">
      <el-form-item v-if="showCount" :label="t('chapterDialog.countLabel')">
        <el-input-number
          v-model="form.count"
          :min="1"
          :max="50"
          :step="1"
          controls-position="right"
        />
        <div class="hint">{{ t('chapterDialog.countHint') }}</div>
        <div v-if="isBatch" class="batch-preview">
          {{ batchRangeText }}
        </div>
      </el-form-item>
      <el-form-item v-if="!isBatch" :label="t('chapterDialog.titleLabel')">
        <el-input
          v-model="form.title"
          :placeholder="t('chapterDialog.titlePlaceholder')"
          maxlength="200"
          show-word-limit
        >
          <template #prepend>
            <span class="prefix">{{ prefix }}</span>
          </template>
        </el-input>
        <div class="hint">{{ t('chapterDialog.titleHint') }}</div>
      </el-form-item>
      <el-form-item v-if="showSummary && !isBatch" :label="t('chapterDialog.summaryLabel')">
        <el-input
          v-model="form.summary"
          type="textarea"
          :rows="4"
          :placeholder="t('chapterDialog.summaryPlaceholder')"
          maxlength="4000"
          show-word-limit
        />
      </el-form-item>
      <div v-if="isBatch" class="batch-skip">
        {{ t('chapterDialog.batchSkipFields') }}
      </div>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">{{ t('common.cancel') }}</el-button>
      <el-button type="primary" :loading="submitting" @click="onSubmit">
        {{ submitText }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.prefix {
  color: #1f2329;
  font-weight: 600;
}
.hint {
  font-size: 12px;
  color: #86909c;
  margin-top: 4px;
  line-height: 1.5;
}
.batch-preview {
  margin-top: 6px;
  font-size: 13px;
  color: #4080ff;
  font-weight: 500;
}
.batch-skip {
  padding: 8px 12px;
  margin: 0 0 0 72px;
  font-size: 12px;
  color: #86909c;
  background: #f5f7fa;
  border-radius: 6px;
  line-height: 1.6;
}
</style>
