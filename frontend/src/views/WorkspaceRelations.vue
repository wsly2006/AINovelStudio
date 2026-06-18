<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, MagicStick, Right } from '@element-plus/icons-vue'
import { relationsApi } from '../api/analysis'
import { useCharactersStore } from '../stores/characters'
import { streamProgressSSE } from '../api/sse'

const route = useRoute()
const { t } = useI18n()
const charsStore = useCharactersStore()

const projectId = computed(() => Number(route.params.id))
const relations = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const extracting = ref(false)
const extractProgress = ref({ index: 0, total: 0, title: '' })

const form = ref({ from_id: null, to_id: null, type: '', description: '' })
const editingId = ref(null)

const charById = computed(() => {
  const m = {}
  for (const c of charsStore.items) m[c.id] = c
  return m
})

async function loadRelations() {
  loading.value = true
  try {
    relations.value = await relationsApi.list(projectId.value)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (!charsStore.items.length) await charsStore.load(projectId.value)
  await loadRelations()
})

function openNew() {
  editingId.value = null
  form.value = { from_id: null, to_id: null, type: '', description: '' }
  dialogVisible.value = true
}

function openEdit(r) {
  editingId.value = r.id
  form.value = {
    from_id: r.from_id,
    to_id: r.to_id,
    type: r.type,
    description: r.description || '',
  }
  dialogVisible.value = true
}

async function onSubmit() {
  if (!form.value.from_id || !form.value.to_id || !form.value.type.trim()) {
    ElMessage.warning('请填写完整')
    return
  }
  try {
    if (editingId.value) {
      await relationsApi.update(editingId.value, {
        type: form.value.type,
        description: form.value.description || null,
      })
    } else {
      await relationsApi.create(projectId.value, {
        from_id: form.value.from_id,
        to_id: form.value.to_id,
        type: form.value.type,
        description: form.value.description || null,
      })
    }
    dialogVisible.value = false
    await loadRelations()
    ElMessage.success(t('relations.saved'))
  } catch (e) {
    ElMessage.error(e.message || t('common.failed'))
  }
}

async function onDelete(r) {
  try {
    await ElMessageBox.confirm(t('relations.deleteConfirm'), t('relations.deleteTitle'), {
      type: 'warning',
      confirmButtonText: t('common.delete'),
      cancelButtonText: t('common.cancel'),
    })
  } catch {
    return
  }
  try {
    await relationsApi.remove(r.id)
    await loadRelations()
    ElMessage.success(t('relations.deleted'))
  } catch (e) {
    ElMessage.error(e.message || t('common.failed'))
  }
}

async function onExtract() {
  if (charsStore.items.length < 2) {
    ElMessage.warning(t('relations.needCharacters'))
    return
  }
  extracting.value = true
  extractProgress.value = { index: 0, total: 0, title: '' }

  let extracted = 0
  await streamProgressSSE(
    relationsApi.extractUrl(projectId.value),
    {},
    {
      onStart: ({ total }) => (extractProgress.value = { index: 0, total, title: '' }),
      onProgress: ({ index, total, title }) =>
        (extractProgress.value = { index, total, title: title || '' }),
      onDone: (data) => {
        extracted = data.extracted || 0
      },
      onError: (msg) => ElMessage.error(`${t('characters.extractFailed')}: ${msg}`),
    }
  )

  extracting.value = false
  await loadRelations()
  ElMessage.success(t('relations.extractDone', { n: extracted }))
}

function nameOf(id) {
  return charById.value[id]?.name || `#${id}`
}
</script>

<template>
  <div class="relations-page" v-loading="loading">
    <header class="header">
      <span class="title">{{ t('relations.pageTitle') }} ({{ relations.length }})</span>
      <div class="actions">
        <el-button :icon="MagicStick" :loading="extracting" @click="onExtract">
          {{ t('relations.extract') }}
        </el-button>
        <el-button type="primary" :icon="Plus" @click="openNew">
          {{ t('relations.newRelation') }}
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

    <div v-if="relations.length === 0 && !loading" class="empty">{{ t('relations.empty') }}</div>

    <div class="grid">
      <div v-for="r in relations" :key="r.id" class="rel-card" @click="openEdit(r)">
        <div class="row">
          <span class="name">{{ nameOf(r.from_id) }}</span>
          <span class="arrow"><el-icon><Right /></el-icon></span>
          <span class="type">{{ r.type }}</span>
          <span class="arrow"><el-icon><Right /></el-icon></span>
          <span class="name">{{ nameOf(r.to_id) }}</span>
          <span class="spacer" />
          <el-button text size="small" type="danger" @click.stop="onDelete(r)">
            {{ t('common.delete') }}
          </el-button>
        </div>
        <div v-if="r.description" class="desc">{{ r.description }}</div>
      </div>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? t('common.edit') : t('relations.newRelation')"
      width="480px"
    >
      <el-form label-position="top">
        <el-form-item :label="t('relations.fromLabel')" required>
          <el-select
            v-model="form.from_id"
            :disabled="!!editingId"
            placeholder=" "
            style="width: 100%"
            filterable
          >
            <el-option v-for="c in charsStore.items" :key="c.id" :value="c.id" :label="c.name" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('relations.toLabel')" required>
          <el-select
            v-model="form.to_id"
            :disabled="!!editingId"
            placeholder=" "
            style="width: 100%"
            filterable
          >
            <el-option
              v-for="c in charsStore.items"
              :key="c.id"
              :value="c.id"
              :label="c.name"
              :disabled="c.id === form.from_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('relations.typeLabel')" required>
          <el-input v-model="form.type" :placeholder="t('relations.typePlaceholder')" maxlength="40" />
        </el-form-item>
        <el-form-item :label="t('relations.descLabel')">
          <el-input v-model="form.description" type="textarea" :rows="3" />
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
.relations-page {
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
.empty {
  text-align: center;
  color: #86909c;
  padding: 60px 16px;
  font-size: 13px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
  gap: 12px;
}
.rel-card {
  background: #fff;
  border-radius: 10px;
  padding: 12px 14px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: border-color 0.1s;
}
.rel-card:hover {
  border-color: #c9d2ff;
}
.rel-card .row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.rel-card .name {
  font-weight: 600;
  color: #1f2329;
}
.rel-card .arrow {
  color: #c9cdd4;
}
.rel-card .type {
  background: #ecf5ff;
  color: #4080ff;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
}
.rel-card .spacer {
  flex: 1;
}
.rel-card .desc {
  color: #4e5969;
  font-size: 13px;
  margin-top: 6px;
  line-height: 1.5;
}
</style>
