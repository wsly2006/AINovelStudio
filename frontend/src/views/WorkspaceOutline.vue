<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MagicStick, Document } from '@element-plus/icons-vue'
import { useWorkspaceStore } from '../stores/workspace'
import ChapterList from '../components/ChapterList.vue'
import ChapterCreateDialog from '../components/ChapterCreateDialog.vue'
import ChapterBeatsEditor from '../components/ChapterBeatsEditor.vue'
import OutlineBatchDialog from '../components/OutlineBatchDialog.vue'
import { formatChapterFullTitle } from '../composables/chapterTitle'
import { chaptersApi } from '../api/chapters'
import { plotThreadsApi } from '../api/plotThreads'

const route = useRoute()
const store = useWorkspaceStore()
const { t } = useI18n()

const dialogVisible = ref(false)
const dialogMode = ref('create')
const dialogOrderIndex = ref(1)
const dialogTitle = ref('')
const dialogSummary = ref('')
const dialogTargetId = ref(null)

const batchDialogVisible = ref(false)

// 当前章节大纲缓存
const currentBeats = ref([])
const titleDraft = ref('')
const summaryDraft = ref('')
const savingMeta = ref(false)
const savingBeats = ref(false)

const projectThreads = ref([])

const selectedChapter = computed(
  () => store.chapters.find((c) => c.id === store.selectedId) || null
)

const selectedChapterFullTitle = computed(() =>
  selectedChapter.value ? formatChapterFullTitle(selectedChapter.value, t) : ''
)

const hasContent = computed(
  () => (selectedChapter.value?.word_count || 0) > 0
)

async function refreshThreads(pid) {
  try {
    projectThreads.value = await plotThreadsApi.list(pid)
  } catch {
    projectThreads.value = []
  }
}

async function loadChapterDetail() {
  const id = selectedChapter.value?.id
  if (!id) {
    currentBeats.value = []
    titleDraft.value = ''
    summaryDraft.value = ''
    return
  }
  try {
    const detail = await chaptersApi.get(id)
    currentBeats.value = Array.isArray(detail.beats) ? detail.beats : []
    titleDraft.value = detail.title || ''
    summaryDraft.value = detail.summary || ''
  } catch {
    currentBeats.value = []
  }
}

watch(() => selectedChapter.value?.id, () => {
  loadChapterDetail()
}, { immediate: true })

onMounted(() => {
  const pid = Number(route.params.id)
  refreshThreads(pid)
})

async function flushMeta() {
  const ch = selectedChapter.value
  if (!ch) return
  const titleNext = (titleDraft.value || '').trim()
  const summaryNext = (summaryDraft.value || '').trim()
  const titleSame = (ch.title || '') === titleNext
  const summarySame = (ch.summary || '') === summaryNext
  if (titleSame && summarySame) return
  savingMeta.value = true
  try {
    await store.updateChapterMeta(ch.id, {
      title: titleNext,
      summary: summaryNext,
    })
  } catch (e) {
    ElMessage.error(e.message || t('workspace.updateFailed'))
  } finally {
    savingMeta.value = false
  }
}

async function onSelect(chapter) {
  if (chapter.id === store.selectedId) return
  await flushMeta()
  store.select(chapter.id)
}

async function onBeatsChange(next) {
  // 编辑节拍后立即落库,大纲阶段更像 CRUD,不像编辑器有 1.5s 防抖
  currentBeats.value = next
  const id = selectedChapter.value?.id
  if (!id || savingBeats.value) return
  savingBeats.value = true
  try {
    await chaptersApi.update(id, { beats: next })
  } catch (e) {
    ElMessage.error(e.message || t('workspace.updateFailed'))
  } finally {
    savingBeats.value = false
  }
}

function onCreate() {
  dialogMode.value = 'create'
  dialogOrderIndex.value = store.chapters.length + 1
  dialogTitle.value = ''
  dialogSummary.value = ''
  dialogTargetId.value = null
  dialogVisible.value = true
}

function onRename(chapter) {
  dialogMode.value = 'rename'
  dialogOrderIndex.value = chapter.order_index
  dialogTitle.value = chapter.title || ''
  dialogSummary.value = ''
  dialogTargetId.value = chapter.id
  dialogVisible.value = true
}

