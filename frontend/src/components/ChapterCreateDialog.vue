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

const form = ref({ title: '', summary: '' })
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

async function onSubmit() {
  if (!formRef.value) return
  // 副标题与概述都允许为空,无需校验
  submitting.value = true
  try {
    const payload = {
      title: form.value.title.trim(),
      summary: form.value.summary.trim() || null,
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
      <el-form-item :label="t('chapterDialog.titleLabel')">
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
      <el-form-item v-if="showSummary" :label="t('chapterDialog.summaryLabel')">
        <el-input
          v-model="form.summary"
          type="textarea"
          :rows="4"
          :placeholder="t('chapterDialog.summaryPlaceholder')"
          maxlength="4000"
          show-word-limit
        />
      </el-form-item>
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
</style>
