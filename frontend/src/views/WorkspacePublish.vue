<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useWorkspaceStore } from '../stores/workspace'
import { projectsApi } from '../api/projects'
import { platformsApi } from '../api/platforms'

const { t } = useI18n()
const store = useWorkspaceStore()

const platforms = ref([])
const loadingPlatforms = ref(false)

const form = ref({
  pen_name: '',
  series_name: '',
  series_index: null,
  blurb: '',
  keywords: [],
  categories: [],
  target_platform_codes: [],
})
const keywordInput = ref('')
const categoryInput = ref('')
const submitting = ref(false)

// 取目标平台 schema 的并集,关键词上限按所选平台中最严的取
const activePlatforms = computed(() =>
  platforms.value.filter((p) => form.value.target_platform_codes.includes(p.code))
)

const keywordsLimit = computed(() => {
  let limit = null
  for (const p of activePlatforms.value) {
    for (const f of p.metadata_schema || []) {
      if (f.key === 'keywords' && f.max_count) {
        limit = limit == null ? f.max_count : Math.min(limit, f.max_count)
      }
    }
  }
  return limit
})

const categoriesLimit = computed(() => {
  let limit = null
  for (const p of activePlatforms.value) {
    for (const f of p.metadata_schema || []) {
      if (f.key === 'categories' && f.max_count) {
        limit = limit == null ? f.max_count : Math.min(limit, f.max_count)
      }
    }
  }
  return limit
})

const blurbLimit = computed(() => {
  let limit = null
  for (const p of activePlatforms.value) {
    for (const f of p.metadata_schema || []) {
      if (f.key === 'blurb' && f.max_len) {
        limit = limit == null ? f.max_len : Math.min(limit, f.max_len)
      }
    }
  }
  return limit
})

async function loadPlatforms() {
  loadingPlatforms.value = true
  try {
    platforms.value = await platformsApi.list()
  } catch (e) {
    ElMessage.error(e.message || t('publish.loadPlatformsFailed'))
  } finally {
    loadingPlatforms.value = false
  }
}

function fillFromProject(project) {
  if (!project) return
  form.value = {
    pen_name: project.pen_name || '',
    series_name: project.series_name || '',
    series_index: project.series_index ?? null,
    blurb: project.blurb || '',
    keywords: Array.isArray(project.keywords) ? project.keywords.slice() : [],
    categories: Array.isArray(project.categories) ? project.categories.slice() : [],
    target_platform_codes: Array.isArray(project.target_platform_codes)
      ? project.target_platform_codes.slice()
      : [],
  }
}

watch(() => store.project, fillFromProject, { immediate: true })

onMounted(loadPlatforms)

function addKeyword() {
  const v = keywordInput.value.trim()
  if (!v) return
  if (form.value.keywords.includes(v)) {
    keywordInput.value = ''
    return
  }
  form.value.keywords.push(v)
  keywordInput.value = ''
}

function removeKeyword(idx) {
  form.value.keywords.splice(idx, 1)
}

function addCategory() {
  const v = categoryInput.value.trim()
  if (!v) return
  if (form.value.categories.includes(v)) {
    categoryInput.value = ''
    return
  }
  form.value.categories.push(v)
  categoryInput.value = ''
}

function removeCategory(idx) {
  form.value.categories.splice(idx, 1)
}

function togglePlatform(code) {
  const idx = form.value.target_platform_codes.indexOf(code)
  if (idx >= 0) form.value.target_platform_codes.splice(idx, 1)
  else form.value.target_platform_codes.push(code)
}

const groupedPlatforms = computed(() => {
  const cn = []
  const global = []
  const other = []
  for (const p of platforms.value) {
    if (p.region === 'cn') cn.push(p)
    else if (p.region === 'global') global.push(p)
    else other.push(p)
  }
  return { cn, global, other }
})

