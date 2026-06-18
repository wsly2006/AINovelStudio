<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Document, User, Share, Reading, Compass, TrendCharts, Flag, Box, Connection } from '@element-plus/icons-vue'
import { useWorkspaceStore } from '../stores/workspace'

const props = defineProps({
  projectId: { type: [Number, String], required: true },
})

const router = useRouter()
const route = useRoute()
const { t } = useI18n()
const workspace = useWorkspaceStore()

const NAV_ITEMS = computed(() => {
  const base = [
    { name: 'workspace-content', labelKey: 'workspaceTab.content', icon: Document },
    { name: 'workspace-characters', labelKey: 'workspaceTab.characters', icon: User },
    { name: 'workspace-items', labelKey: 'workspaceTab.items', icon: Box },
    { name: 'workspace-relations', labelKey: 'workspaceTab.relations', icon: Share },
    { name: 'workspace-threads', labelKey: 'workspaceTab.threads', icon: Connection },
    { name: 'workspace-plot', labelKey: 'workspaceTab.plot', icon: Reading },
    { name: 'workspace-world', labelKey: 'workspaceTab.world', icon: Compass },
    { name: 'workspace-tasks', labelKey: 'workspaceTab.tasks', icon: Flag },
  ]
  if (workspace.project?.progression_enabled) {
    base.push({
      name: 'workspace-progression',
      labelKey: 'workspaceTab.progression',
      icon: TrendCharts,
    })
  }
  return base
})

const activeName = computed(() => route.name)

function go(name) {
  router.push({ name, params: { id: String(props.projectId) } })
}
</script>

<template>
  <nav class="left-nav">
    <button
      v-for="item in NAV_ITEMS"
      :key="item.name"
      class="nav-item"
      :class="{ active: activeName === item.name }"
      :title="t(item.labelKey)"
      @click="go(item.name)"
    >
      <el-icon :size="18"><component :is="item.icon" /></el-icon>
      <span class="label">{{ t(item.labelKey) }}</span>
    </button>
  </nav>
</template>

<style scoped>
.left-nav {
  width: 72px;
  flex-shrink: 0;
  background: #fff;
  border-right: 1px solid #e5e6eb;
  display: flex;
  flex-direction: column;
  padding: 8px 6px;
  gap: 4px;
  /* 让选中的"书签"可以越过右边界,贴到内容区上 */
  overflow: visible;
  position: relative;
  z-index: 1;
}
.nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 4px;
  border: none;
  background: transparent;
  border-radius: 8px;
  cursor: pointer;
  color: #4e5969;
  font-family: inherit;
  position: relative;
  transition: background 0.15s, color 0.15s, margin-right 0.18s, padding-right 0.18s;
}
.nav-item:hover:not(.active) {
  background: #f2f3f5;
}
.nav-item.active {
  background: #ecf5ff;
  color: #4080ff;
  /* 书签效果:右侧切平,负 margin 越过 nav 右边界覆盖在内容区之上 */
  border-radius: 10px 0 0 10px;
  margin-right: -7px;
  padding-right: 11px;
  z-index: 2;
  box-shadow:
    inset 3px 0 0 0 #4080ff,
    -2px 0 6px -3px rgba(64, 128, 255, 0.25);
}
.nav-item.active::after {
  /* 顶/底两个小圆角凹槽,让书签"挂"在分隔线上的过渡更自然 */
  content: '';
  position: absolute;
  right: -7px;
  top: 0;
  bottom: 0;
  width: 7px;
  background: #ecf5ff;
  pointer-events: none;
}
.nav-item.active .label {
  font-weight: 600;
}
.label {
  font-size: 12px;
  letter-spacing: 0.5px;
}
</style>
