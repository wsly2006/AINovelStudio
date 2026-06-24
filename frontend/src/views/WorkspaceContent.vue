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
import AIAssistantDrawer from '../components/AIAssistantDrawer.vue'
import ChapterScoreDialog from '../components/ChapterScoreDialog.vue'
import ChapterStyleDialog from '../components/ChapterStyleDialog.vue'
import ChapterBeatsDialog from '../components/ChapterBeatsDialog.vue'
import OutlineAlignmentDialog from '../components/OutlineAlignmentDialog.vue'
import ChapterTranslateDrawer from '../components/ChapterTranslateDrawer.vue'
import AutoWriteDialog from '../components/AutoWriteDialog.vue'
import AutoWriteProgressDrawer from '../components/AutoWriteProgressDrawer.vue'
import { formatChapterFullTitle } from '../composables/chapterTitle'
import { indexChapter } from '../composables/indexChapter'
import { locateQuote } from '../composables/locateQuote'
import { chapterVersionsApi } from '../api/chapterVersions'
import { chaptersApi } from '../api/chapters'
import { plotThreadsApi } from '../api/plotThreads'
import { outlineApi } from '../api/outline'

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
const drawerInitialInstruction = ref('')

// AI 助手抽屉:基于工程/章节/选区的多轮对话
const assistantVisible = ref(false)
const assistantSelection = ref('')

const dialogVisible = ref(false)
const dialogMode = ref('create') // 'create' | 'rename' | 'edit'
const dialogOrderIndex = ref(1)
const dialogTitle = ref('')
const dialogSummary = ref('')
const dialogTargetId = ref(null)

// AI 评分对话框
const scoreVisible = ref(false)
// AI 文风检查对话框
const styleVisible = ref(false)
// 大纲一致性对账对话框
const outlineAlignVisible = ref(false)
// 章节翻译抽屉(M3)
const translateDrawerVisible = ref(false)
const glossaryCount = ref(0)

// 自动连写
const autoWriteDialogVisible = ref(false)
const autoWriteProgressVisible = ref(false)
const autoWriteTaskId = ref('')
const autoWriteChapterIds = ref([])
const autoWriteMode = ref('auto_fix')
const autoWriteThreshold = ref(70)

// 节拍对话框 + 当前章节的最新节拍。打开抽屉/对话框前实时拉,免得改了章节后用旧值
const beatsDialogVisible = ref(false)
const currentChapterBeats = ref([])
const currentChapterAlignment = ref([])

// 工程主线列表(供节拍编辑里选「推进哪条线」)
const projectThreads = ref([])

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
  refreshThreads(pid)
})

async function refreshThreads(pid) {
  try {
    projectThreads.value = await plotThreadsApi.list(pid)
  } catch {
    projectThreads.value = []
  }
}

// 打开生成抽屉 / 节拍对话框前,先拉一次章节详情拿最新 beats + 对账结果
async function fetchCurrentBeats() {
  const id = selectedChapter.value?.id
  if (!id) {
    currentChapterBeats.value = []
    currentChapterAlignment.value = []
    return
  }
  try {
    const detail = await chaptersApi.get(id)
    currentChapterBeats.value = Array.isArray(detail.beats) ? detail.beats : []
    currentChapterAlignment.value = Array.isArray(detail.beats_alignment)
      ? detail.beats_alignment
      : []
  } catch {
    currentChapterBeats.value = []
    currentChapterAlignment.value = []
  }
}

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
    const count = payload.count || 1
    try {
      if (count > 1) {
        // 批量追加空白章节走 outlineApi,落库后刷一遍 store
        const drafts = Array.from({ length: count }, () => ({
          title: '',
          summary: null,
          beats: [],
        }))
        await outlineApi.batchCreate(store.project.id, drafts)
        await store.loadProject(store.project.id)
        ElMessage.success(t('workspace.chapterBatchCreated', { n: count }))
      } else {
        await store.createChapter({
          title: payload.title,
          summary: payload.summary,
        })
        ElMessage.success(t('workspace.chapterCreated'))
      }
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
  await fetchCurrentBeats()
  drawerMode.value = 'generate'
  drawerVisible.value = true
}

// 自动连写:打开配置对话框,刷新最新章节列表后再开
async function onAIAutoWrite() {
  await flushEditor()
  await flushSummary()
  autoWriteDialogVisible.value = true
}

// 配置对话框点「开始连写」后的回调:接住 task_id,打开进度抽屉
function onAutoWriteStarted({ taskId, chapterIds, mode, scoreThreshold }) {
  autoWriteTaskId.value = taskId
  autoWriteChapterIds.value = chapterIds || []
  autoWriteMode.value = mode || 'auto_fix'
  autoWriteThreshold.value = scoreThreshold || 70
  autoWriteProgressVisible.value = true
}