async function onSave() {
  if (!store.project) return
  submitting.value = true
  try {
    const payload = {
      pen_name: form.value.pen_name?.trim() || null,
      series_name: form.value.series_name?.trim() || null,
      series_index: form.value.series_index || null,
      blurb: form.value.blurb?.trim() || null,
      keywords: form.value.keywords,
      categories: form.value.categories,
      target_platform_codes: form.value.target_platform_codes,
    }
    const updated = await projectsApi.update(store.project.id, payload)
    store.project = { ...store.project, ...updated }
    ElMessage.success(t('publish.saved'))
  } catch (e) {
    ElMessage.error(e.message || t('common.failed'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="publish-page">
    <div class="header">
      <h2>{{ t('publish.pageTitle') }}</h2>
      <div class="hint">{{ t('publish.pageHint') }}</div>
    </div>

    <div class="form-grid">
      <!-- 笔名 -->
      <section class="card">
        <div class="card-title">{{ t('publish.cardPenName') }}</div>
        <el-form label-width="100px" label-position="left">
          <el-form-item :label="t('publish.penNameLabel')">
            <el-input
              v-model="form.pen_name"
              :placeholder="t('publish.penNamePlaceholder')"
              maxlength="80"
            />
          </el-form-item>
          <el-form-item :label="t('publish.seriesNameLabel')">
            <el-input
              v-model="form.series_name"
              :placeholder="t('publish.seriesNamePlaceholder')"
              maxlength="120"
            />
          </el-form-item>
          <el-form-item :label="t('publish.seriesIndexLabel')">
            <el-input-number
              v-model="form.series_index"
              :min="1"
              :max="999"
              controls-position="right"
              style="width: 140px"
            />
          </el-form-item>
        </el-form>
      </section>

      <!-- 长简介 -->
      <section class="card">
        <div class="card-title">
          {{ t('publish.cardBlurb') }}
          <span v-if="blurbLimit" class="title-hint">
            {{ t('publish.blurbLimitHint', { limit: blurbLimit }) }}
          </span>
        </div>
        <el-input
          v-model="form.blurb"
          type="textarea"
          :rows="8"
          :maxlength="blurbLimit || undefined"
          show-word-limit
          :placeholder="t('publish.blurbPlaceholder')"
          resize="vertical"
        />
      </section>

      <!-- 关键词 -->
      <section class="card">
        <div class="card-title">
          {{ t('publish.cardKeywords') }}
          <span class="title-hint">
            <template v-if="keywordsLimit"
              >{{ t('publish.keywordsLimitHint', { limit: keywordsLimit, count: form.keywords.length }) }}</template
            >
            <template v-else>{{ t('publish.keywordsCountHint', { count: form.keywords.length }) }}</template>
          </span>
        </div>
        <div class="chips">
          <el-tag
            v-for="(kw, i) in form.keywords"
            :key="kw"
            closable
            @close="removeKeyword(i)"
          >
            {{ kw }}
          </el-tag>
          <el-input
            v-model="keywordInput"
            :placeholder="t('publish.keywordsPlaceholder')"
            class="chip-input"
            size="small"
            @keyup.enter="addKeyword"
          />
        </div>
        <div
          v-if="keywordsLimit && form.keywords.length > keywordsLimit"
          class="warn"
        >
          {{ t('publish.keywordsExceeded', { limit: keywordsLimit }) }}
        </div>
      </section>

      <!-- 分类 -->
      <section class="card">
        <div class="card-title">
          {{ t('publish.cardCategories') }}
          <span class="title-hint">
            <template v-if="categoriesLimit"
              >{{ t('publish.categoriesLimitHint', { limit: categoriesLimit, count: form.categories.length }) }}</template
            >
            <template v-else>{{ t('publish.categoriesCountHint', { count: form.categories.length }) }}</template>
          </span>
        </div>
        <div class="chips">
          <el-tag
            v-for="(cat, i) in form.categories"
            :key="cat"
            type="success"
            closable
            @close="removeCategory(i)"
          >
            {{ cat }}
          </el-tag>
          <el-input
            v-model="categoryInput"
            :placeholder="t('publish.categoriesPlaceholder')"
            class="chip-input"
            size="small"
            @keyup.enter="addCategory"
          />
        </div>
        <div
          v-if="categoriesLimit && form.categories.length > categoriesLimit"
          class="warn"
        >
          {{ t('publish.categoriesExceeded', { limit: categoriesLimit }) }}
        </div>
      </section>

      <!-- 目标平台 -->
      <section class="card span-2" v-loading="loadingPlatforms">
        <div class="card-title">{{ t('publish.cardPlatforms') }}</div>
        <div class="platform-hint">
          {{ t('publish.platformsHint') }}
        </div>
        <div class="platform-group" v-if="groupedPlatforms.global.length">
          <div class="group-title">{{ t('publish.groupGlobal') }}</div>
          <div class="platform-grid">
            <button
              v-for="p in groupedPlatforms.global"
              :key="p.code"
              type="button"
              class="platform-card"
              :class="{ active: form.target_platform_codes.includes(p.code) }"
              @click="togglePlatform(p.code)"
            >
              <div class="platform-name">{{ p.name }}</div>
              <div class="platform-formats">
                {{ (p.formats || []).join(' / ') || '-' }}
              </div>
            </button>
          </div>
        </div>
        <div class="platform-group" v-if="groupedPlatforms.cn.length">
          <div class="group-title">{{ t('publish.groupCN') }}</div>
          <div class="platform-grid">
            <button
              v-for="p in groupedPlatforms.cn"
              :key="p.code"
              type="button"
              class="platform-card"
              :class="{ active: form.target_platform_codes.includes(p.code) }"
              @click="togglePlatform(p.code)"
            >
              <div class="platform-name">{{ p.name }}</div>
              <div class="platform-formats">
                {{ (p.formats || []).join(' / ') || '-' }}
              </div>
            </button>
          </div>
        </div>
        <div class="platform-group" v-if="groupedPlatforms.other.length">
          <div class="group-title">{{ t('publish.groupOther') }}</div>
          <div class="platform-grid">
            <button
              v-for="p in groupedPlatforms.other"
              :key="p.code"
              type="button"
              class="platform-card"
              :class="{ active: form.target_platform_codes.includes(p.code) }"
              @click="togglePlatform(p.code)"
            >
              <div class="platform-name">{{ p.name }}</div>
              <div class="platform-formats">
                {{ (p.formats || []).join(' / ') || '-' }}
              </div>
            </button>
          </div>
        </div>
      </section>
    </div>

    <div class="footer">
      <el-button type="primary" :loading="submitting" @click="onSave">
        {{ t('common.save') }}
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.publish-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 16px 20px;
  overflow: auto;
  background: #f5f7fa;
}
.header {
  margin-bottom: 16px;
}
.header h2 {
  margin: 0 0 4px;
  font-size: 18px;
  font-weight: 600;
  color: #1f2329;
}
.hint {
  font-size: 12px;
  color: #86909c;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
.card {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  padding: 14px 16px;
}
.card.span-2 {
  grid-column: 1 / -1;
}
.card-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2329;
  margin-bottom: 10px;
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.title-hint {
  font-size: 12px;
  font-weight: normal;
  color: #86909c;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.chip-input {
  width: 200px;
}
.warn {
  font-size: 12px;
  color: #d46b08;
  margin-top: 8px;
}
.platform-hint {
  font-size: 12px;
  color: #86909c;
  margin-bottom: 12px;
}
.platform-group {
  margin-bottom: 12px;
}
.group-title {
  font-size: 12px;
  color: #86909c;
  margin-bottom: 6px;
}
.platform-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 8px;
}
.platform-card {
  text-align: left;
  padding: 10px 12px;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
  font-family: inherit;
}
.platform-card:hover {
  border-color: #4080ff;
}
.platform-card.active {
  border-color: #4080ff;
  background: #ecf5ff;
}
.platform-name {
  font-size: 13px;
  font-weight: 600;
  color: #1f2329;
}
.platform-formats {
  font-size: 11px;
  color: #86909c;
  text-transform: uppercase;
  margin-top: 4px;
}
.footer {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
