<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import client from '../api/client'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  projectId: { type: Number, default: null },
  // 章节列表(已按 order_index 排序),用于「起始章节」下拉
  chapters: { type: Array, default: () => [] },
  // 当前编辑器选中的章节,作为默认起点
  defaultChapterId: { type: Number, default: null },
  // 工程的人物 / 世界观 / 物品(同 AIGenerateDrawer 的注入)
  characters: { type: Array, default: () => [] },
  worldEntities: { type: Array, default: () => [] },
  items: { type: Array, default: () => [] },
  defaultTargetWordCount: { type: Number, default: 4000 },
})
const emit = defineEmits(['update:modelValue', 'started'])

const startChapterId = ref(null)
const count = ref(3)
const targetWordCount = ref(4000)
const mode = ref('auto_fix')
const scoreThreshold = ref(70)
const extraInstruction = ref('')
const selectedCharacterIds = ref([])
const selectedWorldIds = ref([])
const selectedItemIds = ref([])
const submitting = ref(false)

const KIND_LABEL = { location: '地点', organization: '组织', concept: '概念' }

// 默认从「当前章节」或「第一个空白章节」开始,后者更贴合「连写」场景
const firstEmptyChapter = computed(
  () => props.chapters.find((c) => (c.word_count || 0) === 0) || null
)

watch(
  () => props.modelValue,
  (v) => {
    if (!v) return
    targetWordCount.value = Number(props.defaultTargetWordCount) || 4000
    extraInstruction.value = ''
    mode.value = 'auto_fix'
    scoreThreshold.value = 70
    count.value = Math.min(3, Math.max(1, props.chapters.length))
    // 优先用 prop 指定;否则用第一个空章;再不行用第一章
    startChapterId.value =
      props.defaultChapterId ||
      firstEmptyChapter.value?.id ||
      props.chapters[0]?.id ||
      null
    // 默认勾选主角,主流程默认不带世界观 / 物品
    selectedCharacterIds.value = props.characters
      .filter((c) => c.role === '主角')
      .map((c) => c.id)
    selectedWorldIds.value = []
    selectedItemIds.value = []
  }
)

// 起点 + count 决定实际会写哪些章节,展示给用户确认
const previewChapters = computed(() => {
  if (!startChapterId.value) return []
  const list = props.chapters
  const i = list.findIndex((c) => c.id === startChapterId.value)
  if (i < 0) return []
  return list.slice(i, i + count.value)
})

async function onSubmit() {
  if (!props.projectId || !startChapterId.value || submitting.value) return
  submitting.value = true
  try {
    const body = {
      start_chapter_id: startChapterId.value,
      count: count.value,
      target_word_count: targetWordCount.value,
      extra_instruction: extraInstruction.value.trim() || null,
      character_ids: [...selectedCharacterIds.value],
      world_entity_ids: [...selectedWorldIds.value],
      item_ids: [...selectedItemIds.value],
      mode: mode.value,
      score_threshold: scoreThreshold.value,
    }
    const resp = await client.post(
      `/projects/${props.projectId}/ai/auto-write`,
      body,
      { timeout: 30000 }
    )
    const data = resp.data || {}
    emit('started', {
      taskId: data.task_id,
      chapterIds: data.chapter_ids || [],
      total: previewChapters.value.length,
      mode: mode.value,
      scoreThreshold: scoreThreshold.value,
    })
    emit('update:modelValue', false)
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e.message || '启动失败')
  } finally {
    submitting.value = false
  }
}

