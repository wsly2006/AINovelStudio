<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { stateEventsApi } from '../api/stateEvents'

const props = defineProps({
  // 上下文
  characterId: { type: Number, required: true },
  projectId: { type: Number, required: true },
  // 用于 id → 名字翻译
  chapters: { type: Array, default: () => [] },
  ladders: { type: Array, default: () => [] },
  ladderId: { type: Number, default: null }, // 当前人物绑定的阶梯
  worldEntities: { type: Array, default: () => [] },
})

const { t } = useI18n()

const events = ref([])
const snapshot = ref(null)
const loading = ref(false)

const dialogVisible = ref(false)
const editingId = ref(null)
const form = ref(emptyForm())

const KIND_OPTIONS = [
  { value: 'tier_up', labelKey: 'kindTierUp' },
  { value: 'tier_down', labelKey: 'kindTierDown' },
  { value: 'location_change', labelKey: 'kindLocationChange' },
  { value: 'item_acquired', labelKey: 'kindItemAcquired' },
  { value: 'item_lost', labelKey: 'kindItemLost' },
  { value: 'injury', labelKey: 'kindInjury' },
  { value: 'other', labelKey: 'kindOther' },
]

const ladderTiers = computed(() => {
  const ladder = props.ladders.find((l) => l.id === props.ladderId)
  return ladder?.tiers || []
})

const locations = computed(() => props.worldEntities.filter((e) => e.kind === 'location'))
const items = computed(() => props.worldEntities.filter((e) => e.kind === 'item'))

const chapterById = computed(() => {
  const m = {}
  for (const c of props.chapters) m[c.id] = c
  return m
})

function emptyForm() {
  return {
    chapter_id: null,
    kind: 'tier_up',
    order_in_chapter: 0,
    to_index: null,
    to_id: null,
    item_id: null,
    injury_desc: '',
    note: '',
  }
}

async function reload() {
  if (!props.characterId) return
  loading.value = true
  try {
    const [evs, snap] = await Promise.all([
      stateEventsApi.list(props.projectId, { characterId: props.characterId }),
      stateEventsApi.snapshot(props.characterId),
    ])
    events.value = evs
    snapshot.value = snap
  } catch (e) {
    ElMessage.error(e.message || t('common.failed'))
  } finally {
    loading.value = false
  }
}

onMounted(reload)
watch(() => props.characterId, reload)

function openAdd() {
  editingId.value = null
  form.value = emptyForm()
  if (props.chapters.length > 0) form.value.chapter_id = props.chapters[0].id
  dialogVisible.value = true
}

function openEdit(ev) {
  editingId.value = ev.id
  const p = ev.payload || {}
  form.value = {
    chapter_id: ev.chapter_id,
    kind: ev.kind,
    order_in_chapter: ev.order_in_chapter ?? 0,
    to_index: p.to_index ?? null,
    to_id: p.to_id ?? null,
    item_id: p.item_id ?? null,
    injury_desc: p.description ?? '',
    note: p.note ?? '',
  }
  dialogVisible.value = true
}

function buildPayload() {
  const f = form.value
  switch (f.kind) {
    case 'tier_up':
    case 'tier_down':
      return { to_index: f.to_index, note: f.note || null }
    case 'location_change':
      return { to_id: f.to_id, note: f.note || null }
    case 'item_acquired':
    case 'item_lost':
      return { item_id: f.item_id, note: f.note || null }
    case 'injury':
      return { description: f.injury_desc, severity: 'medium' }
    case 'other':
      return { note: f.note }
  }
  return {}
}

async function onSubmit() {
  const f = form.value
  if (!f.chapter_id) {
    ElMessage.warning(t('stateEvents.chapterLabel'))
    return
  }
  const body = {
    chapter_id: f.chapter_id,
    kind: f.kind,
    order_in_chapter: f.order_in_chapter || 0,
    payload: buildPayload(),
  }
  try {
    if (editingId.value) {
      await stateEventsApi.update(editingId.value, body)
    } else {
      await stateEventsApi.create(props.characterId, body)
    }
    dialogVisible.value = false
    ElMessage.success(t('stateEvents.saved'))
    await reload()
  } catch (e) {
    ElMessage.error(e.message || t('common.failed'))
  }
}

async function onDelete(ev) {
  try {
    await ElMessageBox.confirm(t('stateEvents.deleteConfirm'), t('stateEvents.deleteTitle'), {
      type: 'warning',
      confirmButtonText: t('common.delete'),
      cancelButtonText: t('common.cancel'),
    })
  } catch {
    return
  }
  try {
    await stateEventsApi.remove(ev.id)
    ElMessage.success(t('stateEvents.deleted'))
    await reload()
  } catch (e) {
    ElMessage.error(e.message || t('common.failed'))
  }
}

