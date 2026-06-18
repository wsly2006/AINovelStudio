<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useWorkspaceStore } from '../stores/workspace'
import { useCharactersStore } from '../stores/characters'
import { useWorldStore } from '../stores/world'
import { useItemsStore } from '../stores/items'
import ChapterList from '../components/ChapterList.vue'
import ChapterEditor from '../components/ChapterEditor.vue'
import ChapterCreateDialog from '../components/ChapterCreateDialog.vue'
import AIToolbar from '../components/AIToolbar.vue'
import AIGenerateDrawer from '../components/AIGenerateDrawer.vue'
import ChapterScoreDialog from '../components/ChapterScoreDialog.vue'
import { formatChapterFullTitle } from '../composables/chapterTitle'
import { indexChapter } from '../composables/indexChapter'
import { chapterVersionsApi } from '../api/chapterVersions'

const route = useRoute()
const store = useWorkspaceStore()
const charactersStore = useCharactersStore()
const worldStore = useWorldStore()
const itemsStore = useItemsStore()
const { t } = useI18n()

const editorRef = ref(null)
const drawerVisible = ref(false)
const drawerMode = ref('generate')
const drawerSelection = ref('')
const drawerCursorText = ref('')

const dialogVisible = ref(false)
const dialogMode = ref('create') // 'create' | 'rename' | 'edit'
const dialogOrderIndex = ref(1)
const dialogTitle = ref('')
const dialogSummary = ref('')
const dialogTargetId = ref(null)

// AI 评分对话框
const scoreVisible = ref(false)

const selectedChapter = computed(
  () => store.chapters.find((c) => c.id === store.selectedId) || null
)

const selectedChapterFullTitle = computed(() =>
  selectedChapter.value ? formatChapterFullTitle(selectedChapter.value, t) : ''
)

// 章节概述本地缓存:在编辑器顶部直接编辑,失焦自动落库
const summaryInputEl = ref(null)
const summaryDraft = ref('')
watch(
  () => selectedChapter.value?.id,
  () => {
    summaryDraft.value = selectedChapter.value?.summary || ''
  },
  { immediate: true }
)
watch(
  () => selectedChapter.value?.summary,
  (val) => {
    // 外部(如 AI 生成梗概)更新了 summary 时同步到草稿,避免覆盖本地正在输入的修改
    const ta = summaryInputEl.value?.$el?.querySelector?.('textarea')
    if (document.activeElement !== ta) {
      summaryDraft.value = val || ''
    }
  }
)

async function flushSummary() {
  const ch = selectedChapter.value
  if (!ch) return
  const next = summaryDraft.value || ''
  if ((ch.summary || '') === next) return
  try {
    await store.updateChapterMeta(ch.id, { summary: next })
  } catch (e) {
    ElMessage.error(e.message || t('workspace.updateFailed'))
  }
}

// 工程内的人物列表 / 世界观 / 物品(供 AI 注入多选用)
const projectCharacters = computed(() => charactersStore.items)
const projectWorld = computed(() => worldStore.items)
const projectItems = computed(() => itemsStore.items)

onMounted(() => {
  const pid = Number(route.params.id)
  if (charactersStore.projectId !== pid) {
    charactersStore.load(pid).catch(() => {})
  }
  if (worldStore.projectId !== pid) {
    worldStore.load(pid).catch(() => {})
  }
  if (itemsStore.projectId !== pid) {
    itemsStore.load(pid).catch(() => {})
  }
})

async function flushEditor() {
  if (editorRef.value?.flush) {
    try {
      await editorRef.value.flush()
    } catch {
      /* 保存失败不阻塞跳转 */
    }
  }
}

async function onSelect(chapter) {
  if (chapter.id === store.selectedId) return
  await flushEditor()
  await flushSummary()
  store.select(chapter.id)
}

async function onCreate() {
  await flushEditor()
  await flushSummary()
  dialogMode.value = 'create'
  dialogOrderIndex.value = store.chapters.length + 1
  dialogTitle.value = ''
  dialogSummary.value = ''
  dialogTargetId.value = null
  dialogVisible.value = true
}

async function onRename(chapter) {
  dialogMode.value = 'rename'
  dialogOrderIndex.value = chapter.order_index
  dialogTitle.value = chapter.title || ''
  dialogSummary.value = ''
  dialogTargetId.value = chapter.id
  dialogVisible.value = true
}

// 双击章节卡片:与新建对话框同款,但是预填当前内容,提交后走 update
async function onEdit(chapter) {
  await flushEditor()
  dialogMode.value = 'edit'
  dialogOrderIndex.value = chapter.order_index
  dialogTitle.value = chapter.title || ''
  dialogSummary.value = chapter.summary || ''
  dialogTargetId.value = chapter.id
  dialogVisible.value = true
}

