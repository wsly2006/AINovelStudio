<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { streamSSE } from '../api/ai.js'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  // 'generate' | 'continue' | 'rewrite'
  mode: { type: String, required: true },
  chapterId: { type: Number, default: null },
  // 由父级传入,改写 / 续写依赖
  selection: { type: String, default: '' },
  cursorText: { type: String, default: '' },
  // 工程的人物列表(供多选注入)
  characters: { type: Array, default: () => [] },
  // 工程的世界观条目(供多选注入)
  worldEntities: { type: Array, default: () => [] },
  // 工程的物品(供多选注入)
  items: { type: Array, default: () => [] },
  // 工程在「新建」时填的每章字数,作为本章生成的默认目标字数
  defaultTargetWordCount: { type: Number, default: 4000 },
})
const emit = defineEmits(['update:modelValue', 'accept', 'append', 'insert', 'replace'])

const { t } = useI18n()

const targetWordCount = ref(4000)
const extraInstruction = ref('')
const rewriteInstruction = ref('')
const selectedCharacterIds = ref([])
const selectedWorldIds = ref([])
const selectedItemIds = ref([])
const result = ref('')
const phase = ref('idle') // idle | streaming | done | error
const errorMsg = ref('')

let abortCtrl = null

const drawerTitle = computed(() => {
  return {
    generate: t('ai.drawerGenerateTitle'),
    continue: t('ai.drawerContinueTitle'),
    rewrite: t('ai.drawerRewriteTitle'),
  }[props.mode] || ''
})

const canStart = computed(() => {
  if (phase.value === 'streaming') return false
  if (props.mode === 'rewrite') return !!rewriteInstruction.value.trim() && !!props.selection
  return true
})

const KIND_LABEL = {
  location: '地点',
  organization: '组织',
  item: '物品',
  concept: '概念',
}

watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      // 打开抽屉时重置
      result.value = ''
      phase.value = 'idle'
      errorMsg.value = ''
      if (props.mode !== 'rewrite') extraInstruction.value = ''
      if (props.mode === 'rewrite') rewriteInstruction.value = ''
      // 目标字数对齐工程「每章字数」,用户仍可在抽屉内临时改
      targetWordCount.value = Number(props.defaultTargetWordCount) || 4000
      // 默认勾选所有"主角"角色,简化首次生成
      selectedCharacterIds.value = props.characters
        .filter((c) => c.role === '主角')
        .map((c) => c.id)
      // 世界观、物品默认不勾,避免上下文过长
      selectedWorldIds.value = []
      selectedItemIds.value = []
    } else {
      stop()
    }
  }
)

async function start() {
  if (!canStart.value || !props.chapterId) return
  result.value = ''
  errorMsg.value = ''
  phase.value = 'streaming'
  abortCtrl = new AbortController()

  const url = `/api/chapters/${props.chapterId}/ai/${props.mode}`
  const charIds = [...selectedCharacterIds.value]
  const worldIds = [...selectedWorldIds.value]
  const itemIds = [...selectedItemIds.value]
  const body =
    props.mode === 'generate'
      ? {
          target_word_count: targetWordCount.value,
          extra_instruction: extraInstruction.value || null,
          character_ids: charIds,
          world_entity_ids: worldIds,
          item_ids: itemIds,
        }
      : props.mode === 'continue'
      ? {
          cursor_text: props.cursorText,
          extra_instruction: extraInstruction.value || null,
          character_ids: charIds,
          world_entity_ids: worldIds,
          item_ids: itemIds,
        }
      : {
          selection: props.selection,
          instruction: rewriteInstruction.value,
          character_ids: charIds,
        }

  await streamSSE(url, body, {
    signal: abortCtrl.signal,
    onDelta: (text) => {
      result.value += text
    },
    onDone: () => {
      phase.value = 'done'
    },
    onError: (msg) => {
      errorMsg.value = msg
      phase.value = 'error'
      ElMessage.error(`${t('ai.error')}: ${msg}`)
    },
  })
}

function stop() {
  if (abortCtrl) {
    abortCtrl.abort()
    abortCtrl = null
  }
  if (phase.value === 'streaming') phase.value = 'done'
}

function close() {
  stop()
  emit('update:modelValue', false)
}

function collapseBlankLines(text) {
  // 把段落之间的多个换行折叠成单个换行,避免 AI 输出的双换行造成正文里大量空行
  return (text || '').replace(/\r\n/g, '\n').replace(/\n{2,}/g, '\n')
}

