<script setup>
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  projectId: { type: Number, default: null },
})
const emit = defineEmits(['update:modelValue', 'completed'])

const { t } = useI18n()

const mode = ref('merge')
const phase = ref('idle') // idle | running | done | error
const progress = ref({ index: 0, total: 0, title: '' })
const errorMsg = ref('')
const summary = ref({ extracted: 0 })

let abortCtrl = null

watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      mode.value = 'merge'
      phase.value = 'idle'
      progress.value = { index: 0, total: 0, title: '' }
      errorMsg.value = ''
      summary.value = { extracted: 0 }
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
  progress.value = { index: 0, total: 0, title: '' }
  abortCtrl = new AbortController()

  try {
    const resp = await fetch(`/api/projects/${props.projectId}/characters/extract`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ mode: mode.value }),
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
          progress.value = { index: 0, total: evt.data.total, title: '' }
        } else if (evt.event === 'progress') {
          progress.value = {
            index: evt.data.index,
            total: evt.data.total,
            title: evt.data.title || '',
          }
        } else if (evt.event === 'done') {
          summary.value = { extracted: evt.data.extracted || 0 }
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
    ElMessage.error(`${t('characters.extractFailed')}: ${e.message}`)
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
    :title="t('characters.extract')"
    width="520px"
    :close-on-click-modal="false"
    :before-close="(done) => { stop(); done() }"
  >
    <div class="content">
      <p class="subtitle">{{ t('characters.extractSubtitle') }}</p>

      <el-form-item :label="t('characters.extractMode')" v-if="phase === 'idle'">
        <el-radio-group v-model="mode">
          <el-radio value="merge">{{ t('characters.extractModeMerge') }}</el-radio>
          <el-radio value="replace">{{ t('characters.extractModeReplace') }}</el-radio>
        </el-radio-group>
      </el-form-item>

      <div v-if="phase === 'running'" class="progress-area">
        <el-progress :percentage="progressPercent()" :stroke-width="14" />
        <p class="progress-text" v-if="progress.total">
          {{ t('characters.extractAt', {
            title: progress.title || '...',
            i: progress.index,
            n: progress.total
          }) }}
        </p>
      </div>

      <div v-if="phase === 'done'" class="done-area">
        <el-alert
          :title="t('characters.extractDone', { n: summary.extracted })"
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
      <el-button @click="close">{{ phase === 'done' ? t('common.confirm') : t('common.cancel') }}</el-button>
      <el-button
        v-if="phase === 'idle'"
        type="primary"
        @click="startExtract"
      >
        {{ t('characters.extractStart') }}
      </el-button>
      <el-button v-else-if="phase === 'running'" type="danger" @click="stop">
        {{ t('ai.stop') }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.content {
  min-height: 100px;
}
.subtitle {
  color: #86909c;
  font-size: 13px;
  margin: 0 0 16px;
}
.progress-area {
  padding: 8px 0;
}
.progress-text {
  margin: 12px 0 0;
  font-size: 13px;
  color: #4e5969;
}
.done-area {
  padding-top: 8px;
}
</style>
