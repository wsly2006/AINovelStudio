<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Upload, EditPen, DataLine } from '@element-plus/icons-vue'
import { useProjectsStore } from '../stores/projects'
import ProjectCard from '../components/ProjectCard.vue'
import ProjectCreateDialog from '../components/ProjectCreateDialog.vue'
import { streamProgressSSE } from '../api/sse'

const router = useRouter()
const store = useProjectsStore()
const { t } = useI18n()
const dialogVisible = ref(false)
const fileInput = ref(null)
const importing = ref(false)

// AI 生成进度面板状态。任务跑在服务器后台,这里只订阅事件流。
const aiGenerating = ref(false)
const aiProgress = ref({ index: 0, total: 0, title: '', name: '' })
const aiTaskId = ref(null)
const aiCreatedProjectId = ref(null)
const aiAbort = ref(null)
const aiAutoNavigate = ref(true) // done 时是否自动跳转;断线重连时设 false

const TASK_STORAGE_KEY = 'ai-novel.ai-task'

function saveTaskRef(taskId, projectId, name) {
  try {
    localStorage.setItem(
      TASK_STORAGE_KEY,
      JSON.stringify({ taskId, projectId, name }),
    )
  } catch {
    // 隐私模式禁用 storage 时静默忽略,功能仍可在当前会话内用
  }
}

function clearTaskRef() {
  aiTaskId.value = null
  try {
    localStorage.removeItem(TASK_STORAGE_KEY)
  } catch {}
}

function loadTaskRef() {
  try {
    const raw = localStorage.getItem(TASK_STORAGE_KEY)
    if (!raw) return null
    return JSON.parse(raw)
  } catch {
    return null
  }
}

onMounted(async () => {
  await store.refresh()
  // 检查是否有未完成的 AI 任务,有就接着订阅
  const saved = loadTaskRef()
  if (saved?.taskId) {
    aiAutoNavigate.value = false  // 用户主动刷新过页面,不再自动跳转
    aiCreatedProjectId.value = saved.projectId
    aiProgress.value = { index: 0, total: 0, title: '', name: saved.name || '' }
    subscribe(saved.taskId)
  }
})

onBeforeUnmount(() => {
  if (aiAbort.value) aiAbort.value.abort()
})

function openProject(project) {
  router.push(`/projects/${project.id}/workspace`)
}

async function onImported(result) {
  ElMessage.success(
    t('home.importSuccess', { name: result.name, chapters: result.chapter_count, characters: 0 })
  )
  await store.refresh()
  router.push(`/projects/${result.id}/workspace`)
}

function openCreateDialog() {
  if (aiGenerating.value) {
    ElMessage.info(t('home.aiBusyHint'))
    return
  }
  dialogVisible.value = true
}