function onAccept() {
  // 全章替换(generate / 整章场景)
  emit('replace', collapseBlankLines(result.value))
  close()
}

function onAppend() {
  emit('append', collapseBlankLines(result.value))
  close()
}

function onInsert() {
  emit('insert', collapseBlankLines(result.value))
  close()
}

function onReplaceSelection() {
  emit('accept', collapseBlankLines(result.value)) // accept = 替换选区
  close()
}
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    :title="drawerTitle"
    direction="rtl"
    size="640px"
    :before-close="(done) => { stop(); done() }"
  >
    <div class="form">
      <!-- generate -->
      <template v-if="mode === 'generate'">
        <el-form-item :label="t('ai.targetWordCount')">
          <el-input-number
            v-model="targetWordCount"
            :min="200"
            :max="20000"
            :step="500"
            style="width: 200px"
          />
        </el-form-item>
        <el-form-item :label="t('ai.extraInstruction')">
          <el-input
            v-model="extraInstruction"
            type="textarea"
            :rows="3"
            :placeholder="t('ai.extraInstructionPlaceholder')"
          />
        </el-form-item>
      </template>

      <!-- continue -->
      <template v-else-if="mode === 'continue'">
        <el-alert
          :title="cursorText ? `已捕获前文 ${cursorText.length} 字作为续写依据` : t('ai.cursorEmpty')"
          :type="cursorText ? 'info' : 'warning'"
          :closable="false"
          show-icon
        />
        <el-form-item :label="t('ai.extraInstruction')" style="margin-top: 16px">
          <el-input
            v-model="extraInstruction"
            type="textarea"
            :rows="3"
            :placeholder="t('ai.extraInstructionPlaceholder')"
          />
        </el-form-item>
      </template>

      <!-- rewrite -->
      <template v-else-if="mode === 'rewrite'">
        <el-alert
          v-if="!selection"
          :title="t('ai.selectionEmpty')"
          type="warning"
          :closable="false"
          show-icon
        />
        <template v-else>
          <div class="selection-box">
            <div class="label">{{ '原文' }} ({{ selection.length }} 字)</div>
            <div class="selection-text">{{ selection }}</div>
          </div>
          <el-form-item :label="t('ai.rewriteInstruction')" required style="margin-top: 16px">
            <el-input
              v-model="rewriteInstruction"
              type="textarea"
              :rows="3"
              :placeholder="t('ai.rewriteInstructionPlaceholder')"
            />
          </el-form-item>
        </template>
      </template>

      <!-- 注入人物档案(三种模式都可用) -->
      <el-form-item :label="t('ai.injectCharactersLabel')">
        <el-select
          v-if="characters.length > 0"
          v-model="selectedCharacterIds"
          multiple
          collapse-tags
          collapse-tags-tooltip
          filterable
          style="width: 100%"
        >
          <el-option
            v-for="c in characters"
            :key="c.id"
            :value="c.id"
            :label="c.name"
          >
            <span>{{ c.name }}</span>
            <span v-if="c.role" class="role-hint">{{ c.role }}</span>
          </el-option>
        </el-select>
        <el-alert
          v-else
          :title="t('ai.injectCharactersEmpty')"
          type="info"
          :closable="false"
        />
        <div class="hint">{{ t('ai.injectCharactersHint') }}</div>
      </el-form-item>

      <!-- 注入世界观条目(generate / continue 才显示,rewrite 不需要) -->
      <el-form-item v-if="mode !== 'rewrite'" :label="t('ai.injectWorldLabel')">
        <el-select
          v-if="worldEntities.length > 0"
          v-model="selectedWorldIds"
          multiple
          collapse-tags
          collapse-tags-tooltip
          filterable
          style="width: 100%"
        >
          <el-option
            v-for="e in worldEntities"
            :key="e.id"
            :value="e.id"
            :label="e.name"
          >
            <span>{{ e.name }}</span>
            <span class="role-hint">{{ KIND_LABEL[e.kind] || e.kind }}</span>
          </el-option>
        </el-select>
        <el-alert
          v-else
          :title="t('ai.injectWorldEmpty')"
          type="info"
          :closable="false"
        />
        <div class="hint">{{ t('ai.injectWorldHint') }}</div>
      </el-form-item>

      <!-- 注入物品(generate / continue 才显示) -->
      <el-form-item v-if="mode !== 'rewrite'" :label="t('ai.injectItemsLabel')">
        <el-select
          v-if="items.length > 0"
          v-model="selectedItemIds"
          multiple
          collapse-tags
          collapse-tags-tooltip
          filterable
          style="width: 100%"
        >
          <el-option
            v-for="it in items"
            :key="it.id"
            :value="it.id"
            :label="it.name"
          />
        </el-select>
        <el-alert
          v-else
          :title="t('ai.injectItemsEmpty')"
          type="info"
          :closable="false"
        />
        <div class="hint">{{ t('ai.injectItemsHint') }}</div>
      </el-form-item>

      <p v-if="mode !== 'rewrite'" class="auto-events">
        {{ t('ai.injectAutoEvents') }}
      </p>
    </div>

    <div class="actions">
      <el-button
        v-if="phase !== 'streaming'"
        type="primary"
        :disabled="!canStart"
        @click="start"
      >
        {{ phase === 'idle' ? t('ai.start') : '重新生成' }}
      </el-button>
      <el-button v-else type="danger" @click="stop">{{ t('ai.stop') }}</el-button>
    </div>

    <div class="result-area">
      <div class="result-header">
        <span class="phase">
          <span v-if="phase === 'streaming'" class="dot streaming" />
          <span v-else-if="phase === 'done'" class="dot done" />
          <span v-else-if="phase === 'error'" class="dot error" />
          {{
            phase === 'streaming'
              ? t('ai.streaming')
              : phase === 'done'
              ? t('ai.done')
              : phase === 'error'
              ? t('ai.error')
              : ''
          }}
        </span>
        <span class="counter">{{ result.length }} 字</span>
      </div>
      <div class="result-body">
        <pre v-if="result">{{ result }}</pre>
        <div v-else class="result-empty">点击上方「{{ t('ai.start') }}」开始生成。</div>
      </div>
    </div>

    <template #footer>
      <div class="footer-actions" v-if="phase === 'done' && result">
        <el-button @click="close">{{ t('ai.discard') }}</el-button>
        <template v-if="mode === 'rewrite'">
          <el-button type="primary" @click="onReplaceSelection">{{ t('ai.replace') }}</el-button>
        </template>
        <template v-else-if="mode === 'continue'">
          <el-button @click="onAppend">{{ t('ai.appendToEnd') }}</el-button>
          <el-button type="primary" @click="onInsert">{{ t('ai.insertAtCursor') }}</el-button>
        </template>
        <template v-else>
          <el-button @click="onAppend">{{ t('ai.appendToEnd') }}</el-button>
          <el-button type="primary" @click="onAccept">{{ t('ai.accept') }}</el-button>
        </template>
      </div>
    </template>
  </el-drawer>
