<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Setting, Download, ArrowDown, Sunny, Moon, ChatLineRound, DataLine } from '@element-plus/icons-vue'
import { useWorkspaceStore } from '../stores/workspace'
import { useCharactersStore } from '../stores/characters'
import { useWorldStore } from '../stores/world'
import { useLaddersStore } from '../stores/ladders'
import { useTasksStore } from '../stores/tasks'
import { useAIInfoStore } from '../stores/aiInfo'
import { useThemeStore } from '../stores/theme'
import AIConfigDialog from '../components/AIConfigDialog.vue'
import PromptManagerDialog from '../components/PromptManagerDialog.vue'
import WorkspaceLeftNav from '../components/WorkspaceLeftNav.vue'

const props = defineProps({ id: { type: String, required: true } })
const router = useRouter()
const store = useWorkspaceStore()
const charactersStore = useCharactersStore()
const worldStore = useWorldStore()
const laddersStore = useLaddersStore()
const tasksStore = useTasksStore()
const aiInfo = useAIInfoStore()
const theme = useThemeStore()
const { t } = useI18n()

const projectId = computed(() => Number(props.id))
const aiConfigVisible = ref(false)
const promptManagerVisible = ref(false)

const isHC = computed(() => theme.current === 'high-contrast')
const themeToggleTitle = computed(() =>
  isHC.value ? t('theme.switchToDefault') : t('theme.switchToHighContrast')
)

const aiBadgeText = computed(() => {
  if (!aiInfo.loaded) return t('aiConfig.button')
  if (!aiInfo.configured) return t('ai.notConfiguredShort')
  return aiInfo.model
})

async function load() {
  // 切工程时清空旁路 store,避免上个工程的数据串到新工程
  charactersStore.reset()
  worldStore.reset()
  laddersStore.reset()
  tasksStore.reset()
  try {
    await store.loadProject(projectId.value)
    // 进阶启用时预拉一下阶梯,方便人物编辑器和左侧导航使用
    if (store.project?.progression_enabled) {
      laddersStore.load(projectId.value).catch(() => {})
    }
  } catch (e) {
    ElMessage.error(e.message || t('workspace.loadFailed'))
    router.push('/')
  }
}

onMounted(() => {
  load()
  aiInfo.refresh()
})
watch(projectId, load)
onBeforeUnmount(() => {
  store.reset()
  charactersStore.reset()
  worldStore.reset()
  laddersStore.reset()
  tasksStore.reset()
})

function onAIConfigSaved() {
  aiInfo.refresh()
}

function onExport(kind) {
  // 直接打开下载链接,浏览器会按 Content-Disposition 保存
  const url = `/api/projects/${projectId.value}/export.${kind}`
  window.open(url, '_blank')
}
</script>

<template>
  <div class="workspace" v-loading="store.loading">
    <header class="topbar">
      <el-button text :icon="ArrowLeft" @click="router.push('/')">
        {{ t('workspace.backHome') }}
      </el-button>
      <h1 class="title">{{ store.project?.name || '...' }}</h1>
      <span class="spacer" />

      <el-dropdown trigger="click" @command="onExport">
        <el-button :icon="Download">
          {{ t('workspace.exportMenu') }}<el-icon class="el-icon--right"><ArrowDown /></el-icon>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="json">
              <div>
                <div>{{ t('workspace.exportJson') }}</div>
                <div class="dropdown-hint">{{ t('workspace.exportJsonHint') }}</div>
              </div>
            </el-dropdown-item>
            <el-dropdown-item command="md" divided>
              <div>
                <div>{{ t('workspace.exportMd') }}</div>
                <div class="dropdown-hint">{{ t('workspace.exportMdHint') }}</div>
              </div>
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>

      <el-button :icon="ChatLineRound" @click="promptManagerVisible = true">
        {{ t('prompts.button') }}
      </el-button>

      <el-button :icon="DataLine" @click="router.push('/stats/tokens')">
        用量统计
      </el-button>

      <button
        class="ai-badge"
        :class="{ off: aiInfo.loaded && !aiInfo.configured }"
        :title="t('aiConfig.button')"
        @click="aiConfigVisible = true"
      >
        <el-icon><Setting /></el-icon>
        <span class="badge-text">{{ aiBadgeText }}</span>
      </button>

      <button
        class="theme-toggle"
        :title="themeToggleTitle"
        :aria-label="themeToggleTitle"
        @click="theme.toggle()"
      >
        <el-icon :size="14">
          <Moon v-if="isHC" />
          <Sunny v-else />
        </el-icon>
        <span>{{ isHC ? t('theme.high') : t('theme.default') }}</span>
      </button>
    </header>

    <div class="body">
      <WorkspaceLeftNav :project-id="props.id" />
      <div class="page">
        <router-view />
      </div>
    </div>

    <AIConfigDialog v-model="aiConfigVisible" @saved="onAIConfigSaved" />
    <PromptManagerDialog v-model="promptManagerVisible" />
  </div>
</template>

<style scoped>
.workspace {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
}
.topbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: #fff;
  border-bottom: 1px solid #e5e6eb;
  flex-shrink: 0;
}
.topbar .title {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
  color: #1f2329;
  max-width: 360px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.topbar .spacer {
  flex: 1;
}
.dropdown-hint {
  font-size: 11px;
  color: #86909c;
  margin-top: 2px;
}
.ai-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 14px;
  background: #ecf5ff;
  color: #4080ff;
  font-size: 12px;
  font-weight: 500;
  border: 1px solid transparent;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
  font-family: inherit;
}
.ai-badge:hover {
  background: #d9ebff;
}
.ai-badge.off {
  background: #fff7e6;
  color: #d46b08;
  border-color: #ffd591;
}
.ai-badge.off:hover {
  background: #ffeac4;
}
.badge-text {
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.body {
  flex: 1;
  display: flex;
  overflow: hidden;
}
.page {
  flex: 1;
  display: flex;
  overflow: hidden;
  min-width: 0;
}
</style>
