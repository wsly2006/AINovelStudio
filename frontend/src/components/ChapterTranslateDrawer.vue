<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  chapterId: { type: Number, default: null },
  // 父级可选传入工程的术语表数,只用于 hint 文案
  glossaryCount: { type: Number, default: 0 },
})
const emit = defineEmits(['update:modelValue', 'translated', 'view-version'])

const { t } = useI18n()

const LANG_OPTIONS = [
  { value: 'en-US', label: 'English' },
  { value: 'es-ES', label: 'Español' },
  { value: 'id-ID', label: 'Indonesia' },
  { value: 'ja-JP', label: '日本語' },
  { value: 'ko-KR', label: '한국어' },
  { value: 'vi-VN', label: 'Tiếng Việt' },
]

const targetLang = ref('en-US')
const extraInstruction = ref('')
const phase = ref('idle') // idle | streaming | done | error
const result = ref('')
const errorMsg = ref('')
const finalVersion = ref(null) // {version_id, word_count, target_lang}

let abortCtrl = null

const charCount = computed(() => result.value.length)
const canStart = computed(() => phase.value === 'idle' && !!props.chapterId)

watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      phase.value = 'idle'
      result.value = ''
      errorMsg.value = ''
      finalVersion.value = null
      extraInstruction.value = ''
    } else {
      stop()
    }
  }
)

function stop() {
  if (abortCtrl) {
    abortCtrl.abort()
    abortCtrl = null
  }
}

function close() {
  stop()
  emit('update:modelValue', false)
}

function viewInHistory() {
  if (finalVersion.value?.version_id) {
    emit('view-version', {
      versionId: finalVersion.value.version_id,
      lang: targetLang.value,
    })
  }
  close()
}

async function startTranslate() {
  if (!props.chapterId) return
  phase.value = 'streaming'
  result.value = ''
  errorMsg.value = ''
  finalVersion.value = null
  abortCtrl = new AbortController()

  try {
    const resp = await fetch(`/api/chapters/${props.chapterId}/translate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({
        target_lang: targetLang.value,
        extra_instruction: extraInstruction.value.trim() || null,
      }),
      signal: abortCtrl.signal,
    })
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}))
      errorMsg.value = data.detail || `HTTP ${resp.status}`
      phase.value = 'error'
      return
    }
    const reader = resp.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    let finished = false

    while (!finished) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let idx
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const block = buffer.slice(0, idx)
        buffer = buffer.slice(idx + 2)
        const evt = parseSSEBlock(block)
        if (!evt) continue
        if (evt.event === 'delta') {
          result.value += evt.data.text || ''
        } else if (evt.event === 'done') {
          finalVersion.value = {
            version_id: evt.data.version_id,
            word_count: evt.data.word_count || 0,
            target_lang: evt.data.target_lang || targetLang.value,
          }
          phase.value = 'done'
          finished = true
          emit('translated', finalVersion.value)
        } else if (evt.event === 'error') {
          errorMsg.value = evt.data.message || 'AI error'
          phase.value = 'error'
          finished = true
        }
      }
    }
  } catch (e) {
    if (e.name === 'AbortError') return
    errorMsg.value = e.message
    phase.value = 'error'
    ElMessage.error(`${t('translate.failed')}: ${e.message}`)
  }
}

function parseSSEBlock(block) {
  const lines = block.split(/\r?\n/)
  let event = 'message'
  const dataLines = []
  for (const line of lines) {
    if (!line) continue
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
  }
  if (!dataLines.length) return null
  let data
  try {
    data = JSON.parse(dataLines.join('\n'))
  } catch {
    data = {}
  }
  return { event, data }
}
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    :title="t('translate.drawerTitle')"
    direction="rtl"
    size="600px"
    :close-on-click-modal="false"
    :before-close="(done) => { stop(); done() }"
  >
    <div class="content">
      <p class="hint">{{ t('translate.drawerHint') }}</p>

      <div v-if="glossaryCount > 0" class="glossary-hint">
        {{ t('translate.glossaryHint', { n: glossaryCount }) }}
      </div>

      <el-form label-position="top" v-if="phase === 'idle'">
        <el-form-item :label="t('translate.targetLangLabel')">
          <el-select v-model="targetLang" style="width: 100%">
            <el-option
              v-for="opt in LANG_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('translate.extraInstructionLabel')">
          <el-input
            v-model="extraInstruction"
            type="textarea"
            :rows="3"
            :placeholder="t('translate.extraInstructionPlaceholder')"
            maxlength="2000"
          />
        </el-form-item>
      </el-form>

      <div v-if="phase === 'streaming' || phase === 'done'" class="result-area">
        <div class="result-head">
          <span v-if="phase === 'streaming'" class="streaming-tag">
            {{ t('translate.streaming') }}
          </span>
          <span class="char-count">
            {{ t('translate.streamingChars', { n: charCount }) }}
          </span>
        </div>
        <pre class="result-body">{{ result || '...' }}</pre>
      </div>

      <div v-if="phase === 'done'" class="done-strip">
        <el-alert
          :title="t('translate.done', {
            n: finalVersion?.word_count || 0,
            vid: finalVersion?.version_id || '?',
          })"
          type="success"
          :closable="false"
          show-icon
        />
      </div>

      <div v-if="phase === 'error'" class="done-strip">
        <el-alert :title="errorMsg" type="error" :closable="false" show-icon />
      </div>
    </div>

    <template #footer>
      <el-button @click="close">
        {{ phase === 'done' ? t('common.confirm') : t('common.cancel') }}
      </el-button>
      <el-button
        v-if="phase === 'idle'"
        type="primary"
        :disabled="!canStart"
        @click="startTranslate"
      >
        {{ t('translate.start') }}
      </el-button>
      <el-button
        v-else-if="phase === 'streaming'"
        type="danger"
        @click="stop"
      >
        {{ t('translate.cancel') }}
      </el-button>
      <el-button
        v-else-if="phase === 'done'"
        type="primary"
        @click="viewInHistory"
      >
        {{ t('translate.viewInHistory') }}
      </el-button>
    </template>
  </el-drawer>
</template>

<style scoped>
.content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  overflow: hidden;
}
.hint {
  margin: 0;
  font-size: 13px;
  color: #4e5969;
  line-height: 1.6;
}
.glossary-hint {
  font-size: 12px;
  color: #4080ff;
  background: #ecf5ff;
  border-radius: 6px;
  padding: 6px 10px;
}
.result-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 0;
}
.result-head {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
}
.streaming-tag {
  color: #4080ff;
  font-weight: 600;
}
.char-count {
  color: #86909c;
  font-variant-numeric: tabular-nums;
}
.result-body {
  flex: 1;
  margin: 0;
  padding: 12px;
  background: #f7f8fa;
  border-radius: 8px;
  overflow: auto;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  color: #1f2329;
  min-height: 0;
}
.done-strip {
  flex-shrink: 0;
}
</style>
