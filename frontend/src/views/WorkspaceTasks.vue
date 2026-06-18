<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useTasksStore } from '../stores/tasks'
import { useCharactersStore } from '../stores/characters'
import { useWorkspaceStore } from '../stores/workspace'

const route = useRoute()
const { t } = useI18n()
const store = useTasksStore()
const charactersStore = useCharactersStore()
const workspace = useWorkspaceStore()

const projectId = computed(() => Number(route.params.id))
const filterStatus = ref('')
const dialogVisible = ref(false)
const editingId = ref(null)
const form = ref(emptyForm())

const STATUS_OPTIONS = [
  { value: 'pending', labelKey: 'tasks.statusPending', tagType: 'info' },
  { value: 'in_progress', labelKey: 'tasks.statusInProgress', tagType: 'warning' },
  { value: 'done', labelKey: 'tasks.statusDone', tagType: 'success' },
  { value: 'abandoned', labelKey: 'tasks.statusAbandoned', tagType: 'danger' },
]

function emptyForm() {
  return {
    title: '',
    description: '',
    status: 'pending',
    priority: 3,
    assignee_ids: [],
    started_chapter_id: null,
    finished_chapter_id: null,
  }
}

const filtered = computed(() =>
  filterStatus.value
    ? store.items.filter((t) => t.status === filterStatus.value)
    : store.items
)

const charById = computed(() => {
  const m = {}
  for (const c of charactersStore.items) m[c.id] = c
  return m
})

const chapterById = computed(() => {
  const m = {}
  for (const c of workspace.chapters) m[c.id] = c
  return m
})

onMounted(async () => {
  await store.load(projectId.value)
  // 这两个旁路 store 可能尚未加载
  if (charactersStore.projectId !== projectId.value) {
    charactersStore.load(projectId.value).catch(() => {})
  }
})

function openNew() {
  editingId.value = null
  form.value = emptyForm()
  dialogVisible.value = true
}

function openEdit(task) {
  editingId.value = task.id
  form.value = {
    title: task.title,
    description: task.description || '',
    status: task.status,
    priority: task.priority,
    assignee_ids: [...(task.assignee_ids || [])],
    started_chapter_id: task.started_chapter_id ?? null,
    finished_chapter_id: task.finished_chapter_id ?? null,
  }
  dialogVisible.value = true
}

async function onSubmit() {
  if (!form.value.title.trim()) {
    ElMessage.warning(t('tasks.fieldTitlePlaceholder'))
    return
  }
  try {
    const payload = {
      title: form.value.title,
      description: form.value.description || null,
      status: form.value.status,
      priority: form.value.priority,
      assignee_ids: form.value.assignee_ids,
      started_chapter_id: form.value.started_chapter_id,
      finished_chapter_id: form.value.finished_chapter_id,
    }
    if (editingId.value) {
      await store.update(editingId.value, payload)
    } else {
      await store.create(payload)
    }
    dialogVisible.value = false
    ElMessage.success(t('tasks.saved'))
  } catch (e) {
    ElMessage.error(e.message || t('common.failed'))
  }
}

