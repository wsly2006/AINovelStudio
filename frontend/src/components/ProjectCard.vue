<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Delete, Document, EditPen } from '@element-plus/icons-vue'

const props = defineProps({
  project: { type: Object, required: true },
})
const emit = defineEmits(['open', 'delete'])
const { t, locale } = useI18n()

const themeColor = computed(() => props.project.cover_color || '#5b8def')

const genreLabel = computed(() => {
  const g = props.project.genre
  if (!g) return ''
  // genre 字段存的是 key,显示走 i18n;旧数据若是中文显示原值
  const key = `genre.${g}`
  const translated = t(key)
  return translated === key ? g : translated
})

const lastEditedText = computed(() => {
  const tm = props.project.last_edited_at
  if (!tm) return ''
  const date = new Date(tm)
  const diffMs = Date.now() - date.getTime()
  const min = Math.floor(diffMs / 60000)
  if (min < 1) return t('projectCard.timeJustNow')
  if (min < 60) return t('projectCard.timeMinutes', { n: min })
  const hour = Math.floor(min / 60)
  if (hour < 24) return t('projectCard.timeHours', { n: hour })
  const day = Math.floor(hour / 24)
  if (day < 30) return t('projectCard.timeDays', { n: day })
  return date.toLocaleDateString(locale.value)
})

const wordCountText = computed(() => {
  const n = props.project.word_count || 0
  if (n < 1000) return t('projectCard.wordCount', { n })
  return t('projectCard.wordCountWan', { n: (n / 10000).toFixed(1) })
})

const chapterCountText = computed(() =>
  t('projectCard.chapterCount', { n: props.project.chapter_count })
)

function onDelete(e) {
  e.stopPropagation()
  emit('delete', props.project)
}
</script>

<template>
  <div class="project-card" @click="emit('open', project)">
    <div class="cover" :style="{ background: themeColor }">
      <span class="initial">{{ project.name.charAt(0) }}</span>
      <button class="delete-btn" @click="onDelete" :title="t('projectCard.deleteTip')">
        <el-icon><Delete /></el-icon>
      </button>
    </div>
    <div class="body">
      <div class="title">{{ project.name }}</div>
      <div class="genre">
        <el-tag v-if="genreLabel" size="small" type="info">{{ genreLabel }}</el-tag>
      </div>
      <div class="desc">{{ project.description || t('projectCard.noDescription') }}</div>
      <div class="meta">
        <span><el-icon><Document /></el-icon> {{ chapterCountText }}</span>
        <span><el-icon><EditPen /></el-icon> {{ wordCountText }}</span>
        <span class="time">{{ lastEditedText }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.project-card {
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
  cursor: pointer;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  transition: transform 0.15s, box-shadow 0.15s;
  display: flex;
  flex-direction: column;
}
.project-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.1);
}
.project-card:hover .delete-btn {
  opacity: 1;
}
.cover {
  height: 120px;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}
.initial {
  color: #fff;
  font-size: 48px;
  font-weight: 600;
  opacity: 0.85;
}
.delete-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  border: none;
  background: rgba(0, 0, 0, 0.4);
  color: #fff;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.15s, background 0.15s;
}
.delete-btn:hover {
  background: #f56c6c;
}
.body {
  padding: 14px 16px 16px;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.title {
  font-size: 16px;
  font-weight: 600;
  color: #1f2329;
}
.genre {
  min-height: 22px;
}
.desc {
  font-size: 13px;
  color: #86909c;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  flex: 1;
}
.meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #86909c;
  align-items: center;
  margin-top: 4px;
}
.meta .el-icon {
  vertical-align: middle;
  margin-right: 2px;
}
.meta .time {
  margin-left: auto;
}
</style>
