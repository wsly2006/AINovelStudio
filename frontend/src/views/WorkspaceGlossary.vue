<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Download, Lock } from '@element-plus/icons-vue'
import { useGlossaryStore } from '../stores/glossary'
import GlossaryEntryDialog from '../components/GlossaryEntryDialog.vue'

const route = useRoute()
const { t } = useI18n()
const store = useGlossaryStore()

const projectId = computed(() => Number(route.params.id))

const filterLang = ref('en-US')
const filterType = ref('')  // '' = 全部
const search = ref('')

const dialogVisible = ref(false)
const dialogEditingId = ref(null)
const dialogInitial = ref(null)

const seedDialogVisible = ref(false)
const seedOverwrite = ref(false)
const seedSubmitting = ref(false)

const TYPE_OPTIONS = ['person', 'place', 'org', 'term', 'skill', 'item', 'other']
const LANG_OPTIONS = [
  { value: 'en-US', label: 'English' },
  { value: 'es-ES', label: 'Español' },
  { value: 'id-ID', label: 'Indonesia' },
  { value: 'ja-JP', label: '日本語' },
  { value: 'ko-KR', label: '한국어' },
  { value: 'vi-VN', label: 'Tiếng Việt' },
]

async function reload() {
  await store.load(projectId.value, { target_lang: filterLang.value })
}

onMounted(async () => {
  await reload()
})

// 切换目标语言时重新拉(类型 + 搜索是前端过滤,不重拉)
watch(filterLang, () => {
  reload()
})

const filteredItems = computed(() => {
  const kw = search.value.trim().toLowerCase()
  return store.items.filter((it) => {
    if (filterType.value && it.entry_type !== filterType.value) return false
    if (kw) {
      const hay = `${it.source} ${it.target}`.toLowerCase()
      if (!hay.includes(kw)) return false
    }
    return true
  })
})

function openNew() {
  dialogEditingId.value = null
  dialogInitial.value = {
    source: '',
    target: '',
    target_lang: filterLang.value,
    entry_type: filterType.value || 'person',
  }
  dialogVisible.value = true
}

function openEdit(row) {
  dialogEditingId.value = row.id
  dialogInitial.value = { ...row }
  dialogVisible.value = true
}

async function onDialogSubmit(payload) {
  try {
    if (dialogEditingId.value) {
      await store.update(dialogEditingId.value, payload)
    } else {
      await store.create(payload)
    }
    ElMessage.success(t('glossary.saved'))
  } catch (e) {
    const detail = e?.response?.data?.detail
    const status = e?.response?.status
    if (status === 409) {
      ElMessage.error(t('glossary.conflictMessage'))
    } else {
      ElMessage.error(detail || e.message || t('common.failed'))
    }
    throw e
  }
}

async function onDelete(row) {
  try {
    await ElMessageBox.confirm(
      t('glossary.deleteConfirm', { source: row.source }),
      t('glossary.deleteTitle'),
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
    await store.remove(row.id)
    ElMessage.success(t('glossary.deleted'))
  } catch (e) {
    ElMessage.error(e.message || t('common.failed'))
  }
}

function openSeedDialog() {
  seedOverwrite.value = false
  seedDialogVisible.value = true
}

async function onConfirmSeed() {
  if (seedSubmitting.value) return
  seedSubmitting.value = true
  try {
    const result = await store.seed({
      target_lang: filterLang.value,
      overwrite: seedOverwrite.value,
    })
    seedDialogVisible.value = false
    ElMessage.success(
      t('glossary.seedDoneSummary', {
        created: result.created,
        skipped: result.skipped,
        updated: result.updated,
      })
    )
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e.message || t('glossary.seedFailed'))
  } finally {
    seedSubmitting.value = false
  }
}

async function onToggleLock(row) {
  try {
    await store.update(row.id, { locked: !row.locked })
  } catch (e) {
    ElMessage.error(e.message || t('common.failed'))
  }
}
</script>

