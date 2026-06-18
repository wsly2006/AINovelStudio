<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, MagicStick, Delete, StarFilled } from '@element-plus/icons-vue'
import { plotThreadsApi } from '../api/plotThreads'

const route = useRoute()
const { t } = useI18n()

const projectId = computed(() => Number(route.params.id))
const items = ref([])
const loading = ref(false)
const suggesting = ref(false)
const selectedId = ref(null)

const STATUS_OPTIONS = [
  { value: 'planning', tKey: 'threads.statusPlanning', color: '#5b8def' },
  { value: 'active', tKey: 'threads.statusActive', color: '#fa8c16' },
  { value: 'resolved', tKey: 'threads.statusResolved', color: '#52c41a' },
  { value: 'abandoned', tKey: 'threads.statusAbandoned', color: '#86909c' },
]

const STATUS_META = Object.fromEntries(STATUS_OPTIONS.map((o) => [o.value, o]))

const selected = computed(
  () => items.value.find((t) => t.id === selectedId.value) || null
)

async function load() {
  loading.value = true
  try {
    items.value = await plotThreadsApi.list(projectId.value)
    if (!selectedId.value && items.value.length) {
      selectedId.value = items.value[0].id
    }
  } catch (e) {
    ElMessage.error(e.message || t('common.failed'))
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function onCreate() {
  try {
    const created = await plotThreadsApi.create(projectId.value, {
      title: '新主线',
      description: '',
      planned_arc: '',
      status: 'planning',
      importance: 3,
    })
    items.value = [...items.value, created]
    selectedId.value = created.id
    ElMessage.success(t('threads.saved'))
  } catch (e) {
    ElMessage.error(e.message || t('common.failed'))
  }
}

// 改字段就地保存。失败时回滚到上一个状态值,不让用户白填。
let saveTimer = null
function onLocalEdit() {
  clearTimeout(saveTimer)
  saveTimer = setTimeout(saveSelected, 500)
}

async function saveSelected() {
  const t_ = selected.value
  if (!t_) return
  try {
    const updated = await plotThreadsApi.update(t_.id, {
      title: t_.title,
      description: t_.description || null,
      planned_arc: t_.planned_arc || null,
      status: t_.status,
      importance: t_.importance,
    })
    const i = items.value.findIndex((x) => x.id === t_.id)
    if (i >= 0) items.value[i] = updated
  } catch (e) {
    ElMessage.error(e.message || t('common.failed'))
    await load()
  }
}

async function onDelete(thread) {
  try {
    await ElMessageBox.confirm(
      t('threads.deleteConfirm'),
      t('threads.deleteTitle'),
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
    await plotThreadsApi.remove(thread.id)
    items.value = items.value.filter((x) => x.id !== thread.id)
    if (selectedId.value === thread.id) {
      selectedId.value = items.value[0]?.id || null
    }
    ElMessage.success(t('threads.deleted'))
  } catch (e) {
    ElMessage.error(e.message || t('common.failed'))
  }
}

async function onSuggest() {
  if (suggesting.value) return
  suggesting.value = true
  const closeMsg = ElMessage({
    type: 'info',
    message: t('threads.aiSuggest') + '…',
    duration: 0,
  })
  try {
    const created = await plotThreadsApi.suggest(projectId.value)
    closeMsg.close()
    if (!Array.isArray(created) || !created.length) {
      ElMessage.warning(t('threads.aiSuggestFailed'))
      return
    }
    items.value = [...items.value, ...created]
    selectedId.value = created[0].id
    ElMessage.success(t('threads.aiSuggestSuccess', { n: created.length }))
  } catch (e) {
    closeMsg.close()
    const detail = e?.response?.data?.detail
    if (detail && (detail.includes('总纲') || detail.includes('简介'))) {
      ElMessage.warning(t('threads.aiSuggestNoSynopsis'))
    } else {
      ElMessage.error(detail || e.message || t('threads.aiSuggestFailed'))
    }
  } finally {
    suggesting.value = false
  }
}
</script>

<template>
  <div class="threads-page" v-loading="loading">
    <header class="header">
      <div class="title-block">
        <span class="title">{{ t('threads.pageTitle') }} ({{ items.length }})</span>
        <span class="hint">{{ t('threads.pageHint') }}</span>
      </div>
      <div class="actions">
        <el-button :icon="MagicStick" :loading="suggesting" @click="onSuggest">
          {{ t('threads.aiSuggest') }}
        </el-button>
        <el-button type="primary" :icon="Plus" @click="onCreate">
          {{ t('threads.newThread') }}
        </el-button>
      </div>
    </header>

    <div v-if="items.length === 0 && !loading" class="empty">
      <div class="empty-emoji">🧭</div>
      <p>{{ t('threads.empty') }}</p>
    </div>

    <div v-else class="layout">
      <!-- 左侧:主线列表 -->
      <aside class="list-pane">
        <div
          v-for="t_ in items"
          :key="t_.id"
          class="list-item"
          :class="{ active: selectedId === t_.id }"
          @click="selectedId = t_.id"
        >
          <div class="row1">
            <span
              class="status-dot"
              :style="{ background: STATUS_META[t_.status]?.color }"
            />
            <span class="item-title">{{ t_.title }}</span>
          </div>
          <div class="row2">
            <span class="status-label">{{ t(STATUS_META[t_.status]?.tKey) }}</span>
            <span class="stars">
              <el-icon v-for="n in t_.importance" :key="n"><StarFilled /></el-icon>
            </span>
          </div>
        </div>
      </aside>

      <!-- 右侧:编辑详情 -->
      <main v-if="selected" class="edit-pane">
        <div class="form-row">
          <label>{{ t('threads.titleLabel') }}</label>
          <el-input
            v-model="selected.title"
            :placeholder="t('threads.titlePlaceholder')"
            maxlength="120"
            @change="onLocalEdit"
          />
        </div>

        <div class="form-row form-row-grid">
          <div class="form-cell">
            <label>{{ t('threads.statusLabel') }}</label>
            <el-radio-group v-model="selected.status" size="default" @change="onLocalEdit">
              <el-radio-button
                v-for="opt in STATUS_OPTIONS"
                :key="opt.value"
                :value="opt.value"
              >
                {{ t(opt.tKey) }}
              </el-radio-button>
            </el-radio-group>
          </div>
          <div class="form-cell form-cell-rate">
            <label>{{ t('threads.importanceLabel') }}</label>
            <el-rate
              v-model="selected.importance"
              :max="5"
              :allow-half="false"
              @change="onLocalEdit"
            />
          </div>
        </div>

        <div class="form-row">
          <label>{{ t('threads.descLabel') }}</label>
          <el-input
            v-model="selected.description"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 5 }"
            :placeholder="t('threads.descPlaceholder')"
            maxlength="4000"
            @change="onLocalEdit"
          />
        </div>

        <div class="form-row">
          <label>{{ t('threads.arcLabel') }}</label>
          <el-input
            v-model="selected.planned_arc"
            type="textarea"
            :autosize="{ minRows: 4, maxRows: 12 }"
            :placeholder="t('threads.arcPlaceholder')"
            maxlength="8000"
            @change="onLocalEdit"
          />
        </div>

        <div class="form-row form-row-actions">
          <el-button text type="danger" :icon="Delete" @click="onDelete(selected)">
            {{ t('common.delete') }}
          </el-button>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.threads-page {
  flex: 1;
  overflow: auto;
  padding: 16px 24px;
  display: flex;
  flex-direction: column;
}
.header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
  flex-shrink: 0;
}
.title-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.title-block .title {
  font-size: 15px;
  font-weight: 600;
}
.title-block .hint {
  font-size: 12px;
  color: #86909c;
  line-height: 1.6;
}
.actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
.empty {
  text-align: center;
  color: #86909c;
  padding: 80px 16px;
}
.empty-emoji {
  font-size: 48px;
  opacity: 0.5;
  margin-bottom: 12px;
}
.layout {
  flex: 1;
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 16px;
  min-height: 0;
}
.list-pane {
  border: 1px solid #e5e6eb;
  border-radius: 10px;
  overflow: auto;
  background: #fff;
}
.list-item {
  padding: 10px 12px;
  cursor: pointer;
  border-bottom: 1px solid #f2f3f5;
  transition: background 0.12s;
}
.list-item:last-child {
  border-bottom: none;
}
.list-item:hover {
  background: #f7f8fa;
}
.list-item.active {
  background: #ecf5ff;
}
.list-item.active .item-title {
  color: #4080ff;
  font-weight: 600;
}
.row1 {
  display: flex;
  align-items: center;
  gap: 8px;
}
.row2 {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 4px;
  padding-left: 18px;
}
.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.item-title {
  flex: 1;
  font-size: 13px;
  color: #1f2329;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.status-label {
  font-size: 12px;
  color: #86909c;
}
.stars {
  color: #fadb14;
  display: inline-flex;
  gap: 1px;
  font-size: 12px;
}
.edit-pane {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 10px;
  padding: 16px 20px;
  overflow: auto;
}
.form-row {
  margin-bottom: 14px;
}
.form-row label {
  display: block;
  font-size: 12px;
  color: #4e5969;
  font-weight: 500;
  margin-bottom: 6px;
}
.form-row-grid {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 16px;
}
.form-cell-rate {
  text-align: right;
}
.form-row-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 24px;
  padding-top: 12px;
  border-top: 1px solid #f2f3f5;
}
</style>