function chapterLabel(cid) {
  const c = chapterById.value[cid]
  if (!c) return `章节 #${cid}`
  const sub = (c.title || '').trim()
  return sub ? `第 ${c.order_index} 章 ${sub}` : `第 ${c.order_index} 章`
}

function kindLabel(kind) {
  const k = KIND_OPTIONS.find((x) => x.value === kind)
  return k ? t(`stateEvents.${k.labelKey}`) : kind
}

function eventBrief(ev) {
  const p = ev.payload || {}
  switch (ev.kind) {
    case 'tier_up':
    case 'tier_down': {
      const idx = p.to_index
      const tier =
        typeof idx === 'number' && ladderTiers.value[idx]
          ? ladderTiers.value[idx]
          : `第 ${idx + 1} 阶`
      return `${kindLabel(ev.kind)} → ${tier}`
    }
    case 'location_change': {
      const loc = locations.value.find((l) => l.id === p.to_id)
      return `${kindLabel(ev.kind)} → ${loc ? loc.name : `#${p.to_id}`}`
    }
    case 'item_acquired':
    case 'item_lost': {
      const it = items.value.find((i) => i.id === p.item_id)
      return `${kindLabel(ev.kind)}: ${it ? it.name : `#${p.item_id}`}`
    }
    case 'injury':
      return `${kindLabel(ev.kind)}: ${p.description || ''}`
    default:
      return p.note || kindLabel(ev.kind)
  }
}

const snapshotDisplay = computed(() => {
  if (!snapshot.value) return null
  const s = snapshot.value
  const tier =
    typeof s.tier_index === 'number' && ladderTiers.value[s.tier_index]
      ? ladderTiers.value[s.tier_index]
      : null
  const loc = locations.value.find((l) => l.id === s.location_id)
  const itemNames = (s.item_ids || [])
    .map((iid) => items.value.find((i) => i.id === iid)?.name)
    .filter(Boolean)
  return {
    tier,
    locationName: loc?.name,
    itemNames,
    injuries: s.injuries || [],
  }
})
</script>