<template>
  <div class="glossary-page" v-loading="store.loading">
    <header class="header">
      <div class="title-block">
        <span class="title">
          {{ t('glossary.pageTitle') }}
          <span class="count">({{ filteredItems.length }} / {{ store.items.length }})</span>
        </span>
        <span class="hint">{{ t('glossary.pageHint') }}</span>
      </div>
      <div class="actions">
        <el-button :icon="Download" @click="openSeedDialog">
          {{ t('glossary.seedFromProject') }}
        </el-button>
        <el-button type="primary" :icon="Plus" @click="openNew">
          {{ t('glossary.newEntry') }}
        </el-button>
      </div>
    </header>

    <div class="filters">
      <el-select v-model="filterLang" class="lang-select">
        <el-option
          v-for="opt in LANG_OPTIONS"
          :key="opt.value"
          :label="opt.label"
          :value="opt.value"
        />
      </el-select>
      <el-radio-group v-model="filterType" size="small">
        <el-radio-button label="">{{ t('glossary.filterAllTypes') }}</el-radio-button>
        <el-radio-button
          v-for="ty in TYPE_OPTIONS"
          :key="ty"
          :label="ty"
        >
          {{ t(`glossary.typeOptions.${ty}`) }}
        </el-radio-button>
      </el-radio-group>
      <el-input
        v-model="search"
        :placeholder="t('glossary.filterSearchPlaceholder')"
        clearable
        class="search-input"
      />
    </div>

    <div v-if="store.items.length === 0 && !store.loading" class="empty">
      {{ t('glossary.empty') }}
    </div>

    <el-table
      v-else
      :data="filteredItems"
      stripe
      class="table"
      @row-dblclick="openEdit"
    >
      <el-table-column
        prop="source"
        :label="t('glossary.columnSource')"
        min-width="160"
      />
      <el-table-column :label="t('glossary.columnTarget')" min-width="200">
        <template #default="{ row }">
          <span v-if="row.target" class="target-text">{{ row.target }}</span>
          <span v-else class="target-empty">{{ t('glossary.targetEmptyHint') }}</span>
        </template>
      </el-table-column>
      <el-table-column :label="t('glossary.columnType')" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="row.entry_type === 'person' ? 'primary' : 'info'" effect="plain">
            {{ t(`glossary.typeOptions.${row.entry_type}`) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="t('glossary.columnLocked')" width="76" align="center">
        <template #default="{ row }">
          <el-button
            text
            size="small"
            :type="row.locked ? 'warning' : 'default'"
            :icon="Lock"
            @click="onToggleLock(row)"
          />
        </template>
      </el-table-column>
      <el-table-column :label="t('glossary.columnActions')" width="148" align="right">
        <template #default="{ row }">
          <el-button text size="small" @click="openEdit(row)">
            {{ t('common.edit') }}
          </el-button>
          <el-button text size="small" type="danger" @click="onDelete(row)">
            {{ t('common.delete') }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <GlossaryEntryDialog
      v-model="dialogVisible"
      :editing-id="dialogEditingId"
      :initial="dialogInitial"
      @submit="onDialogSubmit"
    />

    <el-dialog
      v-model="seedDialogVisible"
      :title="t('glossary.seedDialogTitle')"
      width="480px"
    >
      <p class="seed-hint">{{ t('glossary.seedDialogHint') }}</p>
      <el-form label-position="top">
        <el-form-item :label="t('glossary.fieldTargetLang')">
          <el-select v-model="filterLang" style="width: 100%">
            <el-option
              v-for="opt in LANG_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="seedOverwrite">
            {{ t('glossary.seedOverwriteCheckbox') }}
          </el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="seedDialogVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="seedSubmitting" @click="onConfirmSeed">
          {{ t('common.confirm') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.glossary-page {
  flex: 1;
  overflow: auto;
  padding: 16px 24px;
}
.header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 12px;
  gap: 12px;
  flex-wrap: wrap;
}
.title-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.title {
  font-size: 15px;
  font-weight: 600;
  color: #1f2329;
}
.count {
  font-weight: 400;
  color: #86909c;
  font-size: 13px;
  margin-left: 4px;
}
.hint {
  font-size: 12px;
  color: #86909c;
}
.actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.filters {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.lang-select {
  width: 160px;
}
.search-input {
  width: 240px;
  margin-left: auto;
}
.empty {
  text-align: center;
  color: #86909c;
  padding: 60px 16px;
  font-size: 13px;
}
.table {
  background: #fff;
  border-radius: 8px;
}
.target-text {
  color: #1f2329;
}
.target-empty {
  color: #c0c4cc;
  font-style: italic;
  font-size: 12px;
}
.seed-hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: #4e5969;
  line-height: 1.6;
}
</style>
