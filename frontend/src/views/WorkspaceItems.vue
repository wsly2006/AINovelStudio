<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, MagicStick } from '@element-plus/icons-vue'
import { useItemsStore } from '../stores/items'
import { itemsApi } from '../api/items'
import { streamProgressSSE } from '../api/sse'

const route = useRoute()
const { t } = useI18n()
const store = useItemsStore()

const projectId = computed(() => Number(route.params.id))
const dialogVisible = ref(false)
const editingId = ref(null)
const extracting = ref(false)
const extractProgress = ref({ index: 0, total: 0, title: '' })

const form = ref({
  name: '',
  aliases: [],
  summary: '',
  description: '',
  tags: [],
})

onMounted(async () => {
  await store.load(projectId.value)
})

function openNew() {
  editingId.value = null
  form.value = { name: '', aliases: [], summary: '', description: '', tags: [] }
  dialogVisible.value = true
}

function openEdit(e) {
  editingId.value = e.id
  form.value = {
    name: e.name,
    aliases: [...(e.aliases || [])],
    summary: e.summary || '',
    description: e.description || '',
    tags: [...(e.tags || [])],
  }
  dialogVisible.value = true
}

async function onSubmit() {
  if (!form.value.name.trim()) {
    ElMessage.warning(t('items.fieldNamePlaceholder'))
    return
  }
  try {
    const payload = {
      name: form.value.name,
      aliases: form.value.aliases,
      summary: form.value.summary || null,
      description: form.value.description || null,
      tags: form.value.tags,
    }
    if (editingId.value) {
      await store.update(editingId.value, payload)
    } else {
      await store.create(payload)
    }
    dialogVisible.value = false
    ElMessage.success(t('items.saved'))
  } catch (e) {
    ElMessage.error(e.message || t('common.failed'))
  }
}

async function onDelete(e) {
  try {
    await ElMessageBox.confirm(
      t('items.deleteConfirm', { name: e.name }),
      t('items.deleteTitle'),
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
    await store.remove(e.id)
    ElMessage.success(t('items.deleted'))
  } catch (err) {
    ElMessage.error(err.message || t('common.failed'))
  }
}

async function onExtract() {
  extracting.value = true
  extractProgress.value = { index: 0, total: 0, title: '' }
  let extracted = 0
  await streamProgressSSE(
    itemsApi.extractUrl(projectId.value),
    { mode: 'merge' },
    {
      onStart: ({ total }) => (extractProgress.value = { index: 0, total, title: '' }),
      onProgress: ({ index, total, title }) =>
        (extractProgress.value = { index, total, title: title || '' }),
      onDone: (data) => (extracted = data.extracted || 0),
      onError: (msg) => ElMessage.error(`${t('common.failed')}: ${msg}`),
    }
  )
  extracting.value = false
  await store.load(projectId.value)
  ElMessage.success(t('items.extractDone', { n: extracted }))
}
</script>

<template>
  <div class="items-page" v-loading="store.loading">
    <header class="header">
      <span class="title">{{ t('items.pageTitle') }} ({{ store.items.length }})</span>
      <div class="actions">
        <el-button :icon="MagicStick" :loading="extracting" @click="onExtract">
          {{ t('items.extract') }}
        </el-button>
        <el-button type="primary" :icon="Plus" @click="openNew">
          {{ t('items.newItem') }}
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

    <div v-if="store.items.length === 0 && !store.loading" class="empty">
      {{ t('items.empty') }}
    </div>

    <div class="grid">
      <div
        v-for="e in store.items"
        :key="e.id"
        class="entity-card"
        @click="openEdit(e)"
      >
        <div class="row1">
          <span class="name">{{ e.name }}</span>
          <el-button text size="small" type="danger" @click.stop="onDelete(e)">
            {{ t('common.delete') }}
          </el-button>
        </div>
        <div v-if="e.aliases?.length" class="aliases">{{ e.aliases.join('、') }}</div>
        <div v-if="e.summary" class="summary">{{ e.summary }}</div>
        <div v-if="e.tags?.length" class="tags">
          <el-tag v-for="tag in e.tags" :key="tag" size="small" type="info" effect="plain">
            {{ tag }}
          </el-tag>
        </div>
      </div>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? t('common.edit') : t('items.newItem')"
      width="560px"
    >
      <el-form label-position="top">
        <el-form-item :label="t('items.fieldName')" required>
          <el-input
            v-model="form.name"
            :placeholder="t('items.fieldNamePlaceholder')"
            maxlength="120"
            show-word-limit
          />
        </el-form-item>
        <el-form-item :label="t('items.fieldAliases')">
          <el-select
            v-model="form.aliases"
            multiple
            filterable
            allow-create
            default-first-option
            :placeholder="t('items.fieldAliasesPlaceholder')"
            style="width: 100%"
          >
            <el-option v-for="a in form.aliases" :key="a" :label="a" :value="a" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('items.fieldSummary')">
          <el-input v-model="form.summary" type="textarea" :rows="2" maxlength="400" show-word-limit />
        </el-form-item>
        <el-form-item :label="t('items.fieldDescription')">
          <el-input v-model="form.description" type="textarea" :rows="6" />
        </el-form-item>
        <el-form-item :label="t('items.fieldTags')">
          <el-select
            v-model="form.tags"
            multiple
            filterable
            allow-create
            default-first-option
            :placeholder="t('items.fieldTagsPlaceholder')"
            style="width: 100%"
          >
            <el-option v-for="tag in form.tags" :key="tag" :label="tag" :value="tag" />
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
.items-page {
  flex: 1;
  overflow: auto;
  padding: 16px 24px;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  gap: 12px;
  flex-wrap: wrap;
}
.header .title {
  font-size: 15px;
  font-weight: 600;
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
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 10px;
}
.entity-card {
  background: #fff;
  border-radius: 10px;
  padding: 10px 14px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: border-color 0.1s;
}
.entity-card:hover {
  border-color: #c9d2ff;
}
.row1 {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.name {
  font-size: 14px;
  font-weight: 600;
  color: #1f2329;
}
.aliases {
  font-size: 12px;
  color: #86909c;
  margin-top: 2px;
}
.summary {
  font-size: 13px;
  color: #4e5969;
  line-height: 1.5;
  margin-top: 6px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-top: 6px;
}
</style>