async function onDialogSubmit(payload) {
  if (dialogMode.value === 'create') {
    try {
      await store.createChapter(payload)
      ElMessage.success(t('workspace.chapterCreated'))
    } catch (e) {
      ElMessage.error(e.message || t('workspace.createFailed'))
      throw e
    }
  } else if (dialogMode.value === 'edit') {
    const id = dialogTargetId.value
    if (!id) return
    const target = store.chapters.find((c) => c.id === id)
    if (!target) return
    const titleSame = (target.title || '') === payload.title
    const summarySame = (target.summary || '') === (payload.summary || '')
    if (titleSame && summarySame) return
    try {
      await store.updateChapterMeta(id, payload)
      ElMessage.success(t('workspace.chapterUpdated'))
    } catch (e) {
      ElMessage.error(e.message || t('workspace.updateFailed'))
      throw e
    }
  } else {
    const id = dialogTargetId.value
    if (!id) return
    const target = store.chapters.find((c) => c.id === id)
    if (!target) return
    if ((target.title || '') === payload.title) return
    try {
      await store.renameChapter(id, payload.title)
      ElMessage.success(t('workspace.chapterRenamed'))
    } catch (e) {
      ElMessage.error(e.message || t('workspace.renameFailed'))
      throw e
    }
  }
}

async function onDelete(chapter) {
  try {
    await ElMessageBox.confirm(
      t('workspace.chapterDeleteConfirm', {
        title: formatChapterFullTitle(chapter, t),
      }),
      t('workspace.chapterDeleteTitle'),
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
    await store.removeChapter(chapter.id)
    ElMessage.success(t('workspace.chapterDeleted'))
  } catch (e) {
    ElMessage.error(e.message || t('workspace.deleteFailed'))
  }
}

async function onReorder(newList) {
  try {
    await store.reorder(newList)
  } catch (e) {
    ElMessage.error(e.message || t('workspace.reorderFailed'))
  }
}

function onEditorSaved(meta) {
  store.applyContentSaved(meta.id, meta)
}

async function onAIGenerate() {
  if (!selectedChapter.value) return
  await flushEditor()
  drawerMode.value = 'generate'
  drawerVisible.value = true
}

async function onAIContinue() {
  if (!selectedChapter.value || !editorRef.value) return
  await flushEditor()
  const cursorText = editorRef.value.getCursorText() || editorRef.value.getContent() || ''
  drawerCursorText.value = cursorText.slice(-8000)
  drawerMode.value = 'continue'
  drawerVisible.value = true
}

async function onAIRewrite() {
  if (!selectedChapter.value || !editorRef.value) return
  await flushEditor()
  const sel = editorRef.value.getSelection() || ''
  if (!sel.trim()) {
    ElMessage.warning(t('ai.selectionEmpty'))
    return
  }
  drawerSelection.value = sel
  drawerMode.value = 'rewrite'
  drawerVisible.value = true
}

async function onAISummarize() {
  if (!selectedChapter.value) return
  await flushEditor()
  const id = selectedChapter.value.id
  const closeMsg = ElMessage({ type: 'info', message: t('ai.summarizing'), duration: 0 })
  try {
    const resp = await fetch(`/api/chapters/${id}/ai/summarize`, { method: 'POST' })
    closeMsg.close()
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}))
      ElMessage.error(`${t('ai.error')}: ${data.detail || resp.status}`)
      return
    }
    const data = await resp.json()
    const i = store.chapters.findIndex((c) => c.id === id)
    if (i >= 0) {
      store.chapters[i] = { ...store.chapters[i], summary: data.summary }
    }
    ElMessage.success(t('ai.summarized'))
  } catch (e) {
    closeMsg.close()
    ElMessage.error(`${t('ai.error')}: ${e.message}`)
  }
}

// 索引本章:串行调 5 个 AI 抽取接口,只覆盖当前章。
// 进度用一条常驻 ElMessage 滚动展示,最后汇总到 success。
const indexing = ref(false)
async function onIndexChapter() {
  if (!selectedChapter.value || indexing.value) return
  await flushEditor()
  await flushSummary()
  const projectId = Number(route.params.id)
  const chapterId = selectedChapter.value.id
  indexing.value = true
  const progressMsg = ElMessage({
    type: 'info',
    message: t('ai.indexingStart'),
    duration: 0,
    showClose: true,
  })
  const totals = {}
  try {
    const summary = await indexChapter(projectId, chapterId, {
      onStepStart: (key) => {
        progressMsg.message = t('ai.indexingStep', { step: t(`ai.indexStep.${key}`) })
      },
      onStepDone: (key, { extracted }) => {
        totals[key] = extracted
      },
      onStepError: (key, msg) => {
        // 单步失败只警告不中断,继续抽下一类
        ElMessage.warning(`${t(`ai.indexStep.${key}`)}: ${msg}`)
      },
    })
    // 抽完刷新前端 store,人物 / 世界观 / 物品页面的列表会同步更新
    await Promise.all([
      charactersStore.load(projectId).catch(() => {}),
      worldStore.load(projectId).catch(() => {}),
      itemsStore.load(projectId).catch(() => {}),
    ])
    progressMsg.close()
    const parts = []
    for (const key of ['characters', 'world', 'items', 'relations', 'plot']) {
      const n = summary[key]?.extracted
      if (typeof n === 'number') parts.push(`${t(`ai.indexStep.${key}`)} +${n}`)
    }
    ElMessage.success(
      parts.length
        ? t('ai.indexingDone', { detail: parts.join(' · ') })
        : t('ai.indexingEmpty')
    )
  } catch (e) {
    progressMsg.close()
    ElMessage.error(`${t('ai.error')}: ${e.message}`)
  } finally {
    indexing.value = false
  }
}