// 自动连写跑完后:刷一遍章节列表 + 知识库,让侧栏的字数 / 评分徽章同步
async function onAutoWriteFinished() {
  const projectId = Number(route.params.id)
  try {
    await store.loadProject(projectId)
  } catch {}
  await Promise.all([
    charactersStore.load(projectId).catch(() => {}),
    worldStore.load(projectId).catch(() => {}),
    itemsStore.load(projectId).catch(() => {}),
  ])
}

async function onAIBeats() {
  if (!selectedChapter.value) return
  await flushEditor()
  await fetchCurrentBeats()
  beatsDialogVisible.value = true
}

function onBeatsSaved({ chapterId, beats, beats_alignment }) {
  // 同步到本地缓存,免得抽屉再次打开时还是旧值。改节拍会让对账结果失效,这里也跟着清掉
  if (selectedChapter.value?.id === chapterId) {
    currentChapterBeats.value = Array.isArray(beats) ? beats : []
    currentChapterAlignment.value = Array.isArray(beats_alignment) ? beats_alignment : []
  }
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

// AI 助手:打开抽屉前抓一次当前选区(打开后选区会随用户切换变化,但首次打开取当下值即可)
async function onAIAssistant() {
  await flushEditor()
  assistantSelection.value = editorRef.value?.getSelection?.() || ''
  assistantVisible.value = true
}

async function onAssistantInsert(text) {
  await snapshotBeforeAI()
  editorRef.value?.insertAtCursor(text)
}
async function onAssistantReplace(text) {
  if (!editorRef.value) return
  const sel = editorRef.value.getSelection?.() || ''
  if (!sel) {
    ElMessage.warning(t('ai.selectionEmpty'))
    return
  }
  await snapshotBeforeAI()
  editorRef.value.replaceSelection(text)
}
async function onAssistantAppend(text) {
  await snapshotBeforeAI()
  editorRef.value?.appendToEnd(text)
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

async function onAIStyleCheck() {
  if (!selectedChapter.value) return
  await flushEditor()
  styleVisible.value = true
}

// 大纲对账:把当前章节的正文与计划好的 summary + beats 对账
async function onOutlineAlign() {
  if (!selectedChapter.value) return
  await flushEditor()
  outlineAlignVisible.value = true
}

// 章节翻译:把中文正文翻成目标语言,落 chapter_versions 不动 chapter.content
async function onAITranslate() {
  if (!selectedChapter.value) return
  await flushEditor()
  await flushSummary()
  // 拉一下当前工程的术语表条数,只用于 hint;不阻塞抽屉打开
  try {
    const projectId = Number(route.params.id)
    const list = await fetch(
      `/api/projects/${projectId}/glossary?target_lang=en-US`,
    ).then((r) => (r.ok ? r.json() : []))
    glossaryCount.value = Array.isArray(list) ? list.length : 0
  } catch {
    glossaryCount.value = 0
  }
  translateDrawerVisible.value = true
}

function onTranslated() {
  ElMessage.success(t('translate.done', {
    n: 0,
    vid: '',
  }).split(',')[0])
}

// 评分弹窗里 创建/删除 后通知列表更新分数徽章
function onScoreChanged({ chapterId, latestOverall }) {
  store.applyLatestScore(chapterId, latestOverall)
}

// 文风检查弹窗里 创建/删除 后通知列表更新「AI 味」徽章
function onStyleChanged({ chapterId, latestIssueCount }) {
  store.applyLatestStyleIssueCount(chapterId, latestIssueCount)
}

// 文风检查面板「去改写」:在编辑器里定位 quote 并打开改写抽屉
function onStyleJumpRewrite({ quote, suggestion, why, kind }) {
  const ed = editorRef.value
  if (!ed || !quote) return
  const content = ed.getContent() || ''
  const span = locateQuote(content, quote)
  if (!span) {
    ElMessage.warning('在正文中找不到对应片段,可能已被改写过。请手动选中后再用「改写选区」。')
    return
  }
  ed.selectRange(span[0], span[1])
  // 把 AI 给的「重写方向」预填进改写抽屉,再让用户拍板
  drawerSelection.value = content.slice(span[0], span[1])
  drawerInitialInstruction.value = suggestion
    ? `${suggestion}(原因:${why || kind || 'AI 味较重'})`
    : `去掉 AI 味:${why || kind || ''}`.trim()
  drawerMode.value = 'rewrite'
  drawerVisible.value = true
}

async function onDrawerReplace(text) {
  await snapshotBeforeAI()
  editorRef.value?.replaceAll(text)
  await autoIndexAfterAI()
}
async function onDrawerAppend(text) {
  await snapshotBeforeAI()
  editorRef.value?.appendToEnd(text)
  await autoIndexAfterAI()
}
async function onDrawerInsert(text) {
  await snapshotBeforeAI()
  editorRef.value?.insertAtCursor(text)
  await autoIndexAfterAI()
}
async function onDrawerAccept(text) {
  await snapshotBeforeAI()
  editorRef.value?.replaceSelection(text)
  await autoIndexAfterAI()
}

// AI 写完正文后:先把内容 flush 到 DB,再调单章自动索引,索引完再做节拍-事件对账。
// 失败不弹错,只 console.warn——这是兜底优化,不应妨碍主流程。
async function autoIndexAfterAI() {
  const id = selectedChapter.value?.id
  if (!id) return
  try {
    await flushEditor()
    const idx = await chaptersApi.autoIndex(id)
    if (idx?.extracted > 0) {
      ElMessage.success(`已自动索引本章新增 ${idx.extracted} 个事件`)
    }
    // 章节有节拍才需要对账,后端会自己判断;前端只在 beats 非空时才请求,省一次 AI 调用
    const detail = await chaptersApi.get(id)
    if (Array.isArray(detail.beats) && detail.beats.length > 0) {
      const align = await chaptersApi.checkBeats(id)
      if (align?.missing > 0 || align?.partial > 0) {
        const bits = []
        if (align.missing) bits.push(`${align.missing} 拍未兑现`)
        if (align.partial) bits.push(`${align.partial} 拍弱化`)
        ElMessage.warning(`节拍对账:${bits.join(' / ')},去节拍编辑里看详情`)
      }
    }
  } catch (e) {
    console.warn('自动索引/对账失败,跳过:', e?.message || e)
  }
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
          @beats="onAIBeats"
          @style-check="onAIStyleCheck"
          @continue="onAIContinue"
          @rewrite="onAIRewrite"
          @summarize="onAISummarize"
          @index="onIndexChapter"
          @score="onAIScore"
          @outline-align="onOutlineAlign"
          @translate="onAITranslate"
          @assistant="onAIAssistant"
          @auto-write="onAIAutoWrite"
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
        @request-rewrite="onAIRewrite"
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
    :threads="projectThreads"
    :initial-beats="currentChapterBeats"
    :initial-alignment="currentChapterAlignment"
    :chapter-has-content="(selectedChapter?.word_count || 0) > 0"
    :default-target-word-count="store.project?.words_per_chapter || 4000"
    :initial-instruction="drawerInitialInstruction"
    @replace="onDrawerReplace"
    @append="onDrawerAppend"
    @insert="onDrawerInsert"
    @accept="onDrawerAccept"
    @beats-saved="onBeatsSaved"
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
    @changed="onScoreChanged"
  />

  <ChapterStyleDialog
    v-model="styleVisible"
    :chapter-id="selectedChapter?.id || null"
    :chapter-title="selectedChapterFullTitle"
    @changed="onStyleChanged"
    @jump-rewrite="onStyleJumpRewrite"
  />

  <OutlineAlignmentDialog
    v-model="outlineAlignVisible"
    :chapter-id="selectedChapter?.id || null"
    :chapter-title="selectedChapterFullTitle"
  />

  <ChapterTranslateDrawer
    v-model="translateDrawerVisible"
    :chapter-id="selectedChapter?.id || null"
    :glossary-count="glossaryCount"
    @translated="onTranslated"
  />

  <ChapterBeatsDialog
    v-model="beatsDialogVisible"
    :chapter-id="selectedChapter?.id || null"
    :chapter-title="selectedChapterFullTitle"
    :initial-beats="currentChapterBeats"
    :initial-alignment="currentChapterAlignment"
    :threads="projectThreads"
    :target-word-count="store.project?.words_per_chapter || 4000"
    @saved="onBeatsSaved"
  />

  <AIAssistantDrawer
    v-model="assistantVisible"
    :project-id="store.project?.id || null"
    :chapter-id="selectedChapter?.id || null"
    :chapter-title="selectedChapterFullTitle"
    :selection-text="assistantSelection"
    @insert-to-cursor="onAssistantInsert"
    @replace-selection="onAssistantReplace"
    @append-to-end="onAssistantAppend"
  />

  <AutoWriteDialog
    v-model="autoWriteDialogVisible"
    :project-id="store.project?.id || null"
    :chapters="store.chapters"
    :default-chapter-id="selectedChapter?.id || null"
    :characters="projectCharacters"
    :world-entities="projectWorld"
    :items="projectItems"
    :default-target-word-count="store.project?.words_per_chapter || 4000"
    @started="onAutoWriteStarted"
  />

  <AutoWriteProgressDrawer
    v-model="autoWriteProgressVisible"
    :task-id="autoWriteTaskId"
    :initial-chapter-ids="autoWriteChapterIds"
    :initial-mode="autoWriteMode"
    :initial-threshold="autoWriteThreshold"
    @finished="onAutoWriteFinished"
    @cancelled="onAutoWriteFinished"
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
