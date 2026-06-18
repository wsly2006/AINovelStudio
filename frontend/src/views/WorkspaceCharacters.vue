<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, MagicStick } from '@element-plus/icons-vue'
import { useCharactersStore } from '../stores/characters'
import { useWorkspaceStore } from '../stores/workspace'
import { useLaddersStore } from '../stores/ladders'
import { useWorldStore } from '../stores/world'
import CharacterCard from '../components/CharacterCard.vue'
import CharacterEditor from '../components/CharacterEditor.vue'
import CharacterExtractDrawer from '../components/CharacterExtractDrawer.vue'

const route = useRoute()
const { t } = useI18n()
const store = useCharactersStore()
const workspace = useWorkspaceStore()
const laddersStore = useLaddersStore()
const worldStore = useWorldStore()

const projectId = computed(() => Number(route.params.id))
const selectedId = ref(null)
const extractVisible = ref(false)
const draftMode = ref(false)

const selected = computed(() => {
  if (draftMode.value) return null
  return store.items.find((c) => c.id === selectedId.value) || null
})

// 进阶字段需要的列表
const ladders = computed(() => laddersStore.items)
const locations = computed(() => worldStore.items.filter((e) => e.kind === 'location'))
const allWorldEntities = computed(() => worldStore.items)
const projectChapters = computed(() => workspace.chapters)

async function load() {
  await store.load(projectId.value)
  // 进阶相关数据按需加载,失败不阻塞
  if (laddersStore.projectId !== projectId.value) {
    laddersStore.load(projectId.value).catch(() => {})
  }
  if (worldStore.projectId !== projectId.value) {
    worldStore.load(projectId.value).catch(() => {})
  }
  if (store.items.length > 0 && !selectedId.value) {
    selectedId.value = store.items[0].id
  }
}

onMounted(load)
watch(projectId, () => {
  selectedId.value = null
  load()
})

function onSelect(c) {
  draftMode.value = false
  selectedId.value = c.id
}

function onNew() {
  draftMode.value = true
  selectedId.value = null
}

async function onSave(payload) {
  try {
    if (draftMode.value) {
      const c = await store.create(payload)
      draftMode.value = false
      selectedId.value = c.id
    } else {
      await store.update(selectedId.value, payload)
    }
    ElMessage.success(t('characters.saved'))
  } catch (e) {
    ElMessage.error(e.message || t('common.failed'))
  }
}

async function onDelete(c) {
  try {
    await ElMessageBox.confirm(
      t('characters.deleteConfirm', { name: c.name }),
      t('characters.deleteTitle'),
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
    await store.remove(c.id)
    if (selectedId.value === c.id) {
      selectedId.value = store.items[0]?.id || null
    }
    ElMessage.success(t('characters.deleted'))
  } catch (e) {
    ElMessage.error(e.message || t('common.failed'))
  }
}

function onExtractClick() {
  // 没有可分析的章节时直接提示
  const hasContent = workspace.chapters.some((c) => (c.word_count || 0) > 0)
  if (!hasContent) {
    ElMessage.warning(t('characters.extractEmpty'))
    return
  }
  extractVisible.value = true
}

async function onExtractCompleted() {
  await store.load(projectId.value)
  if (store.items.length > 0 && !selectedId.value) {
    selectedId.value = store.items[0].id
  }
}
</script>

<template>
  <div class="characters-page" v-loading="store.loading">
    <aside class="list-pane">
      <div class="list-header">
        <span class="title">{{ t('characters.pageTitle') }} ({{ store.items.length }})</span>
        <div class="actions">
          <el-button :icon="MagicStick" size="small" @click="onExtractClick">
            {{ t('characters.extract') }}
          </el-button>
          <el-button type="primary" :icon="Plus" size="small" @click="onNew">
            {{ t('characters.newCharacter') }}
          </el-button>
        </div>
      </div>

      <div class="list-body">
        <div v-if="store.items.length === 0 && !draftMode" class="empty">
          {{ t('characters.empty') }}
        </div>
        <div class="cards">
          <CharacterCard
            v-for="c in store.items"
            :key="c.id"
            :character="c"
            :active="!draftMode && c.id === selectedId"
            @select="onSelect"
            @delete="onDelete"
          />
        </div>
      </div>
    </aside>

    <main class="detail-pane">
      <div v-if="!selected && !draftMode" class="placeholder">
        <div class="emoji">👤</div>
        <p>选择一个人物查看 / 编辑,或新建一个</p>
      </div>
      <CharacterEditor
        v-else
        :key="selected?.id ?? 'draft'"
        :character="selected"
        :ladders="ladders"
        :locations="locations"
        :chapters="projectChapters"
        :world-entities="allWorldEntities"
        :project-id="projectId"
        @save="onSave"
      />
    </main>

    <CharacterExtractDrawer
      v-model="extractVisible"
      :project-id="projectId"
      @completed="onExtractCompleted"
    />
  </div>
</template>

<style scoped>
.characters-page {
  flex: 1;
  display: flex;
  overflow: hidden;
}
.list-pane {
  width: 320px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: #f7f8fa;
  border-right: 1px solid #e5e6eb;
}
.list-header {
  padding: 12px 16px;
  border-bottom: 1px solid #e5e6eb;
  flex-shrink: 0;
}
.list-header .title {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #4e5969;
  margin-bottom: 8px;
}
.list-header .actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.list-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}
.cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.empty {
  color: #86909c;
  font-size: 13px;
  text-align: center;
  padding: 40px 16px;
  line-height: 1.6;
}
.detail-pane {
  flex: 1;
  overflow: hidden;
  padding: 16px 24px;
}
.placeholder {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #86909c;
}
.placeholder .emoji {
  font-size: 56px;
  margin-bottom: 12px;
  opacity: 0.6;
}
</style>
