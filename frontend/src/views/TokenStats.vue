<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Refresh } from '@element-plus/icons-vue'
import { statsApi } from '../api/stats'

const { t } = useI18n()
const router = useRouter()
const today = new Date().toISOString().slice(0, 10)
const date = ref(today)
const loading = ref(false)
const data = ref(null)

async function load() {
  loading.value = true
  try {
    data.value = await statsApi.tokens(date.value)
  } catch (e) {
    ElMessage.error(e.message || t('tokenStats.loadFailed'))
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(date, load)

function fmt(n) {
  if (n === null || n === undefined) return '—'
  return Number(n).toLocaleString()
}

function fmtMs(n) {
  if (!n) return '—'
  if (n < 1000) return `${n} ms`
  return `${(n / 1000).toFixed(2)} s`
}

function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleTimeString('zh-CN', { hour12: false })
}

const summary = computed(() => data.value?.summary || null)
const byScene = computed(() => data.value?.by_scene || [])
const byModel = computed(() => data.value?.by_model || [])
const byHour = computed(() => data.value?.by_hour || [])
const recent = computed(() => data.value?.recent || [])

function pct(value, max) {
  if (!max) return 0
  return Math.max(2, Math.round((value / max) * 100))
}
const sceneMax = computed(() => Math.max(1, ...byScene.value.map((b) => b.total_tokens)))
const modelMax = computed(() => Math.max(1, ...byModel.value.map((b) => b.total_tokens)))
const hourMax = computed(() => Math.max(1, ...byHour.value.map((b) => b.total_tokens)))
</script>

<template>
  <div class="token-stats" v-loading="loading">
    <header class="topbar">
      <el-button text :icon="ArrowLeft" @click="router.push('/')">{{ t('tokenStats.backHome') }}</el-button>
      <h1 class="title">{{ t('tokenStats.pageTitle') }}</h1>
      <span class="spacer" />
      <el-date-picker
        v-model="date"
        type="date"
        value-format="YYYY-MM-DD"
        :clearable="false"
        :disabled-date="(d) => d > new Date()"
      />
      <el-button :icon="Refresh" @click="load">{{ t('common.refresh') }}</el-button>
    </header>

    <main class="content">
      <section class="cards">
        <div class="card">
          <div class="card-label">{{ t('tokenStats.cardCalls') }}</div>
          <div class="card-value">{{ fmt(summary?.call_count) }}</div>
          <div class="card-foot">{{ t('tokenStats.cardErrors', { n: fmt(summary?.error_count) }) }}</div>
        </div>
        <div class="card">
          <div class="card-label">{{ t('tokenStats.cardTotal') }}</div>
          <div class="card-value">{{ fmt(summary?.total_tokens) }}</div>
          <div class="card-foot">
            {{ t('tokenStats.cardTotalSub', { prompt: fmt(summary?.prompt_tokens), completion: fmt(summary?.completion_tokens) }) }}
          </div>
        </div>
        <div class="card">
          <div class="card-label">{{ t('tokenStats.cardPrompt') }}</div>
          <div class="card-value">{{ fmt(summary?.prompt_tokens) }}</div>
        </div>
        <div class="card">
          <div class="card-label">{{ t('tokenStats.cardCompletion') }}</div>
          <div class="card-value">{{ fmt(summary?.completion_tokens) }}</div>
        </div>
        <div class="card">
          <div class="card-label">{{ t('tokenStats.cardAvg') }}</div>
          <div class="card-value">{{ fmtMs(summary?.avg_duration_ms) }}</div>
        </div>
      </section>

      <section class="grid-3">
        <div class="panel">
          <div class="panel-title">{{ t('tokenStats.panelByScene') }}</div>
          <div v-if="!byScene.length" class="empty">{{ t('tokenStats.empty') }}</div>
          <ul v-else class="bar-list">
            <li v-for="b in byScene" :key="b.key">
              <div class="bar-row">
                <span class="bar-key">{{ b.key }}</span>
                <span class="bar-val">{{ fmt(b.total_tokens) }}</span>
              </div>
              <div class="bar">
                <div class="bar-fill" :style="{ width: pct(b.total_tokens, sceneMax) + '%' }" />
              </div>
              <div class="bar-sub">
                {{ t('tokenStats.barCallsDetail', { n: b.call_count, prompt: fmt(b.prompt_tokens), completion: fmt(b.completion_tokens) }) }}
              </div>
            </li>
          </ul>
        </div>

        <div class="panel">
          <div class="panel-title">{{ t('tokenStats.panelByModel') }}</div>
          <div v-if="!byModel.length" class="empty">{{ t('tokenStats.empty') }}</div>
          <ul v-else class="bar-list">
            <li v-for="b in byModel" :key="b.key">
              <div class="bar-row">
                <span class="bar-key">{{ b.key }}</span>
                <span class="bar-val">{{ fmt(b.total_tokens) }}</span>
              </div>
              <div class="bar">
                <div class="bar-fill model" :style="{ width: pct(b.total_tokens, modelMax) + '%' }" />
              </div>
              <div class="bar-sub">{{ t('tokenStats.barCalls', { n: b.call_count }) }}</div>
            </li>
          </ul>
        </div>

        <div class="panel">
          <div class="panel-title">{{ t('tokenStats.panelByHour') }}</div>
          <div v-if="!byHour.length" class="empty">{{ t('tokenStats.empty') }}</div>
          <ul v-else class="bar-list">
            <li v-for="b in byHour" :key="b.key">
              <div class="bar-row">
                <span class="bar-key">{{ b.key }}:00</span>
                <span class="bar-val">{{ fmt(b.total_tokens) }}</span>
              </div>
              <div class="bar">
                <div class="bar-fill hour" :style="{ width: pct(b.total_tokens, hourMax) + '%' }" />
              </div>
              <div class="bar-sub">{{ t('tokenStats.barCalls', { n: b.call_count }) }}</div>
            </li>
          </ul>
        </div>
      </section>

      <section class="panel">
        <div class="panel-title">{{ t('tokenStats.panelRecent') }}</div>
        <el-table :data="recent" size="small" stripe>
          <el-table-column :label="t('tokenStats.colTime')" width="100">
            <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column prop="scene" :label="t('tokenStats.colScene')" width="170" />
          <el-table-column prop="model" :label="t('tokenStats.colModel')" min-width="180" show-overflow-tooltip />
          <el-table-column :label="t('tokenStats.colStream')" width="60">
            <template #default="{ row }">{{ row.stream ? t('common.yes') : t('common.no') }}</template>
          </el-table-column>
          <el-table-column :label="t('tokenStats.colPrompt')" width="90">
            <template #default="{ row }">{{ fmt(row.prompt_tokens) }}</template>
          </el-table-column>
          <el-table-column :label="t('tokenStats.colCompletion')" width="90">
            <template #default="{ row }">{{ fmt(row.completion_tokens) }}</template>
          </el-table-column>
          <el-table-column :label="t('tokenStats.colTotal')" width="100">
            <template #default="{ row }">{{ fmt(row.total_tokens) }}</template>
          </el-table-column>
          <el-table-column :label="t('tokenStats.colDuration')" width="90">
            <template #default="{ row }">{{ fmtMs(row.duration_ms) }}</template>
          </el-table-column>
          <el-table-column :label="t('tokenStats.colStatus')" width="100">
            <template #default="{ row }">
              <el-tag v-if="row.status === 'ok'" type="success" size="small">{{ t('tokenStats.statusOk') }}</el-tag>
              <el-tag v-else type="danger" size="small">{{ t('tokenStats.statusFail') }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('tokenStats.colError')" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">{{ row.error || '' }}</template>
          </el-table-column>
        </el-table>
      </section>
    </main>
  </div>
</template>

<style scoped>
.token-stats {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
}
.topbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: #fff;
  border-bottom: 1px solid #e5e6eb;
}
.topbar .title {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
  color: #1f2329;
}
.topbar .spacer {
  flex: 1;
}
.content {
  flex: 1;
  padding: 20px 24px 32px;
  max-width: 1280px;
  width: 100%;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}
.card {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 10px;
  padding: 14px 16px;
}
.card-label {
  font-size: 12px;
  color: #86909c;
}
.card-value {
  margin-top: 6px;
  font-size: 24px;
  font-weight: 600;
  color: #1f2329;
  font-variant-numeric: tabular-nums;
}
.card-foot {
  margin-top: 4px;
  font-size: 12px;
  color: #86909c;
}
.grid-3 {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}
.panel {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 10px;
  padding: 14px 16px;
}
.panel-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 10px;
  color: #1f2329;
}
.empty {
  font-size: 12px;
  color: #86909c;
  padding: 12px 0;
}
.bar-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.bar-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  font-size: 12px;
}
.bar-key {
  color: #1f2329;
  font-weight: 500;
}
.bar-val {
  color: #1f2329;
  font-variant-numeric: tabular-nums;
}
.bar {
  margin-top: 4px;
  height: 6px;
  background: #f0f2f5;
  border-radius: 3px;
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #5b8def, #7c3aed);
}
.bar-fill.model {
  background: linear-gradient(90deg, #14b8a6, #5b8def);
}
.bar-fill.hour {
  background: linear-gradient(90deg, #f59e0b, #ec4899);
}
.bar-sub {
  margin-top: 3px;
  font-size: 11px;
  color: #86909c;
}
</style>
