<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChatLineRound, Delete, Document, EditPen, Plus } from '@element-plus/icons-vue'
import { useAssistantStore } from '../stores/assistant'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  projectId: { type: Number, default: null },
  // 当前章节(可空):用作绑定 + 注入正文
  chapterId: { type: Number, default: null },
  chapterTitle: { type: String, default: '' },
  // 编辑器当前选区(由父组件实时拉)
  selectionText: { type: String, default: '' },
})
const emit = defineEmits([
  'update:modelValue',
  'insert-to-cursor',
  'replace-selection',
  'append-to-end',
])

const { t } = useI18n()
const assistant = useAssistantStore()

const input = ref('')
const includeChapter = ref(true)
const useSelection = ref(false)
const useChapter = ref(true)
const messageListEl = ref(null)

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

watch(
  () => props.modelValue,
  async (v) => {
    if (v && props.projectId) {
      try {
        await assistant.loadConversations(props.projectId)
      } catch (e) {
        ElMessage.error(e.message || t('assistant.error'))
      }
      scrollToBottom()
    }
  }
)

watch(
  () => props.selectionText,
  (val) => {
    // 选区变化时,如果用户开了「就选区提问」,但选区清空了,自动关掉
    if (!val && useSelection.value) useSelection.value = false
  }
)

watch(
  () => [assistant.messages, assistant.streamingText],
  () => scrollToBottom(),
  { deep: true }
)