// AI 覆盖前先把当前内容快照一份,失败也不阻塞主流程(版本系统是兜底,不应妨碍创作)
async function snapshotBeforeAI() {
  const id = selectedChapter.value?.id
  if (!id) return
  try {
    await chapterVersionsApi.snapshotBeforeAI(id)
  } catch (e) {
    console.warn('版本快照失败,跳过:', e?.message || e)
  }
}

async function onAIScore() {
  if (!selectedChapter.value) return
  await flushEditor()
  scoreVisible.value = true
}

async function onDrawerReplace(text) {
  await snapshotBeforeAI()
  editorRef.value?.replaceAll(text)
}
async function onDrawerAppend(text) {
  await snapshotBeforeAI()
  editorRef.value?.appendToEnd(text)
}
async function onDrawerInsert(text) {
  await snapshotBeforeAI()
  editorRef.value?.insertAtCursor(text)
}
async function onDrawerAccept(text) {
  await snapshotBeforeAI()
  editorRef.value?.replaceSelection(text)
}
</script>

<template>
  <aside class="sidebar">
    <ChapterList
      :chapters="store.chapters"
      :selected-id="store.selectedId"
      @select="onSelect"
      @create="onCreate"
      @rename="onRename"
      @delete="onDelete"
      @reorder="onReorder"
      @edit="onEdit"
    />
  </aside>

  <main class="editor">
    <div v-if="!selectedChapter" class="placeholder">
      <div class="emoji">✍️</div>
      <p>{{ t('workspace.selectChapterHint') }}</p>
    </div>

    <div v-else class="editor-inner">
      <div class="header-row">
        <h2 class="chap-title">{{ selectedChapterFullTitle }}</h2>
        <AIToolbar
          :indexing="indexing"
          @generate="onAIGenerate"
          @continue="onAIContinue"
          @rewrite="onAIRewrite"
          @summarize="onAISummarize"
          @index="onIndexChapter"
          @score="onAIScore"
        />
      </div>
      <el-input
        ref="summaryInputEl"
        v-model="summaryDraft"
        type="textarea"
        :autosize="{ minRows: 2, maxRows: 5 }"
        :placeholder="t('chapterDialog.summaryPlaceholder')"
        class="chap-summary"
        resize="none"
        @blur="flushSummary"
      />
      <ChapterEditor
        ref="editorRef"
        :key="selectedChapter.id"
        :chapter-id="selectedChapter.id"
        class="editor-host"
        @saved="onEditorSaved"
      />
    </div>
  </main>

  <AIGenerateDrawer
    v-model="drawerVisible"
    :mode="drawerMode"
    :chapter-id="selectedChapter?.id || null"
    :selection="drawerSelection"
    :cursor-text="drawerCursorText"
    :characters="projectCharacters"
    :world-entities="projectWorld"
    :items="projectItems"
    :default-target-word-count="store.project?.words_per_chapter || 4000"
    @replace="onDrawerReplace"
    @append="onDrawerAppend"
    @insert="onDrawerInsert"
    @accept="onDrawerAccept"
  />

  <ChapterCreateDialog
    v-model="dialogVisible"
    :mode="dialogMode"
    :order-index="dialogOrderIndex"
    :title="dialogTitle"
    :summary="dialogSummary"
    @submit="onDialogSubmit"
  />

  <ChapterScoreDialog
    v-model="scoreVisible"
    :chapter-id="selectedChapter?.id || null"
    :chapter-title="selectedChapterFullTitle"
  />
</template>

<style scoped>
.sidebar {
  width: 280px;
  flex-shrink: 0;
  height: 100%;
}
.editor {
  flex: 1;
  overflow: hidden;
  padding: 16px 24px;
}
.placeholder {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #86909c;
}
.placeholder .emoji {
  font-size: 56px;
  margin-bottom: 12px;
  opacity: 0.6;
}
.editor-inner {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.header-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-shrink: 0;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.chap-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  align-self: center;
}
.chap-summary {
  flex-shrink: 0;
  margin-bottom: 12px;
}
.chap-summary :deep(.el-textarea__inner) {
  font-size: 13px;
  line-height: 1.6;
  color: #4e5969;
  background: #f7f8fa;
  border-color: transparent;
  box-shadow: none;
  padding: 8px 12px;
}
.chap-summary :deep(.el-textarea__inner:hover) {
  background: #f2f3f5;
}
.chap-summary :deep(.el-textarea__inner:focus) {
  background: #fff;
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 1px var(--el-color-primary) inset;
}
.editor-host {
  flex: 1;
  min-height: 0;
}
</style>
