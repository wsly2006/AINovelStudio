<script setup>
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { EditorState } from '@codemirror/state'
import { EditorView, keymap, lineNumbers, placeholder as placeholderExt } from '@codemirror/view'
import { defaultKeymap, history, historyKeymap } from '@codemirror/commands'
import { syntaxHighlighting, defaultHighlightStyle, indentOnInput } from '@codemirror/language'
import { markdown } from '@codemirror/lang-markdown'
import { chaptersApi } from '../api/chapters'
import { useAutoSave } from '../composables/useAutoSave'

const props = defineProps({
  chapterId: { type: Number, required: true },
})
const emit = defineEmits(['saved'])

const { t } = useI18n()

const containerEl = ref(null)
// CodeMirror 视图实例不应被 Vue 深度响应化,用 shallowRef
const view = shallowRef(null)
const content = ref('')
const loading = ref(true)
const wordCount = ref(0)
// 当前编辑器里实际承载的章节 id。saveFn 用这个而不是 props.chapterId,
// 否则切章瞬间 props 已先变到新 id,导致 flush 把旧章节的内容写到新章节。
const editingChapterId = ref(null)

const { state: saveState, savedAt, flush } = useAutoSave(
  content,
  async (text) => {
    const cid = editingChapterId.value
    if (!cid) return
    const result = await chaptersApi.saveContent(cid, text)
    wordCount.value = result.word_count
    emit('saved', result)
  },
  { delay: 1500 }
)

defineExpose({
  flush,
  getContent: () => content.value,
  getSelection: () => {
    const v = view.value
    if (!v) return ''
    const { from, to } = v.state.selection.main
    return v.state.sliceDoc(from, to)
  },
  getCursorText: () => {
    const v = view.value
    if (!v) return content.value
    const head = v.state.selection.main.head
    return v.state.sliceDoc(0, head)
  },
  replaceSelection: (text) => {
    const v = view.value
    if (!v) return
    const { from, to } = v.state.selection.main
    v.dispatch({
      changes: { from, to, insert: text },
      selection: { anchor: from + text.length },
    })
    v.focus()
  },
  insertAtCursor: (text) => {
    const v = view.value
    if (!v) return
    const head = v.state.selection.main.head
    v.dispatch({
      changes: { from: head, to: head, insert: text },
      selection: { anchor: head + text.length },
    })
    v.focus()
  },
  appendToEnd: (text) => {
    const v = view.value
    if (!v) return
    const end = v.state.doc.length
    const sep = end > 0 && !v.state.sliceDoc(end - 1, end).match(/\n/) ? '\n\n' : ''
    v.dispatch({
      changes: { from: end, to: end, insert: sep + text },
      selection: { anchor: end + sep.length + text.length },
    })
    v.focus()
  },
  replaceAll: (text) => {
    const v = view.value
    if (!v) return
    v.dispatch({
      changes: { from: 0, to: v.state.doc.length, insert: text },
      selection: { anchor: text.length },
    })
    v.focus()
  },
})

const stateText = computed(() => {
  const map = {
    idle: t('editor.saveStateIdle'),
    dirty: t('editor.saveStateDirty'),
    saving: t('editor.saveStateSaving'),
    saved: t('editor.saveStateSaved'),
    error: t('editor.saveStateError'),
  }
  return map[saveState.value] || ''
})

const stateClass = computed(() => `state state-${saveState.value}`)

function buildState(initial) {
  return EditorState.create({
    doc: initial,
    extensions: [
      lineNumbers(),
      history(),
      indentOnInput(),
      syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
      markdown(),
      placeholderExt(t('editor.placeholder')),
      keymap.of([...defaultKeymap, ...historyKeymap]),
      EditorView.lineWrapping,
      EditorView.updateListener.of((u) => {
        if (u.docChanged) {
          content.value = u.state.doc.toString()
        }
      }),
      EditorView.theme({
        '&': { height: '100%', fontSize: '15px' },
        '.cm-scroller': {
          fontFamily:
            "ui-monospace, SFMono-Regular, 'Cascadia Code', 'PingFang SC', 'Microsoft YaHei', monospace",
          lineHeight: '1.7',
        },
        '.cm-content': { padding: '16px 20px' },
        '.cm-gutters': { backgroundColor: '#fafbfc', border: 'none' },
      }),
    ],
  })
}

async function loadAndMount() {
  loading.value = true
  // 加载期间清空 id,挡住任何后台 flush 把当前内容写到错误的章节
  editingChapterId.value = null
  try {
    const detail = await chaptersApi.get(props.chapterId)
    content.value = detail.content || ''
    wordCount.value = detail.word_count || 0
  } catch (e) {
    console.error(e)
    content.value = ''
  } finally {
    editingChapterId.value = props.chapterId
    loading.value = false
  }

  if (view.value) {
    view.value.destroy()
    view.value = null
  }
  if (containerEl.value) {
    view.value = new EditorView({
      state: buildState(content.value),
      parent: containerEl.value,
    })
  }
}

onMounted(loadAndMount)
watch(() => props.chapterId, async (newId, oldId) => {
  if (newId === oldId) return
  // 切章节前 flush 旧章节
  await flush()
  loadAndMount()
})
onBeforeUnmount(() => {
  if (view.value) {
    view.value.destroy()
    view.value = null
  }
})

const wordCountText = computed(() => t('workspace.wordCount', { n: wordCount.value }))
</script>

<template>
  <div class="chapter-editor">
    <div class="toolbar">
      <span :class="stateClass">{{ stateText }}</span>
      <span class="spacer" />
      <span class="words">{{ wordCountText }}</span>
    </div>
    <div class="cm-host" ref="containerEl" v-loading="loading"></div>
  </div>
</template>

<style scoped>
.chapter-editor {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}
.toolbar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  padding: 8px 16px;
  border-bottom: 1px solid #e5e6eb;
  font-size: 12px;
  color: #86909c;
  gap: 8px;
}
.spacer {
  flex: 1;
}
.state {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.state::before {
  content: '';
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}
.state-idle { color: #c9cdd4; }
.state-dirty { color: #ff7d00; }
.state-saving { color: #4080ff; }
.state-saved { color: #00b42a; }
.state-error { color: #f53f3f; }
.words {
  font-variant-numeric: tabular-nums;
}
.cm-host {
  flex: 1;
  overflow: hidden;
}
.cm-host :deep(.cm-editor) {
  height: 100%;
}
.cm-host :deep(.cm-editor.cm-focused) {
  outline: none;
}
</style>