function close() {
  emit('update:modelValue', false)
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    title="AI 自动连写"
    width="640px"
  >
    <div class="auto-write-form">
      <el-form label-width="100px">
        <el-form-item label="起始章节">
          <el-select
            v-model="startChapterId"
            filterable
            style="width: 100%"
            placeholder="从这一章开始往后连写"
          >
            <el-option
              v-for="c in chapters"
              :key="c.id"
              :value="c.id"
              :label="`第 ${c.order_index} 章 ${c.title || ''}`"
            >
              <span style="float: left">第 {{ c.order_index }} 章 {{ c.title || '' }}</span>
              <span class="row-hint">{{ c.word_count || 0 }} 字</span>
            </el-option>
          </el-select>
          <div class="hint">默认从第一个空白章节开始,可改为任意一章</div>
        </el-form-item>

        <el-form-item label="连写多少章">
          <el-input-number v-model="count" :min="1" :max="50" :step="1" style="width: 160px" />
          <span class="hint inline">实际可写 {{ previewChapters.length }} 章</span>
        </el-form-item>

        <el-form-item label="每章字数">
          <el-input-number
            v-model="targetWordCount"
            :min="200"
            :max="20000"
            :step="500"
            style="width: 160px"
          />
        </el-form-item>

        <el-form-item label="质量模式">
          <el-radio-group v-model="mode">
            <el-radio value="strict">严格</el-radio>
            <el-radio value="auto_fix">自纠</el-radio>
            <el-radio value="all_through">全推</el-radio>
          </el-radio-group>
          <div class="hint">
            <strong>严格</strong>:节拍未兑现 / 评分不够时重试 1 次,仍不达标则停下;
            <strong>自纠</strong>:重试 1 次后无论结果都继续(默认);
            <strong>全推</strong>:不重试,一路写到底
          </div>
        </el-form-item>

        <el-form-item label="评分阈值">
          <el-input-number
            v-model="scoreThreshold"
            :min="0"
            :max="100"
            :step="5"
            style="width: 160px"
          />
          <span class="hint inline">综合分低于这个值会触发重试(自纠 / 严格档)</span>
        </el-form-item>

        <el-form-item label="额外要求">
          <el-input
            v-model="extraInstruction"
            type="textarea"
            :rows="2"
            placeholder="对每一章都生效的额外要求,如「保留紧张感」「降低主角光环」等"
          />
        </el-form-item>

        <el-form-item label="注入人物">
          <el-select
            v-if="characters.length"
            v-model="selectedCharacterIds"
            multiple
            collapse-tags
            collapse-tags-tooltip
            filterable
            style="width: 100%"
          >
            <el-option v-for="c in characters" :key="c.id" :value="c.id" :label="c.name">
              <span>{{ c.name }}</span>
              <span v-if="c.role" class="row-hint">{{ c.role }}</span>
            </el-option>
          </el-select>
          <el-alert v-else title="暂无人物档案" type="info" :closable="false" />
        </el-form-item>

        <el-form-item label="注入世界观" v-if="worldEntities.length">
          <el-select
            v-model="selectedWorldIds"
            multiple
            collapse-tags
            collapse-tags-tooltip
            filterable
            style="width: 100%"
          >
            <el-option v-for="e in worldEntities" :key="e.id" :value="e.id" :label="e.name">
              <span>{{ e.name }}</span>
              <span class="row-hint">{{ KIND_LABEL[e.kind] || e.kind }}</span>
            </el-option>
          </el-select>
        </el-form-item>

        <el-form-item label="注入物品" v-if="items.length">
          <el-select
            v-model="selectedItemIds"
            multiple
            collapse-tags
            collapse-tags-tooltip
            filterable
            style="width: 100%"
          >
            <el-option v-for="it in items" :key="it.id" :value="it.id" :label="it.name" />
          </el-select>
        </el-form-item>
      </el-form>

      <div v-if="previewChapters.length" class="preview">
        <div class="preview-title">将会顺序写这些章节(每章生成完会自动索引 / 对账 / 评分):</div>
        <ul>
          <li v-for="c in previewChapters" :key="c.id">
            第 {{ c.order_index }} 章 {{ c.title || '' }}
            <span v-if="(c.word_count || 0) > 0" class="warn">
              · 已有 {{ c.word_count }} 字,会被覆盖(自动留版本)
            </span>
          </li>
        </ul>
      </div>
    </div>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button
        type="primary"
        :loading="submitting"
        :disabled="!startChapterId || !previewChapters.length"
        @click="onSubmit"
      >
        开始连写
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.auto-write-form {
  max-height: 60vh;
  overflow-y: auto;
}
.hint {
  color: #86909c;
  font-size: 12px;
  margin-top: 4px;
  line-height: 1.6;
}
.hint.inline {
  margin-left: 8px;
}
.row-hint {
  color: #86909c;
  font-size: 12px;
  margin-left: 8px;
  float: right;
}
.preview {
  margin-top: 12px;
  padding: 12px;
  background: #f7f8fa;
  border-radius: 6px;
  font-size: 13px;
}
.preview-title {
  margin-bottom: 6px;
  color: #4e5969;
}
.preview ul {
  margin: 0;
  padding-left: 20px;
  line-height: 1.8;
}
.preview .warn {
  color: #ff7d00;
  font-size: 12px;
}
</style>
