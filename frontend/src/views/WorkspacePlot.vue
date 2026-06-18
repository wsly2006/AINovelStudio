<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, MagicStick, Search, StarFilled } from '@element-plus/icons-vue'
import { plotApi } from '../api/analysis'
import { stateEventsApi } from '../api/stateEvents'
import { useCharactersStore } from '../stores/characters'
import { useWorkspaceStore } from '../stores/workspace'
import { useWorldStore } from '../stores/world'
import { useLaddersStore } from '../stores/ladders'
import { streamProgressSSE } from '../api/sse'

const route = useRoute()
const { t } = useI18n()
const charsStore = useCharactersStore()
const workspace = useWorkspaceStore()
const worldStore = useWorldStore()
const laddersStore = useLaddersStore()

const projectId = computed(() => Number(route.params.id))
const events = ref([])
const stateEvents = ref([])
const loading = ref(false)
const extracting = ref(false)
const checking = ref(false)
const extractProgress = ref({ index: 0, total: 0, title: '' })
const issues = ref([])

const dialogVisible = ref(false)
const form = ref({
  chapter_id: null,
  title: '',
  description: '',
  importance: 3,
  character_ids: [],
})
const editingId = ref(null)

const charById = computed(() => {
  const m = {}
  for (const c of charsStore.items) m[c.id] = c
  return m
})
const chapterById = computed(() => {
  const m = {}
  for (const c of workspace.chapters) m[c.id] = c
  return m
})
const worldById = computed(() => {
  const m = {}
  for (const e of worldStore.items) m[e.id] = e
  return m
})
const ladderById = computed(() => {
  const m = {}
  for (const l of laddersStore.items) m[l.id] = l
  return m
})

// 按 chapter 分组,同时挂上状态事件
const groupedEvents = computed(() => {
  const groups = new Map()
  for (const ev of events.value) {
    const key = ev.chapter_id
    if (!groups.has(key)) groups.set(key, { events: [], stateEvents: [] })
    groups.get(key).events.push(ev)
  }
  for (const ev of stateEvents.value) {
    const key = ev.chapter_id
    if (!groups.has(key)) groups.set(key, { events: [], stateEvents: [] })
    groups.get(key).stateEvents.push(ev)
  }
  // 按章节 order_index 排
  return Array.from(groups.entries())
    .map(([cid, payload]) => ({
      chapter: chapterById.value[cid] || { id: cid, title: `#${cid}`, order_index: 0 },
      events: payload.events.sort((a, b) => a.order_in_chapter - b.order_in_chapter),
      stateEvents: payload.stateEvents.sort(
        (a, b) => a.order_in_chapter - b.order_in_chapter
      ),
    }))
    .sort((a, b) => (a.chapter.order_index || 0) - (b.chapter.order_index || 0))
})

const STATE_KIND_META = {
  tier_up: { label: '境界提升', color: '#fa8c16' },
  tier_down: { label: '境界下降', color: '#86909c' },
  location_change: { label: '前往', color: '#13c2c2' },
  item_acquired: { label: '获得', color: '#52c41a' },
  item_lost: { label: '失去', color: '#ff7875' },
  injury: { label: '负伤', color: '#f5222d' },
  other: { label: '其他', color: '#bfbfbf' },
}

function describeStateEvent(se) {
  const meta = STATE_KIND_META[se.kind] || STATE_KIND_META.other
  const charName = charById.value[se.character_id]?.name || `#${se.character_id}`
  const p = se.payload || {}
  let detail = ''
  switch (se.kind) {
    case 'tier_up':
    case 'tier_down': {
      const ladder = ladderById.value[charById.value[se.character_id]?.ladder_id]
      const tiers = ladder?.tiers || []
      const idx = p.to_index
      detail =
        typeof idx === 'number' && tiers[idx]
          ? tiers[idx]
          : typeof idx === 'number'
          ? `第 ${idx + 1} 阶`
          : ''
      break
    }
    case 'location_change': {
      const loc = worldById.value[p.to_id]
      detail = loc ? loc.name : ''
      break
    }
    case 'item_acquired':
    case 'item_lost': {
      const item = worldById.value[p.item_id]
      detail = item ? item.name : ''
      break
    }
    case 'injury':
      detail = p.description || ''
      break
    case 'other':
      detail = p.note || ''
      break
  }
  return { charName, label: meta.label, color: meta.color, detail }
}