async function onDelete(task) {
  try {
    await ElMessageBox.confirm(
      t('tasks.deleteConfirm', { title: task.title }),
      t('tasks.deleteTitle'),
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
    await store.remove(task.id)
    ElMessage.success(t('tasks.deleted'))
  } catch (e) {
    ElMessage.error(e.message || t('common.failed'))
  }
}

async function onQuickStatus(task, newStatus) {
  try {
    await store.update(task.id, { status: newStatus })
  } catch (e) {
    ElMessage.error(e.message || t('common.failed'))
  }
}

function statusLabel(status) {
  const opt = STATUS_OPTIONS.find((s) => s.value === status)
  return opt ? t(opt.labelKey) : status
}

function statusType(status) {
  return STATUS_OPTIONS.find((s) => s.value === status)?.tagType || 'info'
}

function priorityLabel(p) {
  return t(`tasks.priority${p}`)
}

function chapterLabel(cid) {
  if (!cid) return ''
  const c = chapterById.value[cid]
  return c ? `第 ${c.order_index} 章` : `#${cid}`
}

function assigneeNames(ids) {
  return (ids || []).map((id) => charById.value[id]?.name).filter(Boolean)
}
</script>

<template>
  <div class="tasks-page" v-loading="store.loading">
    <header class="header">
      <div>
        <div class="title">{{ t('tasks.pageTitle') }} ({{ store.items.length }})</div>
        <div class="hint">{{ t('tasks.pageHint') }}</div>
      </div>
      <div class="actions">
        <el-radio-group v-model="filterStatus" size="small">
          <el-radio-button label="" value="">{{ t('tasks.filterAll') }}</el-radio-button>
          <el-radio-button
            v-for="s in STATUS_OPTIONS"
            :key="s.value"
            :value="s.value"
          >
            {{ t(s.labelKey) }}
          </el-radio-button>
        </el-radio-group>
        <el-button type="primary" :icon="Plus" @click="openNew">
          {{ t('tasks.newTask') }}
        </el-button>
      </div>
    </header>

    <div v-if="filtered.length === 0 && !store.loading" class="empty">
      {{ t('tasks.empty') }}
    </div>

    <div class="list">
      <div
        v-for="task in filtered"
        :key="task.id"
        class="task-row"
        :class="{ done: task.status === 'done', abandoned: task.status === 'abandoned' }"
        @click="openEdit(task)"
      >
        <div class="row1">
          <el-tag :type="statusType(task.status)" size="small">
            {{ statusLabel(task.status) }}
          </el-tag>
          <span class="priority" :data-priority="task.priority">
            {{ priorityLabel(task.priority) }}
          </span>
          <span class="task-title">{{ task.title }}</span>
          <el-button text size="small" type="danger" @click.stop="onDelete(task)">
            {{ t('common.delete') }}
          </el-button>
        </div>
        <div v-if="task.description" class="desc">{{ task.description }}</div>
        <div class="meta">
          <span v-if="assigneeNames(task.assignee_ids).length > 0" class="meta-item">
            <span class="meta-key">{{ t('tasks.fieldAssignees') }}:</span>
            <el-tag
              v-for="name in assigneeNames(task.assignee_ids)"
              :key="name"
              size="small"
              type="info"
              effect="plain"
              class="assignee-tag"
            >{{ name }}</el-tag>
          </span>
          <span v-if="task.started_chapter_id" class="meta-item">
            {{ t('tasks.fieldStartChapter') }}:{{ chapterLabel(task.started_chapter_id) }}
          </span>
          <span v-if="task.finished_chapter_id" class="meta-item">
            {{ t('tasks.fieldFinishChapter') }}:{{ chapterLabel(task.finished_chapter_id) }}
          </span>
        </div>

        <!-- 快捷状态切换 -->
        <div class="quick" @click.stop>
          <span class="quick-label">{{ t('tasks.quickStatus') }}:</span>
          <el-button
            v-for="s in STATUS_OPTIONS"
            :key="s.value"
            text
            size="small"
            :class="{ 'quick-active': task.status === s.value }"
            @click="onQuickStatus(task, s.value)"
          >
            {{ t(s.labelKey) }}
          </el-button>
        </div>
      </div>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? t('common.edit') : t('tasks.newTask')"
      width="560px"
    >
      <el-form label-position="top">
        <el-form-item :label="t('tasks.fieldTitle')" required>
          <el-input
            v-model="form.title"
            :placeholder="t('tasks.fieldTitlePlaceholder')"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
        <el-form-item :label="t('tasks.fieldDescription')">
          <el-input v-model="form.description" type="textarea" :rows="3" maxlength="4000" />
        </el-form-item>

        <div class="grid">
          <el-form-item :label="t('tasks.fieldStatus')">
            <el-select v-model="form.status" style="width: 100%">
              <el-option
                v-for="s in STATUS_OPTIONS"
                :key="s.value"
                :value="s.value"
                :label="t(s.labelKey)"
              />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('tasks.fieldPriority')">
            <el-rate v-model="form.priority" :max="5" :allow-half="false" />
          </el-form-item>
        </div>

        <el-form-item :label="t('tasks.fieldAssignees')">
          <el-select
            v-model="form.assignee_ids"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            style="width: 100%"
            :placeholder="t('tasks.fieldAssigneesPlaceholder')"
          >
            <el-option
              v-for="c in charactersStore.items"
              :key="c.id"
              :value="c.id"
              :label="c.name"
            />
          </el-select>
        </el-form-item>

        <div class="grid">
          <el-form-item :label="t('tasks.fieldStartChapter')">
            <el-select
              v-model="form.started_chapter_id"
              filterable
              clearable
              style="width: 100%"
              :placeholder="t('tasks.fieldChapterPlaceholder')"
            >
              <el-option
                v-for="c in workspace.chapters"
                :key="c.id"
                :value="c.id"
                :label="(c.title || '').trim() ? `第 ${c.order_index} 章 ${c.title}` : `第 ${c.order_index} 章`"
              />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('tasks.fieldFinishChapter')">
            <el-select
              v-model="form.finished_chapter_id"
              filterable
              clearable
              style="width: 100%"
              :placeholder="t('tasks.fieldChapterPlaceholder')"
            >
              <el-option
                v-for="c in workspace.chapters"
                :key="c.id"
                :value="c.id"
                :label="(c.title || '').trim() ? `第 ${c.order_index} 章 ${c.title}` : `第 ${c.order_index} 章`"
              />
            </el-select>
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="onSubmit">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.tasks-page {
  flex: 1;
  overflow: auto;
  padding: 16px 24px;
}
.header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
  gap: 12px;
  flex-wrap: wrap;
}
.header .title {
  font-size: 15px;
  font-weight: 600;
}
.header .hint {
  font-size: 12px;
  color: #86909c;
  margin-top: 2px;
}
.header .actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.empty {
  text-align: center;
  color: #86909c;
  padding: 60px 16px;
  font-size: 13px;
}
.list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.task-row {
  background: #fff;
  border-radius: 10px;
  padding: 12px 14px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: border-color 0.1s;
}
.task-row:hover {
  border-color: #c9d2ff;
}
.task-row.done {
  opacity: 0.7;
}
.task-row.done .task-title {
  text-decoration: line-through;
  color: #86909c;
}
.task-row.abandoned {
  opacity: 0.5;
}
.task-row.abandoned .task-title {
  text-decoration: line-through;
  color: #c9cdd4;
}
.row1 {
  display: flex;
  align-items: center;
  gap: 8px;
}
.priority {
  display: inline-flex;
  align-items: center;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  background: #f7f8fa;
  color: #4e5969;
}
.priority[data-priority="4"] {
  background: #fff7e6;
  color: #d46b08;
}
.priority[data-priority="5"] {
  background: #ffeded;
  color: #f53f3f;
  font-weight: 600;
}
.task-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2329;
  flex: 1;
}
.desc {
  font-size: 13px;
  color: #4e5969;
  margin-top: 6px;
  line-height: 1.5;
}
.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 8px;
  font-size: 12px;
  color: #86909c;
  align-items: center;
}
.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.meta-key {
  margin-right: 4px;
}
.assignee-tag {
  margin-right: 2px;
}
.quick {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px dashed #f2f3f5;
}
.quick-label {
  font-size: 11px;
  color: #c9cdd4;
  margin-right: 4px;
}
.quick-active {
  color: #4080ff !important;
  font-weight: 600;
}
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
</style>
