<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Plus, Delete, MagicStick, Top, Bottom } from '@element-plus/icons-vue'
import { chaptersApi } from '../api/chapters'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  chapterId: { type: Number, default: null },
  // 工程的主线列表(传入便于在节拍上选「推进哪条线」)
  threads: { type: Array, default: () => [] },
  // AI 草拟时的目标字数,影响每拍粒度
  targetWordCount: { type: Number, default: 4000 },
  // 草拟出错时不让用户失去现有手填节拍。compact 留给 AIGenerateDrawer 用紧凑布局
  compact: { type: Boolean, default: false },
  // 节拍-事件对账结果,数组与 modelValue 同序对齐(可空)
  alignment: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])

const { t } = useI18n()

const items = ref([])
const suggesting = ref(false)

// 把对账结果按 beat_index 索引,渲染时按下标取
const alignmentByIndex = computed(() => {
  const m = {}
  for (const a of (props.alignment || [])) {
    if (typeof a?.beat_index === 'number') m[a.beat_index] = a
  }
  return m
})

const STATUS_META = {
  covered: { label: '已兑现', color: '#00b42a', icon: '✓' },
  partial: { label: '弱化', color: '#fa8c16', icon: '⚠' },
  missing: { label: '未兑现', color: '#f53f3f', icon: '✗' },
}

watch(
  () => props.modelValue,
  (v) => {
    items.value = (Array.isArray(v) ? v : []).map((b) => ({
      title: b.title || '',
      detail: b.detail || '',
      thread_titles: Array.isArray(b.thread_titles) ? b.thread_titles.slice() : [],
    }))
  },
  { immediate: true, deep: false }
)

function emitChange() {
  // 只把非空 title 的节拍传出去,避免占位的空行也算节拍
  const out = items.value
    .filter((b) => (b.title || '').trim())
    .map((b) => ({
      title: b.title.trim(),
      detail: (b.detail || '').trim() || null,
      thread_titles: (b.thread_titles || []).filter(Boolean),
    }))
  emit('update:modelValue', out)
}

function addBeat() {
  items.value.push({ title: '', detail: '', thread_titles: [] })
}

function removeBeat(i) {
  items.value.splice(i, 1)
  emitChange()
}

function moveUp(i) {
  if (i <= 0) return
  const t_ = items.value[i]
  items.value.splice(i, 1)
  items.value.splice(i - 1, 0, t_)
  emitChange()
}

function moveDown(i) {
  if (i >= items.value.length - 1) return
  const t_ = items.value[i]
  items.value.splice(i, 1)
  items.value.splice(i + 1, 0, t_)
  emitChange()
}

async function onSuggest() {
  if (suggesting.value || !props.chapterId) return
  suggesting.value = true
  try {
    const data = await chaptersApi.suggestBeats(props.chapterId, {
      target_word_count: props.targetWordCount,
    })
    const beats = Array.isArray(data?.beats) ? data.beats : []
    if (!beats.length) {
      ElMessage.warning(t('beats.suggestEmpty'))
      return
    }
    items.value = beats.map((b) => ({
      title: b.title || '',
      detail: b.detail || '',
      thread_titles: Array.isArray(b.thread_titles) ? b.thread_titles.slice() : [],
    }))
    emitChange()
    ElMessage.success(t('beats.suggestDone', { n: beats.length }))
  } catch (e) {
    const detail = e?.response?.data?.detail
    ElMessage.error(detail || e.message || t('beats.suggestFailed'))
  } finally {
    suggesting.value = false
  }
}
</script>

