<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  // null = 新建,数字 = 编辑该 id
  editingId: { type: Number, default: null },
  // 编辑时的初值
  initial: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'submit'])

const { t } = useI18n()

const TYPE_OPTIONS = ['person', 'place', 'org', 'term', 'skill', 'item', 'other']
const LANG_OPTIONS = [
  { value: 'en-US', label: 'English (en-US)' },
  { value: 'es-ES', label: 'Español (es-ES)' },
  { value: 'id-ID', label: 'Indonesia (id-ID)' },
  { value: 'ja-JP', label: '日本語 (ja-JP)' },
  { value: 'ko-KR', label: '한국어 (ko-KR)' },
  { value: 'vi-VN', label: 'Tiếng Việt (vi-VN)' },
]

const form = ref({
  source: '',
  target: '',
  target_lang: 'en-US',
  entry_type: 'person',
  notes: '',
  locked: false,
})
const submitting = ref(false)

const dialogTitle = computed(() =>
  props.editingId ? t('common.edit') : t('glossary.newEntry')
)

watch(
  () => props.modelValue,
  (v) => {
    if (!v) return
    if (props.initial) {
      form.value = {
        source: props.initial.source || '',
        target: props.initial.target || '',
        target_lang: props.initial.target_lang || 'en-US',
        entry_type: props.initial.entry_type || 'other',
        notes: props.initial.notes || '',
        locked: !!props.initial.locked,
      }
    } else {
      form.value = {
        source: '',
        target: '',
        target_lang: 'en-US',
        entry_type: 'person',
        notes: '',
        locked: false,
      }
    }
  }
)

async function onSubmit() {
  if (!form.value.source.trim()) return
  submitting.value = true
  try {
    const payload = {
      source: form.value.source.trim(),
      target: form.value.target.trim(),
      target_lang: form.value.target_lang,
      entry_type: form.value.entry_type,
      notes: form.value.notes.trim() || null,
      locked: form.value.locked,
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
    width="520px"
  >
    <el-form label-position="top">
      <el-form-item :label="t('glossary.fieldSource')" required>
        <el-input
          v-model="form.source"
          :placeholder="t('glossary.fieldSourcePlaceholder')"
          maxlength="200"
          show-word-limit
        />
      </el-form-item>
      <el-form-item :label="t('glossary.fieldTarget')">
        <el-input
          v-model="form.target"
          :placeholder="t('glossary.fieldTargetPlaceholder')"
          maxlength="200"
          show-word-limit
        />
      </el-form-item>
      <div class="row">
        <el-form-item :label="t('glossary.fieldTargetLang')" class="col-half">
          <el-select v-model="form.target_lang" style="width: 100%">
            <el-option
              v-for="opt in LANG_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('glossary.fieldType')" class="col-half">
          <el-select v-model="form.entry_type" style="width: 100%">
            <el-option
              v-for="ty in TYPE_OPTIONS"
              :key="ty"
              :label="t(`glossary.typeOptions.${ty}`)"
              :value="ty"
            />
          </el-select>
        </el-form-item>
      </div>
      <el-form-item :label="t('glossary.fieldNotes')">
        <el-input
          v-model="form.notes"
          type="textarea"
          :rows="3"
          :placeholder="t('glossary.fieldNotesPlaceholder')"
          maxlength="2000"
        />
      </el-form-item>
      <el-form-item>
        <el-checkbox v-model="form.locked">
          {{ t('glossary.fieldLocked') }}
        </el-checkbox>
        <div class="hint">{{ t('glossary.lockedHint') }}</div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">
        {{ t('common.cancel') }}
      </el-button>
      <el-button type="primary" :loading="submitting" @click="onSubmit">
        {{ t('common.save') }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.row {
  display: flex;
  gap: 12px;
}
.col-half {
  flex: 1;
}
.hint {
  font-size: 12px;
  color: #86909c;
  margin-top: 4px;
  line-height: 1.5;
}
</style>