</template>

<style scoped>
.form {
  margin-bottom: 16px;
}
.form .hint {
  color: #86909c;
  font-size: 12px;
  margin-top: 2px;
  line-height: 1.5;
}
.role-hint {
  color: #86909c;
  font-size: 12px;
  margin-left: 8px;
}
.auto-events {
  margin: 0 0 12px;
  padding: 8px 12px;
  background: #f0f9ff;
  color: #4080ff;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.5;
}
.actions {
  margin-bottom: 16px;
}
.selection-box {
  background: #f7f8fa;
  border-radius: 8px;
  padding: 12px;
  max-height: 160px;
  overflow-y: auto;
}
.selection-box .label {
  font-size: 12px;
  color: #86909c;
  margin-bottom: 4px;
}
.selection-text {
  font-size: 13px;
  color: #4e5969;
  white-space: pre-wrap;
  line-height: 1.6;
}
.result-area {
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  min-height: 240px;
}
.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid #f2f3f5;
  font-size: 12px;
  color: #86909c;
}
.phase {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.dot.streaming {
  background: #4080ff;
  animation: pulse 1s infinite;
}
.dot.done { background: #00b42a; }
.dot.error { background: #f53f3f; }
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.counter { font-variant-numeric: tabular-nums; }
.result-body {
  padding: 12px;
  flex: 1;
  overflow-y: auto;
  max-height: 50vh;
}
.result-body pre {
  font-family: -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  white-space: pre-wrap;
  word-wrap: break-word;
  margin: 0;
  line-height: 1.7;
  font-size: 14px;
}
.result-empty {
  color: #c9cdd4;
  text-align: center;
  padding: 40px 0;
  font-size: 13px;
}
.footer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
