<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Refresh } from '@element-plus/icons-vue'
import { statsApi } from '../api/stats'

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
    ElMessage.error(e.message || '加载失败')
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
      <el-button text :icon="ArrowLeft" @click="router.push('/')">返回首页</el-button>
      <h1 class="title">Token 用量统计</h1>
      <span class="spacer" />
      <el-date-picker
        v-model="date"
        type="date"
        value-format="YYYY-MM-DD"
        :clearable="false"
        :disabled-date="(d) => d > new Date()"
      />
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </header>

    <main class="content">
      <section class="cards">
        <div class="card">
          <div class="card-label">调用次数</div>
          <div class="card-value">{{ fmt(summary?.call_count) }}</div>
          <div class="card-foot">失败 {{ fmt(summary?.error_count) }}</div>
        </div>
        <div class="card">
          <div class="card-label">总 tokens</div>
          <div class="card-value">{{ fmt(summary?.total_tokens) }}</div>
          <div class="card-foot">
            输入 {{ fmt(summary?.prompt_tokens) }} / 输出 {{ fmt(summary?.completion_tokens) }}
          </div>
        </div>
        <div class="card">
          <div class="card-label">输入 tokens</div>
          <div class="card-value">{{ fmt(summary?.prompt_tokens) }}</div>
        </div>
        <div class="card">
          <div class="card-label">输出 tokens</div>
          <div class="card-value">{{ fmt(summary?.completion_tokens) }}</div>
        </div>
        <div class="card">
          <div class="card-label">平均响应</div>
          <div class="card-value">{{ fmtMs(summary?.avg_duration_ms) }}</div>
        </div>
      </section>

      <section class="grid-3">
        <div class="panel">
          <div class="panel-title">按场景</div>
          <div v-if="!byScene.length" class="empty">无数据</div>
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
                {{ b.call_count }} 次 · 入 {{ fmt(b.prompt_tokens) }} / 出 {{ fmt(b.completion_tokens) }}
              </div>
            </li>
          </ul>
        </div>

        <div class="panel">
          <div class="panel-title">按模型</div>
          <div v-if="!byModel.length" class="empty">无数据</div>
          <ul v-else class="bar-list">
            <li v-for="b in byModel" :key="b.key">
              <div class="bar-row">
                <span class="bar-key">{{ b.key }}</span>
                <span class="bar-val">{{ fmt(b.total_tokens) }}</span>
              </div>
              <div class="bar">
                <div class="bar-fill model" :style="{ width: pct(b.total_tokens, modelMax) + '%' }" />
              </div>
              <div class="bar-sub">{{ b.call_count }} 次</div>
            </li>
          </ul>
        </div>

        <div class="panel">
          <div class="panel-title">按小时</div>
          <div v-if="!byHour.length" class="empty">无数据</div>
          <ul v-else class="bar-list">
            <li v-for="b in byHour" :key="b.key">
              <div class="bar-row">
                <span class="bar-key">{{ b.key }}:00</span>
                <span class="bar-val">{{ fmt(b.total_tokens) }}</span>
              </div>
              <div class="bar">
                <div class="bar-fill hour" :style="{ width: pct(b.total_tokens, hourMax) + '%' }" />
              </div>
              <div class="bar-sub">{{ b.call_count }} 次</div>
            </li>
          </ul>
        </div>
      </section>

      <section class="panel">
        <div class="panel-title">最近调用 (最多 50 条)</div>
        <el-table :data="recent" size="small" stripe>
          <el-table-column label="时间" width="100">
            <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column prop="scene" label="场景" width="170" />
          <el-table-column prop="model" label="模型" min-width="180" show-overflow-tooltip />
          <el-table-column label="流式" width="60">
            <template #default="{ row }">{{ row.stream ? '是' : '否' }}</template>
          </el-table-column>
          <el-table-column label="入" width="90">
            <template #default="{ row }">{{ fmt(row.prompt_tokens) }}</template>
          </el-table-column>
          <el-table-column label="出" width="90">
            <template #default="{ row }">{{ fmt(row.completion_tokens) }}</template>
          </el-table-column>
          <el-table-column label="合计" width="100">
            <template #default="{ row }">{{ fmt(row.total_tokens) }}</template>
          </el-table-column>
          <el-table-column label="耗时" width="90">
            <template #default="{ row }">{{ fmtMs(row.duration_ms) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag v-if="row.status === 'ok'" type="success" size="small">成功</el-tag>
              <el-tag v-else type="danger" size="small">失败</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="错误" min-width="200" show-overflow-tooltip>
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
