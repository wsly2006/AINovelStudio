<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Setting, Download, ArrowDown, Sunny, Moon, ChatLineRound, DataLine, Tools, Edit } from '@element-plus/icons-vue'
import { useWorkspaceStore } from '../stores/workspace'
import { useCharactersStore } from '../stores/characters'
import { useWorldStore } from '../stores/world'
import { useLaddersStore } from '../stores/ladders'
import { useTasksStore } from '../stores/tasks'
import { useAIInfoStore } from '../stores/aiInfo'
import { useThemeStore } from '../stores/theme'
import AIConfigDialog from '../components/AIConfigDialog.vue'
import PromptManagerDialog from '../components/PromptManagerDialog.vue'
import ProjectEditDialog from '../components/ProjectEditDialog.vue'
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
const projectEditVisible = ref(false)

// 总纲提醒小横幅:工程没填 synopsis 时露一次,用户点过「不再提示」就 localStorage 标记
const synopsisDismissed = ref(false)
const showSynopsisBanner = computed(
  () =>
    !synopsisDismissed.value
    && store.project
    && !(store.project.synopsis && store.project.synopsis.trim())
)
function dismissBanner() {
  synopsisDismissed.value = true
  try {
    localStorage.setItem(`synopsisBannerDismissed:${projectId.value}`, '1')
  } catch {
    /* localStorage 不可用就只在本会话内隐藏 */
  }
}
function openSynopsisFromBanner() {
  projectEditVisible.value = true
  // 不持久化,只是关掉这次显示;用户填了 synopsis 后下次刷新自动消失
  synopsisDismissed.value = true
}

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
    // 切工程时检查这个工程是否已经被「不再提示」过
    try {
      synopsisDismissed.value =
        localStorage.getItem(`synopsisBannerDismissed:${projectId.value}`) === '1'
    } catch {
      synopsisDismissed.value = false
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

function onProjectSaved(updated) {
  // 直接把后端返回的最新对象写回 store,避免再发一次 GET
  if (updated && store.project) {
    store.project = { ...store.project, ...updated }
  }
}

function onExport(kind) {
  // 直接打开下载链接,浏览器会按 Content-Disposition 保存
  const url = `/api/projects/${projectId.value}/export.${kind}`
  window.open(url, '_blank')
}

// 系统设置下拉菜单:把模型/提示词/用量统计三个入口聚合,顶栏更干净
function onSettings(cmd) {
  if (cmd === 'ai') aiConfigVisible.value = true
  else if (cmd === 'prompts') promptManagerVisible.value = true
  else if (cmd === 'stats') router.push('/stats/tokens')
}
</script>

<template>
  <div class="workspace" v-loading="store.loading">
    <header class="topbar">
      <el-button text :icon="ArrowLeft" @click="router.push('/')">
        {{ t('workspace.backHome') }}
      </el-button>
      <h1 class="title">{{ store.project?.name || '...' }}</h1>
      <button
        v-if="store.project"
        class="title-edit"
        :title="t('projectEdit.title')"
        :aria-label="t('projectEdit.title')"
        @click="projectEditVisible = true"
      >
        <el-icon :size="16"><Edit /></el-icon>
      </button>
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

      <el-dropdown trigger="click" @command="onSettings">
        <el-button :icon="Tools">
          系统设置<el-icon class="el-icon--right"><ArrowDown /></el-icon>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="ai" :icon="Setting">模型设置</el-dropdown-item>
            <el-dropdown-item command="prompts" :icon="ChatLineRound">提示词管理</el-dropdown-item>
            <el-dropdown-item command="stats" :icon="DataLine" divided>用量统计</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>

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
        <div v-if="showSynopsisBanner" class="synopsis-banner">
          <span class="banner-text">{{ t('synopsisBanner.text') }}</span>
          <el-button text type="primary" size="small" @click="openSynopsisFromBanner">
            {{ t('synopsisBanner.actionFill') }}
          </el-button>
          <el-button text size="small" @click="dismissBanner">
            {{ t('synopsisBanner.actionDismiss') }}
          </el-button>
        </div>
        <router-view />
      </div>
    </div>

    <AIConfigDialog v-model="aiConfigVisible" @saved="onAIConfigSaved" />
    <PromptManagerDialog v-model="promptManagerVisible" />
    <ProjectEditDialog
      v-model="projectEditVisible"
      :project="store.project"
      @saved="onProjectSaved"
    />
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
.title-edit {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  border: 1px solid #d9ebff;
  background: #ecf5ff;
  color: #4080ff;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, border-color 0.15s, transform 0.1s;
}
.title-edit:hover {
  background: #4080ff;
  border-color: #4080ff;
  color: #fff;
  transform: scale(1.05);
}
.title-edit:active {
  transform: scale(0.96);
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
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}
.synopsis-banner {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  background: #fff7e6;
  border-bottom: 1px solid #ffd591;
  font-size: 12px;
  color: #d46b08;
}
.banner-text {
  flex: 1;
}
</style>