async function loadAll() {
  loading.value = true
  try {
    if (!charsStore.items.length) await charsStore.load(projectId.value)
    if (worldStore.projectId !== projectId.value) await worldStore.load(projectId.value)
    if (laddersStore.projectId !== projectId.value) await laddersStore.load(projectId.value)
    const [evs, ses] = await Promise.all([
      plotApi.listEvents(projectId.value),
      stateEventsApi.list(projectId.value),
    ])
    events.value = evs
    stateEvents.value = ses
  } finally {
    loading.value = false
  }
}

onMounted(loadAll)

function openNew() {
  editingId.value = null
  form.value = {
    chapter_id: workspace.chapters[0]?.id || null,
    title: '',
    description: '',
    importance: 3,
    character_ids: [],
  }
  dialogVisible.value = true
}

function openEdit(ev) {
  editingId.value = ev.id
  form.value = {
    chapter_id: ev.chapter_id,
    title: ev.title,
    description: ev.description || '',
    importance: ev.importance,
    character_ids: [...(ev.character_ids || [])],
  }
  dialogVisible.value = true
}

async function onSubmit() {
  if (!form.value.title.trim() || !form.value.chapter_id) {
    ElMessage.warning('请填写完整')
    return
  }
  try {
    if (editingId.value) {
      await plotApi.updateEvent(editingId.value, {
        title: form.value.title,
        description: form.value.description || null,
        importance: form.value.importance,
        character_ids: form.value.character_ids,
      })
    } else {
      await plotApi.createEvent(projectId.value, {
        chapter_id: form.value.chapter_id,
        title: form.value.title,
        description: form.value.description || null,
        importance: form.value.importance,
        character_ids: form.value.character_ids,
      })
    }
    dialogVisible.value = false
    await loadAll()
    ElMessage.success(t('plot.saved'))
  } catch (e) {
    ElMessage.error(e.message || t('common.failed'))
  }
}

async function onDelete(ev) {
  try {
    await ElMessageBox.confirm(t('plot.deleteConfirm'), t('plot.deleteTitle'), {
      type: 'warning',
      confirmButtonText: t('common.delete'),
      cancelButtonText: t('common.cancel'),
    })
  } catch {
    return
  }
  try {
    await plotApi.removeEvent(ev.id)
    await loadAll()
    ElMessage.success(t('plot.deleted'))
  } catch (e) {
    ElMessage.error(e.message || t('common.failed'))
  }
}

async function onExtract() {
  extracting.value = true
  extractProgress.value = { index: 0, total: 0, title: '' }
  let extracted = 0
  await streamProgressSSE(
    plotApi.extractUrl(projectId.value),
    {},
    {
      onStart: ({ total }) => (extractProgress.value = { index: 0, total, title: '' }),
      onProgress: ({ index, total, title }) =>
        (extractProgress.value = { index, total, title: title || '' }),
      onDone: (data) => (extracted = data.extracted || 0),
      onError: (msg) => ElMessage.error(`${t('characters.extractFailed')}: ${msg}`),
    }
  )
  extracting.value = false
  await loadAll()
  ElMessage.success(t('plot.extractDone', { n: extracted }))
}

async function onCheck() {
  checking.value = true
  issues.value = []
  const closeMsg = ElMessage({ type: 'info', message: t('plot.checking'), duration: 0 })
  try {
    const result = await plotApi.check(projectId.value)
    issues.value = result.issues || []
    closeMsg.close()
    if (issues.value.length === 0) {
      ElMessage.success(t('plot.noIssues'))
    } else {
      ElMessage.warning(t('plot.issuesFound', { n: issues.value.length }))
    }
  } catch (e) {
    closeMsg.close()
    ElMessage.error(e.message || t('common.failed'))
  } finally {
    checking.value = false
  }
}

function nameOf(id) {
  return charById.value[id]?.name || `#${id}`
}
</script>

