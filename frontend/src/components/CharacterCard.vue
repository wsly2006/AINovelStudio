<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Delete, EditPen } from '@element-plus/icons-vue'

const props = defineProps({
  character: { type: Object, required: true },
  active: { type: Boolean, default: false },
})
const emit = defineEmits(['select', 'delete'])

const { t } = useI18n()

const ROLE_KEY_MAP = {
  '主角': 'cardRoleMain',
  '配角': 'cardRoleSupport',
  '反派': 'cardRoleVillain',
  '路人': 'cardRoleMinor',
}

const ROLE_TYPE = {
  '主角': 'primary',
  '反派': 'danger',
  '配角': 'success',
  '路人': 'info',
}

const roleLabel = computed(() => {
  const r = props.character.role
  if (!r) return ''
  const key = ROLE_KEY_MAP[r]
  return key ? t(`characters.${key}`) : r
})

const roleType = computed(() => ROLE_TYPE[props.character.role] || 'info')

const initial = computed(() => props.character.name?.charAt(0) || '?')

const themeColor = computed(() => {
  // 用 name 哈希一个稳定颜色
  if (props.character.avatar_color) return props.character.avatar_color
  const palette = ['#5b8def', '#7c3aed', '#ec4899', '#f59e0b', '#10b981', '#06b6d4', '#ef4444', '#6b7280']
  let hash = 0
  for (const ch of props.character.name || '?') hash = (hash * 31 + ch.charCodeAt(0)) & 0xfffffff
  return palette[hash % palette.length]
})

const aliasesText = computed(() => (props.character.aliases || []).join('、'))

function onDelete(e) {
  e.stopPropagation()
  emit('delete', props.character)
}
</script>

<template>
  <div class="char-card" :class="{ active }" @click="emit('select', character)">
    <div class="avatar" :style="{ background: themeColor }">{{ initial }}</div>
    <div class="info">
      <div class="row1">
        <span class="name">{{ character.name }}</span>
        <el-tag v-if="roleLabel" :type="roleType" size="small" effect="plain">
          {{ roleLabel }}
        </el-tag>
      </div>
      <div v-if="aliasesText" class="aliases">{{ aliasesText }}</div>
      <div class="profile">{{ character.profile || character.personality || '—' }}</div>
    </div>
    <button class="del-btn" :title="t('common.delete')" @click="onDelete">
      <el-icon><Delete /></el-icon>
    </button>
  </div>
</template>

<style scoped>
.char-card {
  display: flex;
  gap: 12px;
  padding: 12px;
  background: #fff;
  border-radius: 10px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: border-color 0.1s, box-shadow 0.1s;
  position: relative;
}
.char-card:hover {
  border-color: #c9d2ff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}
.char-card:hover .del-btn {
  opacity: 1;
}
.char-card.active {
  border-color: #4080ff;
  background: #f5f8ff;
}
.avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 18px;
  font-weight: 600;
}
.info {
  flex: 1;
  min-width: 0;
}
.row1 {
  display: flex;
  align-items: center;
  gap: 8px;
}
.name {
  font-size: 14px;
  font-weight: 600;
  color: #1f2329;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.aliases {
  font-size: 12px;
  color: #86909c;
  margin-top: 2px;
}
.profile {
  font-size: 12px;
  color: #4e5969;
  margin-top: 4px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.5;
}
.del-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  border: none;
  background: rgba(0, 0, 0, 0.04);
  color: #86909c;
  width: 24px;
  height: 24px;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.15s, background 0.15s, color 0.15s;
}
.del-btn:hover {
  background: #ffeded;
  color: #f56c6c;
}
</style>
