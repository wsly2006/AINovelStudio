<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Document } from '@element-plus/icons-vue'
import { formatChapterFullTitle } from '../composables/chapterTitle'

const props = defineProps({
  chapter: { type: Object, required: true },
  active: { type: Boolean, default: false },
  // 'content' = 正文 tab(默认),显示字数 / 评分 / 文风徽章
  // 'outline' = 大纲 tab,改显节拍数 / 梗概一行预览
  mode: { type: String, default: 'content' },
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
    outlined: t('workspace.statusOutlined'),
    writing: t('workspace.statusWriting'),
    done: t('workspace.statusDone'),
  }
  return map[props.chapter.status] || ''
})

const statusType = computed(() => {
  return {
    draft: 'info',
    outlined: 'primary',
    writing: 'warning',
    done: 'success',
  }[props.chapter.status] || 'info'
})

// 评分徽章:有分才显示,颜色按分段
const score = computed(() => props.chapter.latest_overall_score ?? null)
const scoreColor = computed(() => {
  const n = score.value
  if (n == null) return ''
  if (n >= 9) return '#00b42a'
  if (n >= 7) return '#4080ff'
  if (n >= 5) return '#ff7d00'
  return '#f53f3f'
})

// 文风徽章:0 处显示绿色对勾,>0 显示红色数字,从未检查过(null)不显示
const styleCount = computed(() => props.chapter.latest_style_issue_count ?? null)
const styleColor = computed(() => {
  const n = styleCount.value
  if (n == null) return ''
  return n === 0 ? '#00b42a' : '#f53f3f'
})

// 大纲 tab 用:节拍数(列表 schema 没带 beats 数组,从 latest_beats_count 字段读;
// 后端目前没有这个字段,先留 null,WorkspaceOutline 选中时通过 detail 接口拿)
const beatsCount = computed(() => props.chapter.beats_count ?? null)
const summaryPreview = computed(() => {
  const s = (props.chapter.summary || '').trim()
  return s ? s.replace(/\s+/g, ' ').slice(0, 60) : ''
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

      <template v-if="mode === 'outline'">
        <span v-if="beatsCount != null" class="beats-tag" :title="t('outline.beatsCountTitle')">
          {{ t('outline.beatsCountTag', { n: beatsCount }) }}
        </span>
      </template>
      <template v-else>
        <span class="words">{{ wordCountText }}</span>
        <span
          v-if="styleCount != null"
          class="style-badge"
          :style="{ background: styleColor }"
          :title="
            styleCount === 0
              ? 'AI 文风检查:无明显 AI 味段落'
              : `AI 文风检查:发现 ${styleCount} 处需重写`
          "
        >
          <span v-if="styleCount === 0">✓</span>
          <span v-else>AI×{{ styleCount }}</span>
        </span>
        <span
          v-if="score != null"
          class="score-badge"
          :style="{ background: scoreColor }"
          :title="`AI 综合评分:${score}/10`"
        >
          {{ score }}
        </span>
      </template>
    </div>
    <div v-if="mode === 'outline' && summaryPreview" class="summary-preview">
      {{ summaryPreview }}
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
.score-badge {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: #4080ff;
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}
.style-badge {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  height: 18px;
  padding: 0 6px;
  border-radius: 9px;
  color: #fff;
  font-size: 10px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}
/* 文风 + 评分两个徽章并存时,只让前者占用 margin-left:auto,
   后者紧贴文风徽章右侧 */
.style-badge + .score-badge {
  margin-left: 4px;
}
.beats-tag {
  margin-left: auto;
  font-size: 11px;
  color: #4080ff;
  background: #ecf5ff;
  padding: 2px 8px;
  border-radius: 9px;
  font-variant-numeric: tabular-nums;
}
.summary-preview {
  margin-top: 6px;
  padding-left: 22px;
  font-size: 12px;
  color: #86909c;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
