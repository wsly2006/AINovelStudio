import { defineStore } from 'pinia'
import { ref } from 'vue'
import { assistantApi } from '../api/assistant'
import { streamSSE } from '../api/ai'

export const useAssistantStore = defineStore('assistant', () => {
  const projectId = ref(null)
  const conversations = ref([])
  const activeId = ref(null)
  const messages = ref([]) // 当前对话的所有 message
  const streaming = ref(false)
  // 流式期间临时累积的 assistant 文本(还没落库,落库后清空靠 reload)
  const streamingText = ref('')
  const error = ref('')
  let abortCtrl = null

  function _setActive(id) {
    activeId.value = id
    streamingText.value = ''
    error.value = ''
  }

  async function loadConversations(pid) {
    projectId.value = pid
    conversations.value = await assistantApi.listConversations(pid)
    if (!conversations.value.some((c) => c.id === activeId.value)) {
      _setActive(conversations.value[0]?.id ?? null)
    }
    if (activeId.value) await loadMessages(activeId.value)
    else messages.value = []
  }

  async function loadMessages(conversationId) {
    if (!conversationId) {
      messages.value = []
      return
    }
    messages.value = await assistantApi.listMessages(conversationId)
  }

  async function selectConversation(conversationId) {
    _setActive(conversationId)
    await loadMessages(conversationId)
  }

  async function createConversation(payload = {}) {
    const created = await assistantApi.createConversation(projectId.value, payload)
    conversations.value = [created, ...conversations.value]
    _setActive(created.id)
    messages.value = []
    return created
  }

  async function renameConversation(conversationId, title) {
    const updated = await assistantApi.updateConversation(conversationId, { title })
    const i = conversations.value.findIndex((c) => c.id === conversationId)
    if (i >= 0) conversations.value[i] = { ...conversations.value[i], ...updated }
  }

  async function deleteConversation(conversationId) {
    await assistantApi.deleteConversation(conversationId)
    conversations.value = conversations.value.filter((c) => c.id !== conversationId)
    if (activeId.value === conversationId) {
      _setActive(conversations.value[0]?.id ?? null)
      await loadMessages(activeId.value)
    }
  }

  function abort() {
    if (abortCtrl) {
      abortCtrl.abort()
      abortCtrl = null
    }
    streaming.value = false
  }

  async function sendMessage({ content, chapterId = null, selectionText = null,
                                includeChapterContent = true,
                                characterIds = [], worldEntityIds = [], itemIds = [] }) {
    if (!projectId.value) return
    error.value = ''
    // 没有 active 时先建一个空对话
    if (!activeId.value) {
      await createConversation({ chapter_id: chapterId })
    }
    const convId = activeId.value

    // 乐观插入 user 消息
    const optimisticUser = {
      id: `tmp-user-${Date.now()}`,
      conversation_id: convId,
      role: 'user',
      content,
      chapter_id: chapterId,
      selection_text: selectionText,
      created_at: new Date().toISOString(),
    }
    messages.value = [...messages.value, optimisticUser]

    streaming.value = true
    streamingText.value = ''
    abortCtrl = new AbortController()

    let buf = ''
    await streamSSE(
      `/api/ai/conversations/${convId}/messages`,
      {
        content,
        chapter_id: chapterId,
        selection_text: selectionText,
        include_chapter_content: includeChapterContent,
        character_ids: characterIds,
        world_entity_ids: worldEntityIds,
        item_ids: itemIds,
      },
      {
        onDelta: (text) => {
          buf += text
          streamingText.value = buf
        },
        onDone: () => {
          streaming.value = false
        },
        onError: (msg) => {
          streaming.value = false
          error.value = msg || 'AI 调用失败'
        },
        signal: abortCtrl.signal,
      },
    )
    abortCtrl = null
    // 流结束后从后端重新拉取消息(替换乐观插入 + 拿到真实 id)
    await loadMessages(convId)
    streamingText.value = ''
    // 刷会话标题 / 时间戳
    try {
      const list = await assistantApi.listConversations(projectId.value)
      conversations.value = list
    } catch {}
  }

  function reset() {
    abort()
    projectId.value = null
    conversations.value = []
    activeId.value = null
    messages.value = []
    streamingText.value = ''
    error.value = ''
  }

  return {
    projectId,
    conversations,
    activeId,
    messages,
    streaming,
    streamingText,
    error,
    loadConversations,
    loadMessages,
    selectConversation,
    createConversation,
    renameConversation,
    deleteConversation,
    sendMessage,
    abort,
    reset,
  }
})
