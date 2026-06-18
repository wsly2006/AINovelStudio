<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { promptsApi } from '../api/prompts'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
})
const emit = defineEmits(['update:modelValue'])

const { t } = useI18n()

const items = ref([])
const loading = ref(false)
const saving = ref(false)
const resetting = ref(false)
const activeKey = ref(null)
const draftSystem = ref('')
const draftUser = ref('')

const active = computed(() => items.value.find((i) => i.key === activeKey.value))
// 草稿是否相对当前 active 有变化(决定保存按钮是否可点)
const dirty = computed(() => {
  if (!active.value) return false
  return draftSystem.value !== active.value.system_text || draftUser.value !== active.value.user_template
})

const grouped = computed(() => {
  const groups = {
    writing: { key: 'writing', labelKey: 'prompts.groupWriting', items: [] },
    outline: { key: 'outline', labelKey: 'prompts.groupOutline', items: [] },
    extract: { key: 'extract', labelKey: 'prompts.groupExtract', items: [] },
    analysis: { key: 'analysis', labelKey: 'prompts.groupAnalysis', items: [] },
  }
  for (const it of items.value) {
    const g = groups[it.group] || groups.writing
    g.items.push(it)
  }
  return Object.values(groups).filter((g) => g.items.length > 0)
})

watch(
  () => props.modelValue,
  async (v) => {
    if (!v) return
    await refresh()
  }
)

async function refresh() {
  loading.value = true
  try {
    const data = await promptsApi.list()
    items.value = data
    if (data.length > 0) {
      // 默认选中第一项,或保留之前的选中
      const keep = data.find((i) => i.key === activeKey.value)
      const target = keep || data[0]
      selectItem(target.key)
    }
  } catch (e) {
    ElMessage.error(e.message || t('prompts.loadFailed'))
  } finally {
    loading.value = false
  }
}

// 占位符 chip 的展示文本。直接在模板里写 `{{${ph}}}` 会让 Vue 的插值分词器
// 把内层 }} 当成外层结束,所以拼接挪到 script 里。
function phLabel(ph) {
  return '{{' + ph + '}}'
}

function selectItem(key) {
  const item = items.value.find((i) => i.key === key)
  if (!item) return
  // 直接切换;未保存的草稿被丢弃。提示词改动一般幅度小,
  // 加确认弹窗反而打断节奏。
  activeKey.value = key
  draftSystem.value = item.system_text
  draftUser.value = item.user_template
}

async function onSave() {
  if (!active.value) return
  if (!draftUser.value.trim()) {
    ElMessage.warning(t('prompts.userLabel'))
    return
  }
  saving.value = true
  try {
    const updated = await promptsApi.update(active.value.key, {
      system_text: draftSystem.value,
      user_template: draftUser.value,
    })
    const idx = items.value.findIndex((i) => i.key === updated.key)
    if (idx >= 0) items.value[idx] = updated
    ElMessage.success(t('prompts.saved'))
  } catch (e) {
    ElMessage.error(e.message || t('prompts.saveFailed'))
  } finally {
    saving.value = false
  }
}

async function onReset() {
  if (!active.value) return
  try {
    await ElMessageBox.confirm(
      t('prompts.resetConfirm', { name: active.value.name }),
      t('prompts.resetConfirmTitle'),
      {
        type: 'warning',
        confirmButtonText: t('prompts.resetButton'),
        cancelButtonText: t('common.cancel'),
      }
    )
  } catch {
    return
  }
  resetting.value = true
  try {
    const updated = await promptsApi.reset(active.value.key)
    const idx = items.value.findIndex((i) => i.key === updated.key)
    if (idx >= 0) items.value[idx] = updated
    draftSystem.value = updated.system_text
    draftUser.value = updated.user_template
    ElMessage.success(t('prompts.resetDone'))
  } catch (e) {
    ElMessage.error(e.message || t('prompts.saveFailed'))
  } finally {
    resetting.value = false
  }
}