function scrollToBottom() {
  nextTick(() => {
    const el = messageListEl.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

async function onCreate() {
  try {
    await assistant.createConversation({
      chapter_id: props.chapterId || null,
    })
  } catch (e) {
    ElMessage.error(e.message || t('assistant.error'))
  }
}

async function onSelect(id) {
  if (id === assistant.activeId) return
  try {
    await assistant.selectConversation(id)
    scrollToBottom()
  } catch (e) {
    ElMessage.error(e.message || t('assistant.error'))
  }
}

async function onRename(conv) {
  let title = conv.title || ''
  try {
    const r = await ElMessageBox.prompt(t('assistant.rename'), '', {
      inputValue: title,
      inputPlaceholder: '',
    })
    title = r.value
  } catch {
    return
  }
  try {
    await assistant.renameConversation(conv.id, title || '新对话')
  } catch (e) {
    ElMessage.error(e.message || t('assistant.error'))
  }
}

async function onDelete(conv) {
  try {
    await ElMessageBox.confirm(t('assistant.deleteConfirm'), '', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await assistant.deleteConversation(conv.id)
  } catch (e) {
    ElMessage.error(e.message || t('assistant.error'))
  }
}

async function onSend() {
  const content = input.value.trim()
  if (!content) {
    ElMessage.warning(t('assistant.pleaseTypeContent'))
    return
  }
  if (assistant.streaming) return
  const payload = {
    content,
    chapterId: useChapter.value ? props.chapterId || null : null,
    selectionText: useSelection.value ? props.selectionText : null,
    includeChapterContent: includeChapter.value,
  }
  input.value = ''
  try {
    await assistant.sendMessage(payload)
    if (assistant.error) {
      ElMessage.error(assistant.error)
    }
  } catch (e) {
    ElMessage.error(e.message || t('assistant.error'))
  }
}

function onStop() {
  assistant.abort()
}

function onQuick(text) {
  input.value = text
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success(t('assistant.copied'))
  } catch {
    ElMessage.warning('复制失败,请手动选择')
  }
}

function insertToEditor(text) {
  emit('insert-to-cursor', text)
}
function replaceSelection(text) {
  emit('replace-selection', text)
}
function appendToEnd(text) {
  emit('append-to-end', text)
}

function onKeydown(e) {
  // Ctrl+Enter / Cmd+Enter 直接发
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault()
    onSend()
  }
}
</script>

<template>
  <el-drawer
    v-model="visible"
    :title="t('assistant.title')"
    direction="rtl"
    size="520px"
    :with-header="true"
    :destroy-on-close="false"
  >
    <div class="assistant-root">
      <!-- 会话列表 -->
      <div class="conv-bar">
        <el-button
          type="primary"
          plain
          size="small"
          :icon="Plus"
          @click="onCreate"
        >
          {{ t('assistant.newConversation') }}
        </el-button>
        <div class="conv-list">
          <div
            v-for="c in assistant.conversations"
            :key="c.id"
            class="conv-item"
            :class="{ active: c.id === assistant.activeId }"
            @click="onSelect(c.id)"
          >
            <span class="conv-title" :title="c.title">{{ c.title }}</span>
            <span class="conv-actions">
              <el-button
                text
                size="small"
                :icon="EditPen"
                @click.stop="onRename(c)"
              />
              <el-button
                text
                size="small"
                :icon="Delete"
                @click.stop="onDelete(c)"
              />
            </span>
          </div>
          <div v-if="!assistant.conversations.length" class="conv-empty">
            <el-icon><ChatLineRound /></el-icon>
            <span>{{ t('assistant.placeholderEmpty') }}</span>
          </div>
        </div>
      </div>

      <!-- 消息区 -->
      <div class="chat-area">
        <div ref="messageListEl" class="msg-list">
          <div
            v-for="m in assistant.messages"
            :key="m.id"
            class="msg"
            :class="m.role"
          >
            <div class="msg-role">
              {{ m.role === 'user' ? '我' : 'AI' }}
            </div>
            <div class="msg-body">
              <div v-if="m.selection_text" class="msg-selection">
                {{ t('assistant.selectionLabel') }}:{{ m.selection_text }}
              </div>
              <div class="msg-content">{{ m.content }}</div>
              <div v-if="m.role === 'assistant' && m.content" class="msg-actions">
                <el-button text size="small" @click="copyText(m.content)">
                  {{ t('assistant.copy') }}
                </el-button>
                <el-button text size="small" @click="insertToEditor(m.content)">
                  {{ t('assistant.insertToCursor') }}
                </el-button>
                <el-button text size="small" @click="replaceSelection(m.content)">
                  {{ t('assistant.replaceSelection') }}
                </el-button>
                <el-button text size="small" @click="appendToEnd(m.content)">
                  {{ t('assistant.appendToEnd') }}
                </el-button>
              </div>
            </div>
          </div>

          <!-- 流式中的占位气泡 -->
          <div v-if="assistant.streaming" class="msg assistant streaming">
            <div class="msg-role">AI</div>
            <div class="msg-body">
              <div class="msg-content">{{ assistant.streamingText || '…' }}</div>
            </div>
          </div>
        </div>

        <!-- 选项行 -->
        <div class="opt-row">
          <el-checkbox v-model="useChapter" :disabled="!chapterId" size="small">
            {{ chapterId ? t('assistant.bindChapter') : t('assistant.chapterNone') }}
          </el-checkbox>
          <el-checkbox
            v-model="includeChapter"
            :disabled="!useChapter || !chapterId"
            size="small"
          >
            {{ t('assistant.includeChapterContent') }}
          </el-checkbox>
          <el-checkbox
            v-model="useSelection"
            :disabled="!selectionText"
            size="small"
          >
            {{ t('assistant.askAboutSelection') }}
          </el-checkbox>
        </div>

        <!-- 快捷指令 -->
        <div class="quick-row">
          <el-button size="small" plain @click="onQuick(t('assistant.quickContinue'))">
            {{ t('assistant.quickContinue') }}
          </el-button>
          <el-button size="small" plain @click="onQuick(t('assistant.quickPolish'))">
            {{ t('assistant.quickPolish') }}
          </el-button>
          <el-button size="small" plain @click="onQuick(t('assistant.quickAlternatives'))">
            {{ t('assistant.quickAlternatives') }}
          </el-button>
          <el-button size="small" plain @click="onQuick(t('assistant.quickFindIssues'))">
            {{ t('assistant.quickFindIssues') }}
          </el-button>
        </div>

        <!-- 输入区 -->
        <div class="input-row">
          <el-input
            v-model="input"
            type="textarea"
            :rows="3"
            :placeholder="
              assistant.streaming
                ? t('assistant.placeholderRunning')
                : t('assistant.placeholderEmpty')
            "
            :disabled="assistant.streaming"
            resize="none"
            @keydown="onKeydown"
          />
          <div class="input-actions">
            <el-button
              v-if="!assistant.streaming"
              type="primary"
              :disabled="!input.trim()"
              @click="onSend"
            >
              {{ t('assistant.send') }}
            </el-button>
            <el-button v-else type="danger" @click="onStop">
              {{ t('assistant.stop') }}
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<style scoped>
.assistant-root {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 8px;
}
.conv-bar {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  border-bottom: 1px solid #e5e6eb;
  padding-bottom: 8px;
}
.conv-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-height: 80px;
  overflow-y: auto;
}
.conv-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: 220px;
  padding: 2px 6px 2px 10px;
  border-radius: 12px;
  background: #f2f3f5;
  font-size: 12px;
  color: #4e5969;
  cursor: pointer;
  user-select: none;
}
.conv-item:hover {
  background: #e8eaed;
}
.conv-item.active {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}
.conv-title {
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.conv-empty {
  font-size: 12px;
  color: #86909c;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  gap: 8px;
}
.msg-list {
  flex: 1;
  overflow-y: auto;
  padding-right: 4px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.msg {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.msg.user .msg-body {
  background: var(--el-color-primary-light-9);
}
.msg.assistant .msg-body {
  background: #f7f8fa;
}
.msg.streaming .msg-body {
  border: 1px dashed var(--el-color-primary-light-5);
}
.msg-role {
  font-size: 11px;
  color: #86909c;
}
.msg-body {
  border-radius: 8px;
  padding: 10px 12px;
}
.msg-selection {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
  padding: 4px 6px;
  border-left: 2px solid #c6cbd6;
  background: rgba(0, 0, 0, 0.03);
  white-space: pre-wrap;
  word-break: break-word;
}
.msg-content {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.7;
  color: #1d2129;
}
.msg-actions {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.opt-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 12px;
  color: #4e5969;
}
.quick-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.input-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.input-actions {
  display: flex;
  justify-content: flex-end;
}
</style>
