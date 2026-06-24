<script setup>
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  projectId: { type: Number, default: null },
  // 父级当前过滤的目标语,默认作为抽取目标
  defaultTargetLang: { type: String, default: 'en-US' },
})
const emit = defineEmits(['update:modelValue', 'completed'])

const { t } = useI18n()

const LANG_OPTIONS = [
  { value: 'en-US', label: 'English' },
  { value: 'es-ES', label: 'Español' },
  { value: 'id-ID', label: 'Indonesia' },
  { value: 'ja-JP', label: '日本語' },
  { value: 'ko-KR', label: '한국어' },
  { value: 'vi-VN', label: 'Tiếng Việt' },
]

const targetLang = ref(props.defaultTargetLang)
const phase = ref('idle') // idle | running | done | error
const progress = ref({ index: 0, total: 0, title: '', addedTotal: 0 })
const errorMsg = ref('')
const summary = ref({ extracted: 0, skipped: 0 })

let abortCtrl = null

watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      targetLang.value = props.defaultTargetLang || 'en-US'
      phase.value = 'idle'
      progress.value = { index: 0, total: 0, title: '', addedTotal: 0 }
      errorMsg.value = ''
      summary.value = { extracted: 0, skipped: 0 }
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

async function startExtract() {
  if (!props.projectId) return
  phase.value = 'running'
  errorMsg.value = ''
  progress.value = { index: 0, total: 0, title: '', addedTotal: 0 }
  abortCtrl = new AbortController()

  try {
    const resp = await fetch(`/api/projects/${props.projectId}/glossary/extract`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ target_lang: targetLang.value }),
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
        if (evt.event === 'start') {
          progress.value = { index: 0, total: evt.data.total, title: '', addedTotal: 0 }
        } else if (evt.event === 'progress') {
          progress.value = {
            index: evt.data.index,
            total: evt.data.total,
            title: evt.data.title || '',
            addedTotal: progress.value.addedTotal + (evt.data.added || 0),
          }
        } else if (evt.event === 'done') {
          summary.value = {
            extracted: evt.data.extracted || 0,
            skipped: evt.data.skipped || 0,
          }
          phase.value = 'done'
          finished = true
          emit('completed')
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
    ElMessage.error(`${t('glossary.extractFailed')}: ${e.message}`)
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

function close() {
  stop()
  emit('update:modelValue', false)
}

function progressPercent() {
  if (!progress.value.total) return 0
  return Math.round((progress.value.index / progress.value.total) * 100)
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    :title="t('glossary.extractDrawerTitle')"
    width="520px"
    :close-on-click-modal="false"
    :before-close="(done) => { stop(); done() }"
  >
    <div class="content">
      <p class="subtitle">{{ t('glossary.extractDrawerHint') }}</p>

      <el-form-item :label="t('glossary.fieldTargetLang')" v-if="phase === 'idle'">
        <el-select v-model="targetLang" style="width: 100%">
          <el-option
            v-for="opt in LANG_OPTIONS"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
      </el-form-item>

      <div v-if="phase === 'running'" class="progress-area">
        <el-progress :percentage="progressPercent()" :stroke-width="14" />
        <p class="progress-text" v-if="progress.total">
          {{ progress.title || '...' }}
          <span class="muted">({{ progress.index }}/{{ progress.total }})</span>
          <span v-if="progress.addedTotal > 0" class="added-tag">
            +{{ progress.addedTotal }}
          </span>
        </p>
      </div>

      <div v-if="phase === 'done'" class="done-area">
        <el-alert
          :title="t('glossary.extractDone', {
            added: summary.extracted,
            skipped: summary.skipped,
          })"
          type="success"
          :closable="false"
          show-icon
        />
      </div>

      <div v-if="phase === 'error'" class="done-area">
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
        @click="startExtract"
      >
        {{ t('glossary.extractStart') }}
      </el-button>
      <el-button v-else-if="phase === 'running'" type="danger" @click="stop">
        {{ t('glossary.extractCancel') }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.content {
  min-height: 120px;
}
.subtitle {
  color: #4e5969;
  font-size: 13px;
  margin: 0 0 16px;
  line-height: 1.6;
}
.progress-area {
  padding: 8px 0;
}
.progress-text {
  margin: 12px 0 0;
  font-size: 13px;
  color: #4e5969;
  display: flex;
  align-items: center;
  gap: 8px;
}
.muted {
  color: #86909c;
  font-size: 12px;
}
.added-tag {
  color: #00b42a;
  font-weight: 600;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.done-area {
  padding-top: 8px;
}
</style>