// onAICreate: 提交 AI 生成请求 → 拿到 task_id → 订阅 SSE
async function onAICreate(payload) {
  aiGenerating.value = true
  aiAutoNavigate.value = true
  aiProgress.value = { index: 0, total: payload.chapter_count, title: '', name: payload.project.name }
  aiCreatedProjectId.value = null

  let resp
  try {
    resp = await fetch('/api/projects/ai-create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  } catch (e) {
    aiGenerating.value = false
    ElMessage.error(`${t('home.aiCreateFailed')}: ${e.message}`)
    return
  }
  if (!resp.ok) {
    aiGenerating.value = false
    let detail = `HTTP ${resp.status}`
    try {
      const data = await resp.json()
      if (data?.detail) detail = data.detail
    } catch {}
    ElMessage.error(`${t('home.aiCreateFailed')}: ${detail}`)
    return
  }
  const { task_id, project_id } = await resp.json()
  aiTaskId.value = task_id
  aiCreatedProjectId.value = project_id
  saveTaskRef(task_id, project_id, payload.project.name)
  subscribe(task_id)
}

function subscribe(taskId) {
  aiAbort.value = new AbortController()
  aiGenerating.value = true
  // 注意:不要 await,subscribe 内部循环到流结束才 resolve;这里只触发它
  streamProgressSSE(
    `/api/ai-tasks/${taskId}/stream`,
    null,
    {
      method: 'GET',
      signal: aiAbort.value.signal,
      onStart: ({ project_id, total, name }) => {
        if (project_id) aiCreatedProjectId.value = project_id
        aiProgress.value = {
          ...aiProgress.value,
          total: total || aiProgress.value.total,
          name: name || aiProgress.value.name,
        }
      },
      onProgress: ({ index, total, title }) => {
        aiProgress.value = { ...aiProgress.value, index, total, title: title || '' }
      },
      onResult: ({ project_id, chapter_count }) => {
        if (project_id) aiCreatedProjectId.value = project_id
        aiProgress.value = { ...aiProgress.value, index: chapter_count || aiProgress.value.index }
      },
      onDone: async () => {
        aiGenerating.value = false
        clearTaskRef()
        await store.refresh()
        ElMessage.success(t('home.aiCreateDone', { n: aiProgress.value.index || 0 }))
        if (aiAutoNavigate.value && aiCreatedProjectId.value) {
          router.push(`/projects/${aiCreatedProjectId.value}/workspace`)
        }
      },
      onCancelled: async () => {
        aiGenerating.value = false
        clearTaskRef()
        await store.refresh()
        ElMessage.warning(t('home.aiCreateCancelled'))
      },
      onError: (msg, statusCode) => {
        aiGenerating.value = false
        if (statusCode === 404) {
          // 任务已经过期或服务器重启丢失;清掉本地引用
          clearTaskRef()
          ElMessage.warning(t('home.aiTaskGone'))
        } else {
          // 不清 storage:错误可能是网络抖动,刷新还能看到。任务已结束的 error 由
          // 服务器的 finished_at 触发 reaper 清理,这里不强删
          ElMessage.error(`${t('home.aiCreateFailed')}: ${msg}`)
        }
      },
    },
  )
}

async function onCancelAI() {
  if (!aiTaskId.value) {
    if (aiAbort.value) aiAbort.value.abort()
    aiGenerating.value = false
    return
  }
  try {
    await fetch(`/api/ai-tasks/${aiTaskId.value}`, { method: 'DELETE' })
  } catch {
    // 取消本身失败也不阻塞 UI,服务器端的取消事件最终会通过 SSE 流过来
  }
}

async function onDelete(project) {
  try {
    await ElMessageBox.confirm(
      t('homeMessages.deleteConfirm', { name: project.name }),
      t('homeMessages.deleteTitle'),
      {
        type: 'warning',
        confirmButtonText: t('common.delete'),
        cancelButtonText: t('common.cancel'),
      }
    )
  } catch {
    return
  }
  try {
    await store.remove(project.id)
    ElMessage.success(t('homeMessages.deleteSuccess'))
  } catch (e) {
    ElMessage.error(e.message || t('homeMessages.deleteFailed'))
  }
}

function triggerImport() {
  fileInput.value?.click()
}

async function onFilePicked(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file) return
  importing.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    const resp = await fetch('/api/projects/import', { method: 'POST', body: fd })
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}))
      throw new Error(data.detail || `HTTP ${resp.status}`)
    }
    const data = await resp.json()
    ElMessage.success(
      t('home.importSuccess', {
        name: data.name,
        chapters: data.chapter_count,
        characters: data.character_count,
      })
    )
    await store.refresh()
  } catch (err) {
    ElMessage.error(`${t('home.importFailed')}: ${err.message}`)
  } finally {
    importing.value = false
  }
}
</script>