<template>
  <div class="plot-page" v-loading="loading">
    <header class="header">
      <span class="title">{{ t('plot.pageTitle') }} ({{ events.length }})</span>
      <div class="actions">
        <el-button :icon="Search" :loading="checking" @click="onCheck">
          {{ t('plot.check') }}
        </el-button>
        <el-button :icon="MagicStick" :loading="extracting" @click="onExtract">
          {{ t('plot.extract') }}
        </el-button>
        <el-button type="primary" :icon="Plus" @click="openNew" :disabled="!workspace.chapters.length">
          {{ t('plot.newEvent') }}
        </el-button>
      </div>
    </header>

    <div v-if="extracting" class="progress-strip">
      <el-progress
        :percentage="extractProgress.total ? Math.round((extractProgress.index / extractProgress.total) * 100) : 0"
        :stroke-width="6"
      />
      <span class="progress-text">
        {{ extractProgress.title }} ({{ extractProgress.index }}/{{ extractProgress.total }})
      </span>
    </div>

    <div v-if="issues.length" class="issues">
      <div class="issues-title">{{ t('plot.issuesFound', { n: issues.length }) }}</div>
      <div v-for="(iss, i) in issues" :key="i" class="issue">
        <div class="issue-head">
          <el-tag type="warning" size="small">{{ iss.kind }}</el-tag>
          <span class="issue-title">{{ iss.title }}</span>
        </div>
        <div class="issue-detail">{{ iss.detail }}</div>
        <div v-if="iss.related_event_ids?.length" class="issue-meta">
          {{ t('plot.issueRelatedEvents') }}: {{ iss.related_event_ids.join(', ') }}
        </div>
        <div v-if="iss.related_character_ids?.length" class="issue-meta">
          {{ t('plot.issueRelatedChars') }}:
          {{ iss.related_character_ids.map(nameOf).join('、') }}
        </div>
      </div>
    </div>

    <div v-if="events.length === 0 && !loading" class="empty">{{ t('plot.empty') }}</div>

    <div class="timeline">
      <div v-for="grp in groupedEvents" :key="grp.chapter.id" class="chapter-group">
        <div class="chap-header">
          <span class="dot" />
          <span class="chap-title">
            <template v-if="(grp.chapter.title || '').trim()">
              第 {{ grp.chapter.order_index }} 章 《{{ grp.chapter.title }}》
            </template>
            <template v-else>第 {{ grp.chapter.order_index }} 章</template>
          </span>
        </div>
        <div class="events">
          <div
            v-for="ev in grp.events"
            :key="ev.id"
            class="event-card"
            @click="openEdit(ev)"
          >
            <div class="ev-row1">
              <span class="ev-title">{{ ev.title }}</span>
              <span class="stars">
                <el-icon v-for="n in ev.importance" :key="n"><StarFilled /></el-icon>
              </span>
              <el-button text size="small" type="danger" @click.stop="onDelete(ev)">
                {{ t('common.delete') }}
              </el-button>
            </div>
            <div v-if="ev.description" class="ev-desc">{{ ev.description }}</div>
            <div v-if="ev.character_ids?.length" class="ev-chars">
              <el-tag
                v-for="cid in ev.character_ids"
                :key="cid"
                size="small"
                effect="plain"
                type="info"
              >
                {{ nameOf(cid) }}
              </el-tag>
            </div>
          </div>
        </div>

        <!-- 人物状态变化:本章发生的所有 state events -->
        <div v-if="grp.stateEvents.length > 0" class="state-lane">
          <div class="lane-title">本章人物变化</div>
          <div class="lane-items">
            <div
              v-for="se in grp.stateEvents"
              :key="se.id"
              class="state-pill"
              :style="{ borderLeftColor: describeStateEvent(se).color }"
            >
              <span class="se-name">{{ describeStateEvent(se).charName }}</span>
              <span
                class="se-kind"
                :style="{ background: describeStateEvent(se).color }"
              >
                {{ describeStateEvent(se).label }}
              </span>
              <span v-if="describeStateEvent(se).detail" class="se-detail">
                {{ describeStateEvent(se).detail }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? t('common.edit') : t('plot.newEvent')"
      width="520px"
    >
      <el-form label-position="top">
        <el-form-item :label="t('plot.chapterLabel')" required>
          <el-select
            v-model="form.chapter_id"
            :disabled="!!editingId"
            style="width: 100%"
            filterable
          >
            <el-option
              v-for="c in workspace.chapters"
              :key="c.id"
              :value="c.id"
              :label="(c.title || '').trim() ? `第 ${c.order_index} 章 ${c.title}` : `第 ${c.order_index} 章`"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('plot.titleLabel')" required>
          <el-input v-model="form.title" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item :label="t('plot.descLabel')">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item :label="t('plot.importanceLabel')">
          <el-rate v-model="form.importance" :max="5" :allow-half="false" />
        </el-form-item>
        <el-form-item :label="t('plot.charactersLabel')">
          <el-select v-model="form.character_ids" multiple filterable style="width: 100%">
            <el-option v-for="c in charsStore.items" :key="c.id" :value="c.id" :label="c.name" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="onSubmit">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.plot-page {
  flex: 1;
  overflow: auto;
  padding: 16px 24px;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.header .title {
  font-size: 15px;
  font-weight: 600;
}
.header .actions {
  display: flex;
  gap: 8px;
}
.progress-strip {
  background: #f7f8fa;
  border-radius: 8px;
  padding: 8px 12px;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 12px;
}
.progress-strip .el-progress {
  flex: 1;
}
.progress-text {
  font-size: 12px;
  color: #4e5969;
  white-space: nowrap;
}
.issues {
  background: #fff7e6;
  border: 1px solid #ffd591;
  border-radius: 10px;
  padding: 12px 14px;
  margin-bottom: 16px;
}
.issues-title {
  font-weight: 600;
  color: #d46b08;
  margin-bottom: 8px;
}
.issue {
  padding: 8px 0;
  border-top: 1px dashed #ffd591;
}
.issue:first-of-type {
  border-top: none;
  padding-top: 0;
}
.issue-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.issue-title {
  font-weight: 500;
}
.issue-detail {
  font-size: 13px;
  color: #4e5969;
  line-height: 1.6;
}
.issue-meta {
  font-size: 12px;
  color: #86909c;
  margin-top: 4px;
}
.empty {
  text-align: center;
  color: #86909c;
  padding: 60px 16px;
  font-size: 13px;
}
.timeline {
  position: relative;
  padding-left: 18px;
}
.timeline::before {
  content: '';
  position: absolute;
  left: 5px;
  top: 6px;
  bottom: 6px;
  width: 2px;
  background: #e5e6eb;
}
.chapter-group {
  position: relative;
  margin-bottom: 24px;
}
.chap-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  position: relative;
  margin-left: -18px;
  padding-left: 18px;
}
.chap-header .dot {
  position: absolute;
  left: 0;
  top: 6px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #4080ff;
  border: 2px solid #fff;
  box-shadow: 0 0 0 2px #e5e6eb;
}
.chap-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2329;
}
.events {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.event-card {
  background: #fff;
  border-radius: 10px;
  padding: 10px 14px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: border-color 0.1s;
}
.event-card:hover {
  border-color: #c9d2ff;
}
.ev-row1 {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ev-title {
  font-weight: 600;
  flex: 1;
  color: #1f2329;
}
.stars {
  color: #fadb14;
  display: inline-flex;
  gap: 2px;
}
.ev-desc {
  font-size: 13px;
  color: #4e5969;
  line-height: 1.6;
  margin-top: 4px;
}
.ev-chars {
  margin-top: 6px;
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.state-lane {
  margin-top: 10px;
  padding: 8px 12px;
  background: #fafbfc;
  border-radius: 8px;
}
.lane-title {
  font-size: 11px;
  font-weight: 600;
  color: #86909c;
  margin-bottom: 6px;
}
.lane-items {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.state-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #fff;
  border: 1px solid #e5e6eb;
  border-left: 3px solid #c9cdd4;
  border-radius: 6px;
  padding: 3px 8px;
  font-size: 12px;
}
.state-pill .se-name {
  font-weight: 600;
  color: #1f2329;
}
.state-pill .se-kind {
  color: #fff;
  border-radius: 10px;
  padding: 1px 6px;
  font-size: 10px;
}
.state-pill .se-detail {
  color: #4e5969;
}
</style>