function onEdit(chapter) {
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
    try {
      await store.updateChapterMeta(id, payload)
      ElMessage.success(t('workspace.chapterUpdated'))
      // 编辑当前选中章节时把本地 draft 同步过来
      if (id === selectedChapter.value?.id) {
        titleDraft.value = payload.title || ''
        summaryDraft.value = payload.summary || ''
      }
    } catch (e) {
      ElMessage.error(e.message || t('workspace.updateFailed'))
      throw e
    }
  } else {
    const id = dialogTargetId.value
    if (!id) return
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

function onBatchSuggest() {
  batchDialogVisible.value = true
}

async function onBatchCreated() {
  // 批量大纲落库后,刷一遍章节列表;选中第一个新章
  const projectId = Number(route.params.id)
  await store.loadProject(projectId).catch(() => {})
}
</script>

<template>
  <aside class="sidebar">
    <ChapterList
      :chapters="store.chapters"
      :selected-id="store.selectedId"
      mode="outline"
      @select="onSelect"
      @create="onCreate"
      @rename="onRename"
      @delete="onDelete"
      @reorder="onReorder"
      @edit="onEdit"
    />
  </aside>

  <main class="outline-main">
    <div class="topbar">
      <span class="topbar-title">{{ t('outline.pageTitle') }}</span>
      <span class="topbar-hint">{{ t('outline.pageHint') }}</span>
      <span class="spacer" />
      <el-button type="primary" :icon="MagicStick" @click="onBatchSuggest">
        {{ t('outline.batchSuggestButton') }}
      </el-button>
    </div>

    <div v-if="!selectedChapter" class="placeholder">
      <div class="emoji">📖</div>
      <p>{{ t('outline.placeholder') }}</p>
      <el-button type="primary" :icon="MagicStick" @click="onBatchSuggest">
        {{ t('outline.batchSuggestButton') }}
      </el-button>
    </div>

    <div v-else class="editor-pane">
      <div class="header-row">
        <h2 class="chap-prefix">{{ t('formats.chapterOrder', { n: selectedChapter.order_index }) }}</h2>
        <el-input
          v-model="titleDraft"
          :placeholder="t('chapterDialog.titlePlaceholder')"
          maxlength="200"
          class="title-input"
          @blur="flushMeta"
        />
      </div>

      <div v-if="hasContent" class="content-banner">
        <el-icon><Document /></el-icon>
        <span>{{ t('outline.contentExistsBanner') }}</span>
      </div>

      <div class="split">
        <div class="col col-left">
          <label class="field-label">{{ t('outline.fieldSummary') }}</label>
          <el-input
            v-model="summaryDraft"
            type="textarea"
            resize="none"
            :placeholder="t('outline.summaryPlaceholder')"
            maxlength="4000"
            show-word-limit
            class="summary-input"
            @blur="flushMeta"
          />
          <div class="field-hint">{{ t('outline.summaryHint') }}</div>
        </div>

        <div class="col col-right">
          <label class="field-label">{{ t('outline.fieldBeats') }}</label>
          <ChapterBeatsEditor
            :model-value="currentBeats"
            @update:model-value="onBeatsChange"
            :chapter-id="selectedChapter.id"
            :threads="projectThreads"
            :target-word-count="store.project?.words_per_chapter || 4000"
          />
        </div>
      </div>
    </div>
  </main>

  <ChapterCreateDialog
    v-model="dialogVisible"
    :mode="dialogMode"
    :order-index="dialogOrderIndex"
    :title="dialogTitle"
    :summary="dialogSummary"
    @submit="onDialogSubmit"
  />

  <OutlineBatchDialog
    v-model="batchDialogVisible"
    :project-id="store.project?.id || null"
    :chapters="store.chapters"
    :default-target-word-count="store.project?.words_per_chapter || 4000"
    @created="onBatchCreated"
  />
</template>

<style scoped>
.sidebar {
  width: 280px;
  flex-shrink: 0;
  height: 100%;
}
.outline-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 16px 24px;
}
.topbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e5e6eb;
  margin-bottom: 16px;
  flex-shrink: 0;
}
.topbar-title {
  font-size: 16px;
  font-weight: 600;
  color: #1f2329;
}
.topbar-hint {
  font-size: 12px;
  color: #86909c;
}
.spacer {
  flex: 1;
}
.placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #86909c;
}
.placeholder .emoji {
  font-size: 56px;
  opacity: 0.6;
}
.editor-pane {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 0;
}
.header-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}
.chap-prefix {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #4e5969;
  flex-shrink: 0;
}
.title-input {
  flex: 1;
}
.title-input :deep(.el-input__inner) {
  font-size: 18px;
  font-weight: 600;
}
.content-banner {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: #fff7e6;
  border: 1px solid #ffd591;
  border-radius: 6px;
  font-size: 12px;
  color: #d46b08;
  flex-shrink: 0;
}
.split {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr);
  gap: 16px;
  min-height: 0;
  overflow: hidden;
}
.col {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 0;
  overflow: hidden;
}
.col-right {
  overflow-y: auto;
  padding-right: 4px;
}
.field-label {
  font-size: 13px;
  font-weight: 600;
  color: #1f2329;
  flex-shrink: 0;
}
.field-hint {
  font-size: 12px;
  color: #86909c;
  flex-shrink: 0;
}
.summary-input {
  flex: 1;
  min-height: 0;
  display: flex;
}
.summary-input :deep(.el-textarea) {
  flex: 1;
  display: flex;
}
.summary-input :deep(.el-textarea__inner) {
  flex: 1;
  height: 100%;
  font-size: 14px;
  line-height: 1.7;
}
</style>