<template>
  <div class="state-events" v-loading="loading">
    <div class="header">
      <div>
        <div class="title">{{ t('stateEvents.sectionTitle') }}</div>
        <div class="hint">{{ t('stateEvents.sectionHint') }}</div>
      </div>
      <el-button :icon="Plus" size="small" @click="openAdd" :disabled="chapters.length === 0">
        {{ t('stateEvents.addEvent') }}
      </el-button>
    </div>

    <!-- 当前快照 -->
    <div v-if="snapshotDisplay" class="snapshot">
      <div class="snap-title">{{ t('stateEvents.snapshotLatest') }}</div>
      <div v-if="!snapshotDisplay.tier && !snapshotDisplay.locationName && snapshotDisplay.itemNames.length === 0 && snapshotDisplay.injuries.length === 0" class="snap-none">
        {{ t('stateEvents.snapshotNone') }}
      </div>
      <div v-else class="snap-rows">
        <div v-if="snapshotDisplay.tier" class="snap-row">
          <span class="snap-key">{{ t('stateEvents.snapshotTier') }}</span>
          <el-tag size="small" type="warning">{{ snapshotDisplay.tier }}</el-tag>
        </div>
        <div v-if="snapshotDisplay.locationName" class="snap-row">
          <span class="snap-key">{{ t('stateEvents.snapshotLocation') }}</span>
          <el-tag size="small" type="success">{{ snapshotDisplay.locationName }}</el-tag>
        </div>
        <div v-if="snapshotDisplay.itemNames.length > 0" class="snap-row">
          <span class="snap-key">{{ t('stateEvents.snapshotItems') }}</span>
          <el-tag
            v-for="name in snapshotDisplay.itemNames"
            :key="name"
            size="small"
            type="primary"
            effect="plain"
            class="snap-tag"
          >{{ name }}</el-tag>
        </div>
        <div v-if="snapshotDisplay.injuries.length > 0" class="snap-row">
          <span class="snap-key">{{ t('stateEvents.snapshotInjuries') }}</span>
          <el-tag
            v-for="(inj, i) in snapshotDisplay.injuries"
            :key="i"
            size="small"
            type="danger"
            effect="plain"
            class="snap-tag"
          >{{ inj }}</el-tag>
        </div>
      </div>
    </div>

    <!-- 事件列表 -->
    <div v-if="events.length === 0 && !loading" class="empty">
      {{ t('stateEvents.eventListEmpty') }}
    </div>
    <div class="event-list">
      <div v-for="ev in events" :key="ev.id" class="event-row" @click="openEdit(ev)">
        <span class="ev-chapter">{{ chapterLabel(ev.chapter_id) }}</span>
        <span class="ev-brief">{{ eventBrief(ev) }}</span>
        <el-button text size="small" type="danger" @click.stop="onDelete(ev)">
          {{ t('common.delete') }}
        </el-button>
      </div>
    </div>

    <!-- 编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? t('common.edit') : t('stateEvents.addEvent')"
      width="500px"
    >
      <el-form label-position="top">
        <el-form-item :label="t('stateEvents.chapterLabel')" required>
          <el-select v-model="form.chapter_id" filterable style="width: 100%">
            <el-option
              v-for="c in chapters"
              :key="c.id"
              :value="c.id"
              :label="(c.title || '').trim() ? `第 ${c.order_index} 章 ${c.title}` : `第 ${c.order_index} 章`"
            />
          </el-select>
        </el-form-item>

        <el-form-item :label="t('stateEvents.kindLabel')" required>
          <el-select v-model="form.kind" style="width: 100%">
            <el-option
              v-for="k in KIND_OPTIONS"
              :key="k.value"
              :value="k.value"
              :label="t(`stateEvents.${k.labelKey}`)"
            />
          </el-select>
        </el-form-item>

        <!-- tier_up / tier_down -->
        <el-form-item
          v-if="form.kind === 'tier_up' || form.kind === 'tier_down'"
          :label="t('stateEvents.toTier')"
        >
          <el-select v-model="form.to_index" :disabled="ladderTiers.length === 0" style="width: 100%">
            <el-option
              v-for="(tier, idx) in ladderTiers"
              :key="idx"
              :value="idx"
              :label="`${idx + 1}. ${tier}`"
            />
          </el-select>
        </el-form-item>

        <!-- location_change -->
        <el-form-item v-if="form.kind === 'location_change'" :label="t('stateEvents.toLocation')">
          <el-select v-model="form.to_id" filterable style="width: 100%">
            <el-option v-for="loc in locations" :key="loc.id" :value="loc.id" :label="loc.name" />
          </el-select>
        </el-form-item>

        <!-- item_acquired / item_lost -->
        <el-form-item
          v-if="form.kind === 'item_acquired' || form.kind === 'item_lost'"
          :label="t('stateEvents.item')"
        >
          <el-select v-model="form.item_id" filterable style="width: 100%">
            <el-option v-for="it in items" :key="it.id" :value="it.id" :label="it.name" />
          </el-select>
        </el-form-item>

        <!-- injury -->
        <el-form-item v-if="form.kind === 'injury'" :label="t('stateEvents.injuryDesc')">
          <el-input v-model="form.injury_desc" />
        </el-form-item>

        <!-- 备注:除 injury 外都显示 -->
        <el-form-item v-if="form.kind !== 'injury'" :label="t('stateEvents.note')">
          <el-input
            v-model="form.note"
            type="textarea"
            :rows="2"
            :placeholder="t('stateEvents.notePlaceholder')"
          />
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
.state-events {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px dashed #e5e6eb;
}
.header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 10px;
  gap: 12px;
}
.header .title {
  font-size: 13px;
  font-weight: 600;
  color: #4e5969;
}
.header .hint {
  font-size: 12px;
  color: #86909c;
  margin-top: 2px;
  line-height: 1.5;
}
.snapshot {
  background: #fafbfc;
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 12px;
}
.snap-title {
  font-size: 12px;
  font-weight: 600;
  color: #86909c;
  margin-bottom: 6px;
}
.snap-none {
  color: #c9cdd4;
  font-size: 12px;
}
.snap-rows {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.snap-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 12px;
}
.snap-key {
  color: #86909c;
  min-width: 60px;
}
.snap-tag {
  margin-right: 4px;
}
.empty {
  text-align: center;
  color: #c9cdd4;
  font-size: 12px;
  padding: 16px 0;
}
.event-list {
  display: flex;
  flex-direction: column;
}
.event-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 4px;
  border-bottom: 1px solid #f2f3f5;
  cursor: pointer;
  font-size: 13px;
}
.event-row:hover {
  background: #fafbfc;
}
.ev-chapter {
  color: #86909c;
  font-size: 12px;
  flex-shrink: 0;
  min-width: 100px;
}
.ev-brief {
  flex: 1;
  color: #1f2329;
}
</style>