<template>
  <div class="beats-editor" :class="{ compact }">
    <div class="header">
      <span class="count">{{ t('beats.countLabel', { n: items.length }) }}</span>
      <span class="spacer" />
      <el-button
        size="small"
        :icon="MagicStick"
        :loading="suggesting"
        :disabled="!chapterId"
        @click="onSuggest"
      >
        {{ t('beats.aiSuggest') }}
      </el-button>
      <el-button size="small" :icon="Plus" @click="addBeat">
        {{ t('beats.add') }}
      </el-button>
    </div>

    <div v-if="items.length === 0" class="empty">
      {{ t('beats.empty') }}
    </div>

    <div v-else class="list">
      <div
        v-for="(b, i) in items"
        :key="i"
        class="beat-row"
        :class="alignmentByIndex[i] ? `beat-row-${alignmentByIndex[i].status}` : ''"
      >
        <div class="row-head">
          <span class="idx">{{ i + 1 }}</span>
          <span
            v-if="alignmentByIndex[i]"
            class="status-badge"
            :style="{ background: STATUS_META[alignmentByIndex[i].status].color }"
            :title="alignmentByIndex[i].note || STATUS_META[alignmentByIndex[i].status].label"
          >
            {{ STATUS_META[alignmentByIndex[i].status].icon }} {{ STATUS_META[alignmentByIndex[i].status].label }}
          </span>
          <el-input
            v-model="b.title"
            :placeholder="t('beats.titlePlaceholder')"
            maxlength="80"
            size="default"
            @change="emitChange"
            class="title-input"
          />
          <el-button text :icon="Top" :disabled="i === 0" @click="moveUp(i)" />
          <el-button
            text
            :icon="Bottom"
            :disabled="i === items.length - 1"
            @click="moveDown(i)"
          />
          <el-button text type="danger" :icon="Delete" @click="removeBeat(i)" />
        </div>
        <el-input
          v-model="b.detail"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 4 }"
          :placeholder="t('beats.detailPlaceholder')"
          maxlength="600"
          @change="emitChange"
          class="detail-input"
        />
        <div
          v-if="alignmentByIndex[i]?.note && alignmentByIndex[i].status !== 'covered'"
          class="alignment-note"
          :style="{ color: STATUS_META[alignmentByIndex[i].status].color }"
        >
          {{ alignmentByIndex[i].note }}
        </div>
        <div v-if="threads.length" class="threads-row">
          <span class="threads-label">{{ t('beats.threadsLabel') }}</span>
          <el-select
            v-model="b.thread_titles"
            multiple
            collapse-tags
            collapse-tags-tooltip
            filterable
            allow-create
            default-first-option
            :placeholder="t('beats.threadsPlaceholder')"
            class="threads-select"
            @change="emitChange"
          >
            <el-option
              v-for="thr in threads"
              :key="thr.id"
              :value="thr.title"
              :label="thr.title"
            />
          </el-select>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.beats-editor {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.header .count {
  font-size: 12px;
  color: #4e5969;
}
.header .spacer {
  flex: 1;
}
.empty {
  text-align: center;
  color: #c9cdd4;
  padding: 18px;
  background: #fafbfc;
  border: 1px dashed #e5e6eb;
  border-radius: 8px;
  font-size: 12px;
}
.list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.beat-row {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.beat-row:hover {
  border-color: #c9d2ff;
}
.row-head {
  display: flex;
  align-items: center;
  gap: 6px;
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
.title-input {
  flex: 1;
  min-width: 0;
}
.detail-input :deep(textarea) {
  font-size: 13px;
  line-height: 1.6;
}
.threads-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.threads-label {
  font-size: 12px;
  color: #86909c;
  flex-shrink: 0;
}
.threads-select {
  flex: 1;
  min-width: 0;
}
.compact .beat-row {
  padding: 6px 8px;
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
}
.alignment-note {
  font-size: 12px;
  line-height: 1.5;
  padding: 4px 8px;
  background: #fafbfc;
  border-radius: 6px;
}
.beat-row-covered {
  border-left: 3px solid #00b42a;
  padding-left: 8px;
}
.beat-row-partial {
  border-left: 3px solid #fa8c16;
  padding-left: 8px;
  background: #fff8ef;
}
.beat-row-missing {
  border-left: 3px solid #f53f3f;
  padding-left: 8px;
  background: #fff5f5;
}
</style>
