<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useLaddersStore } from '../stores/ladders'

const route = useRoute()
const { t } = useI18n()
const store = useLaddersStore()

const projectId = computed(() => Number(route.params.id))
const dialogVisible = ref(false)
const editingId = ref(null)
const form = ref({ name: '', description: '', tiers: [] })

onMounted(() => store.load(projectId.value))

function openNew() {
  editingId.value = null
  form.value = { name: '', description: '', tiers: [] }
  dialogVisible.value = true
}

function openEdit(l) {
  editingId.value = l.id
  form.value = { name: l.name, description: l.description || '', tiers: [...(l.tiers || [])] }
  dialogVisible.value = true
}

async function onSubmit() {
  if (!form.value.name.trim()) {
    ElMessage.warning(t('ladders.fieldNamePlaceholder'))
    return
  }
  try {
    const payload = {
      name: form.value.name,
      description: form.value.description || null,
      tiers: form.value.tiers,
    }
    if (editingId.value) await store.update(editingId.value, payload)
    else await store.create(payload)
    dialogVisible.value = false
    ElMessage.success(t('ladders.saved'))
  } catch (e) {
    ElMessage.error(e.message || t('common.failed'))
  }
}

async function onDelete(l) {
  try {
    await ElMessageBox.confirm(
      t('ladders.deleteConfirm', { name: l.name }),
      t('ladders.deleteTitle'),
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
    await store.remove(l.id)
    ElMessage.success(t('ladders.deleted'))
  } catch (e) {
    ElMessage.error(e.message || t('common.failed'))
  }
}
</script>

<template>
  <div class="ladders-page" v-loading="store.loading">
    <header class="header">
      <div>
        <div class="title">{{ t('ladders.pageTitle') }} ({{ store.items.length }})</div>
        <div class="hint">{{ t('ladders.pageHint') }}</div>
      </div>
      <el-button type="primary" :icon="Plus" @click="openNew">
        {{ t('ladders.newLadder') }}
      </el-button>
    </header>

    <div v-if="store.items.length === 0 && !store.loading" class="empty">
      {{ t('ladders.empty') }}
    </div>

    <div class="grid">
      <div
        v-for="l in store.items"
        :key="l.id"
        class="ladder-card"
        @click="openEdit(l)"
      >
        <div class="row1">
          <span class="name">{{ l.name }}</span>
          <span class="count">{{ t('ladders.tierCount', { n: l.tiers?.length || 0 }) }}</span>
          <el-button text size="small" type="danger" @click.stop="onDelete(l)">
            {{ t('common.delete') }}
          </el-button>
        </div>
        <div v-if="l.description" class="desc">{{ l.description }}</div>
        <div v-if="l.tiers?.length" class="tiers">
          <span v-for="(tier, idx) in l.tiers" :key="idx" class="tier">
            <span class="tier-idx">{{ idx + 1 }}</span>
            <span class="tier-name">{{ tier }}</span>
          </span>
        </div>
      </div>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? t('common.edit') : t('ladders.newLadder')"
      width="560px"
    >
      <el-form label-position="top">
        <el-form-item :label="t('ladders.fieldName')" required>
          <el-input
            v-model="form.name"
            :placeholder="t('ladders.fieldNamePlaceholder')"
            maxlength="60"
            show-word-limit
          />
        </el-form-item>
        <el-form-item :label="t('ladders.fieldDescription')">
          <el-input v-model="form.description" type="textarea" :rows="2" maxlength="400" />
        </el-form-item>
        <el-form-item :label="t('ladders.fieldTiers')">
          <el-select
            v-model="form.tiers"
            multiple
            filterable
            allow-create
            default-first-option
            :placeholder="t('ladders.fieldTiersHint')"
            style="width: 100%"
          >
            <el-option v-for="tier in form.tiers" :key="tier" :label="tier" :value="tier" />
          </el-select>
          <div class="form-hint">{{ t('ladders.fieldTiersHint') }}</div>
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
.ladders-page {
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
.empty {
  text-align: center;
  color: #86909c;
  padding: 60px 16px;
  font-size: 13px;
  line-height: 1.6;
}
.grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}
.ladder-card {
  background: #fff;
  border-radius: 10px;
  padding: 12px 16px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: border-color 0.1s;
}
.ladder-card:hover {
  border-color: #c9d2ff;
}
.row1 {
  display: flex;
  align-items: center;
  gap: 10px;
}
.name {
  font-size: 14px;
  font-weight: 600;
  color: #1f2329;
  flex-shrink: 0;
}
.count {
  font-size: 12px;
  color: #86909c;
  flex: 1;
}
.desc {
  font-size: 12px;
  color: #4e5969;
  margin-top: 6px;
}
.tiers {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}
.tier {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: #f5f7fa;
  padding: 3px 8px;
  border-radius: 12px;
  font-size: 12px;
}
.tier-idx {
  background: #4080ff;
  color: #fff;
  border-radius: 50%;
  width: 16px;
  height: 16px;
  font-size: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-variant-numeric: tabular-nums;
}
.tier-name {
  color: #1f2329;
}
.form-hint {
  font-size: 12px;
  color: #86909c;
  margin-top: 4px;
}
</style>
