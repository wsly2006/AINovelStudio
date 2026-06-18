<script setup>
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { chaptersApi } from '../api/chapters'
import ChapterBeatsEditor from './ChapterBeatsEditor.vue'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  chapterId: { type: Number, default: null },
  chapterTitle: { type: String, default: '' },
  initialBeats: { type: Array, default: () => [] },
  threads: { type: Array, default: () => [] },
  targetWordCount: { type: Number, default: 4000 },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const { t } = useI18n()

const beats = ref([])
const saving = ref(false)

watch(
  () => [props.modelValue, props.initialBeats],
  ([visible, init]) => {
    if (!visible) return
    beats.value = Array.isArray(init)
      ? init.map((b) => ({
          title: b.title || '',
          detail: b.detail || '',
          thread_titles: Array.isArray(b.thread_titles) ? b.thread_titles.slice() : [],
        }))
      : []
  },
  { immediate: true }
)

async function onSave() {
  if (saving.value || !props.chapterId) return
  saving.value = true
  try {
    const updated = await chaptersApi.update(props.chapterId, { beats: beats.value })
    emit('saved', { chapterId: props.chapterId, beats: updated.beats })
    ElMessage.success(t('beats.saved' /* fallback */) || '已保存')
    emit('update:modelValue', false)
  } catch (e) {
    ElMessage.error(e.message || t('common.failed'))
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
    :title="t('beats.dialogTitle')"
    width="720px"
    :close-on-click-modal="false"
  >
    <div class="meta">
      <span class="meta-title">{{ chapterTitle }}</span>
      <span class="meta-hint">{{ t('beats.dialogHint') }}</span>
    </div>

    <ChapterBeatsEditor
      v-model="beats"
      :chapter-id="chapterId"
      :threads="threads"
      :target-word-count="targetWordCount"
    />

    <template #footer>
      <el-button @click="close">{{ t('common.cancel') }}</el-button>
      <el-button type="primary" :loading="saving" @click="onSave">
        {{ t('common.save') }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 16px;
}
.meta-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2329;
}
.meta-hint {
  font-size: 12px;
  color: #86909c;
  line-height: 1.6;
}
</style>