function insertPlaceholder(ph) {
  // 直接拼到 user 末尾;用户也可以手动剪切到光标处
  const token = `{{${ph}}}`
  if (draftUser.value.includes(token)) return
  draftUser.value += (draftUser.value.endsWith('\n') ? '' : '\n') + token
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    :title="t('prompts.title')"
    width="960px"
    top="6vh"
    v-loading="loading"
  >
    <div class="layout">
      <aside class="sidebar">
        <div v-for="g in grouped" :key="g.key" class="group">
          <div class="group-title">{{ t(g.labelKey) }}</div>
          <button
            v-for="it in g.items"
            :key="it.key"
            class="prompt-row"
            :class="{ active: it.key === activeKey }"
            @click="selectItem(it.key)"
          >
            <span class="prompt-name">{{ it.name }}</span>
            <span v-if="it.customized" class="badge">{{ t('prompts.customizedTag') }}</span>
          </button>
        </div>
      </aside>

      <section class="editor">
        <template v-if="active">
          <p class="desc">{{ active.description }}</p>

          <div class="field">
            <label>{{ t('prompts.systemLabel') }}</label>
            <el-input
              v-model="draftSystem"
              type="textarea"
              :rows="3"
              resize="vertical"
            />
          </div>

          <div class="field">
            <label>{{ t('prompts.userLabel') }}</label>
            <el-input
              v-model="draftUser"
              type="textarea"
              :rows="14"
              resize="vertical"
            />
          </div>

          <div class="placeholders" v-if="active.placeholders.length > 0">
            <div class="ph-title">{{ t('prompts.placeholdersLabel') }}</div>
            <div class="ph-chips">
              <button
                v-for="ph in active.placeholders"
                :key="ph"
                class="chip"
                :title="`点击追加 ${phLabel(ph)}`"
                @click="insertPlaceholder(ph)"
              >
                {{ phLabel(ph) }}
              </button>
            </div>
          </div>
        </template>
        <div v-else class="empty">{{ t('prompts.empty') }}</div>
      </section>
    </div>

    <template #footer>
      <div class="footer">
        <div class="footer-left">
          <el-button
            v-if="active"
            :loading="resetting"
            :disabled="saving || !active.customized"
            @click="onReset"
          >
            {{ t('prompts.resetButton') }}
          </el-button>
        </div>
        <div class="footer-right">
          <el-button :disabled="saving" @click="emit('update:modelValue', false)">
            {{ t('common.cancel') }}
          </el-button>
          <el-button
            type="primary"
            :loading="saving"
            :disabled="!active || !dirty"
            @click="onSave"
          >
            {{ t('common.save') }}
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 16px;
  min-height: 520px;
}
.sidebar {
  border-right: 1px solid #e5e6eb;
  padding-right: 8px;
  overflow-y: auto;
  max-height: 70vh;
}
.group + .group {
  margin-top: 14px;
}
.group-title {
  font-size: 11px;
  color: #86909c;
  font-weight: 600;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
  padding: 0 8px;
}
.prompt-row {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  cursor: pointer;
  font-family: inherit;
  text-align: left;
  font-size: 13px;
  color: #1f2329;
  transition: background 0.12s, border-color 0.12s;
}
.prompt-row:hover {
  background: #f2f3f5;
}
.prompt-row.active {
  background: #ecf5ff;
  border-color: #4080ff;
  color: #4080ff;
  font-weight: 500;
}
.prompt-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.badge {
  font-size: 10px;
  background: #ffe8a3;
  color: #8a6d00;
  padding: 1px 6px;
  border-radius: 8px;
  flex-shrink: 0;
}
.editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}
.desc {
  margin: 0;
  font-size: 12px;
  color: #86909c;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.field label {
  font-size: 12px;
  font-weight: 600;
  color: #4e5969;
}
.field :deep(.el-textarea__inner) {
  font-family: 'JetBrains Mono', 'SFMono-Regular', Consolas, monospace;
  font-size: 12.5px;
  line-height: 1.55;
}
.placeholders {
  border-top: 1px dashed #e5e6eb;
  padding-top: 10px;
}
.ph-title {
  font-size: 11px;
  color: #86909c;
  margin-bottom: 6px;
}
.ph-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.chip {
  font-family: 'JetBrains Mono', 'SFMono-Regular', Consolas, monospace;
  font-size: 11px;
  padding: 2px 8px;
  border: 1px solid #c9d2ff;
  background: #f3f6ff;
  color: #4080ff;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.12s;
}
.chip:hover {
  background: #e3ebff;
}
.empty {
  color: #86909c;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  font-size: 13px;
}
.footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.footer-right {
  display: flex;
  gap: 8px;
}
</style>