<template>
  <div class="home">
    <div class="topbar-utils">
      <el-button text :icon="DataLine" @click="router.push('/stats/tokens')">
        用量统计
      </el-button>
    </div>
    <section class="hero">
      <h1 class="hero-title">{{ t('app.name') }}</h1>
      <p class="hero-tagline">{{ t('app.tagline') }}</p>

      <div class="hero-actions">
        <button class="cta-primary" :disabled="aiGenerating" @click="openCreateDialog">
          <el-icon class="cta-icon"><EditPen /></el-icon>
          <span class="cta-main">{{ t('home.heroCreate') }}</span>
          <span class="cta-sub">{{ t('home.newProjectHint') }}</span>
        </button>
        <button class="cta-secondary" :disabled="importing" @click="triggerImport">
          <el-icon class="cta-icon"><Upload /></el-icon>
          <span class="cta-main">{{ t('home.heroImport') }}</span>
          <span class="cta-sub">{{ t('home.importHint') }}</span>
        </button>
      </div>

      <!-- AI 生成进度,只在生成期间出现 -->
      <div v-if="aiGenerating || aiProgress.index > 0" class="ai-progress">
        <div class="ai-progress-head">
          <span class="ai-progress-title">
            {{ t('home.aiProgressTitle', { name: aiProgress.name }) }}
          </span>
          <el-button
            v-if="aiGenerating"
            text
            type="danger"
            size="small"
            @click="onCancelAI"
          >
            {{ t('common.cancel') }}
          </el-button>
        </div>
        <el-progress
          :percentage="aiProgress.total
            ? Math.min(100, Math.round((aiProgress.index / aiProgress.total) * 100))
            : 0"
          :stroke-width="8"
        />
        <div class="ai-progress-line">
          {{ aiProgress.index }}/{{ aiProgress.total }}
          <span v-if="aiProgress.title" class="ai-progress-chap">— {{ aiProgress.title }}</span>
        </div>
      </div>
    </section>

    <main class="content" v-loading="store.loading">
      <div v-if="store.items.length > 0" class="recent">
        <div class="recent-head">
          <h2 class="recent-title">{{ t('home.sectionRecent') }}</h2>
          <el-button text :icon="Plus" @click="openCreateDialog">
            {{ t('home.newProject') }}
          </el-button>
        </div>
        <div class="grid">
          <ProjectCard
            v-for="p in store.items"
            :key="p.id"
            :project="p"
            @open="openProject"
            @delete="onDelete"
          />
        </div>
      </div>
    </main>

    <ProjectCreateDialog
      v-model="dialogVisible"
      @imported="onImported"
      @ai-create="onAICreate"
    />

    <input
      ref="fileInput"
      type="file"
      accept=".json,application/json"
      style="display: none"
      @change="onFilePicked"
    />
  </div>
</template>

<style scoped>
.home {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, #f5f7fb 0%, #ffffff 320px);
}
.topbar-utils {
  display: flex;
  justify-content: flex-end;
  padding: 10px 20px 0;
}

.hero {
  padding: 72px 32px 48px;
  text-align: center;
  max-width: 960px;
  width: 100%;
  margin: 0 auto;
}
.hero-title {
  margin: 0 0 12px;
  font-size: 44px;
  font-weight: 700;
  letter-spacing: -0.5px;
  background: linear-gradient(90deg, #1f2329 0%, #5b8def 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.hero-tagline {
  margin: 0 0 36px;
  font-size: 16px;
  color: #5b6471;
}
.hero-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  max-width: 720px;
  margin: 0 auto;
}
.cta-primary,
.cta-secondary {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  padding: 22px 24px;
  border-radius: 12px;
  border: 1px solid transparent;
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  transition: transform 0.12s, box-shadow 0.12s, border-color 0.12s;
}
.cta-primary {
  background: linear-gradient(135deg, #5b8def 0%, #7c3aed 100%);
  color: #fff;
  box-shadow: 0 8px 24px rgba(91, 141, 239, 0.28);
}
.cta-primary:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 12px 28px rgba(91, 141, 239, 0.36);
}
.cta-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.cta-secondary {
  background: #fff;
  color: #1f2329;
  border-color: #e5e6eb;
}
.cta-secondary:hover:not(:disabled) {
  transform: translateY(-2px);
  border-color: #5b8def;
  box-shadow: 0 8px 20px rgba(31, 35, 41, 0.08);
}
.cta-secondary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.cta-icon {
  font-size: 22px;
}
.cta-main {
  font-size: 18px;
  font-weight: 600;
}
.cta-sub {
  font-size: 13px;
  opacity: 0.85;
}

.ai-progress {
  margin: 24px auto 0;
  max-width: 720px;
  background: #fff;
  border: 1px solid #fbcfe8;
  border-radius: 12px;
  padding: 14px 18px;
  text-align: left;
  box-shadow: 0 4px 12px rgba(236, 72, 153, 0.08);
}
.ai-progress-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.ai-progress-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2329;
}
.ai-progress-line {
  margin-top: 8px;
  font-size: 12px;
  color: #5b6471;
}
.ai-progress-chap {
  margin-left: 6px;
  color: #1f2329;
}

.content {
  flex: 1;
  padding: 16px 32px 48px;
  max-width: 1280px;
  width: 100%;
  margin: 0 auto;
}
.recent {
  background: #f5f7fb;
  border: 1px solid #e8eaef;
  border-radius: 16px;
  padding: 20px 24px 28px;
}
.recent-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 0 0 16px;
}
.recent-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #1f2329;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 20px;
}

@media (max-width: 640px) {
  .hero {
    padding: 48px 20px 32px;
  }
  .hero-title {
    font-size: 32px;
  }
  .hero-actions {
    grid-template-columns: 1fr;
  }
  .content {
    padding: 8px 20px 32px;
  }
}
</style>
