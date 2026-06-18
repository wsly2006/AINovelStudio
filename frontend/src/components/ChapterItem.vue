<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Document } from '@element-plus/icons-vue'
import { formatChapterFullTitle } from '../composables/chapterTitle'

const props = defineProps({
  chapter: { type: Object, required: true },
  active: { type: Boolean, default: false },
})
const emit = defineEmits(['select', 'rename', 'delete', 'edit'])

const { t } = useI18n()

const fullTitle = computed(() => formatChapterFullTitle(props.chapter, t))

const wordCountText = computed(() => {
  const n = props.chapter.word_count || 0
  if (n < 1000) return t('workspace.wordCount', { n })
  return t('projectCard.wordCountWan', { n: (n / 10000).toFixed(1) })
})

const statusText = computed(() => {
  const map = {
    draft: t('workspace.statusDraft'),
    writing: t('workspace.statusWriting'),
    done: t('workspace.statusDone'),
  }
  return map[props.chapter.status] || ''
})

const statusType = computed(() => {
  return { draft: 'info', writing: 'warning', done: 'success' }[props.chapter.status] || 'info'
})

function onCommand(cmd) {
  if (cmd === 'rename') emit('rename', props.chapter)
  else if (cmd === 'delete') emit('delete', props.chapter)
}
</script>

<template>
  <div
    class="chapter-item"
    :class="{ active }"
    @click="emit('select', chapter)"
    @dblclick="emit('edit', chapter)"
  >
    <div class="row1">
      <el-icon class="ico"><Document /></el-icon>
      <span class="title">{{ fullTitle }}</span>
      <el-dropdown trigger="click" @command="onCommand" @click.stop>
        <span class="more" @click.stop>⋯</span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="rename">{{ t('workspace.rename') }}</el-dropdown-item>
            <el-dropdown-item command="delete" divided>
              <span style="color: #f56c6c">{{ t('common.delete') }}</span>
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
    <div class="row2">
      <el-tag :type="statusType" size="small" effect="plain">{{ statusText }}</el-tag>
      <span class="words">{{ wordCountText }}</span>
    </div>
  </div>
</template>

<style scoped>
.chapter-item {
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  transition: background 0.1s;
  user-select: none;
}
.chapter-item:hover {
  background: #f2f3f5;
}
.chapter-item.active {
  background: #e8f0ff;
}
.chapter-item.active .title {
  color: #4080ff;
  font-weight: 600;
}
.row1 {
  display: flex;
  align-items: center;
  gap: 6px;
}
.row1 .ico {
  color: #86909c;
  flex-shrink: 0;
}
.title {
  flex: 1;
  font-size: 13px;
  color: #1f2329;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.more {
  color: #86909c;
  cursor: pointer;
  padding: 0 4px;
  font-size: 16px;
  line-height: 1;
}
.more:hover {
  color: #1f2329;
}
.row2 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
  padding-left: 22px;
}
.words {
  font-size: 12px;
  color: #86909c;
}
</style>
