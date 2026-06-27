<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Plus } from '@element-plus/icons-vue'
import { voiceProfileApi } from '../api/voiceProfile'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  projectId: { type: Number, default: null },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const QUIRK_PRESETS = [
  '段落末尾常用半句留白,而非完整收束',
  '人物常用具体动作替代心理描述',
  '少用形容词堆砌,多用短句白描',
  '避免开头/结尾用"突然"',
  '不用"仿佛""宛如"开头的比喻',
  '对白前后必有动作或视线落点,不让引号悬空',
]

const STYLE_PRESETS = [
  {
    label: '短句白描',
    snippet: '偏短句白描,平均句长 12-18 字,避免长定语从句和"仿佛...一般"句式。',
  },
  {
    label: '节奏跳跃',
    snippet: '段落节奏不要均匀,允许长短交替;偶尔用一句话独立成段表停顿。',
  },
  {
    label: '少用 AI 套语',
    snippet: '避免常见 AI 套语:不可名状、令人窒息、深不见底、说不出的感觉、命运的齿轮。',
  },
  {
    label: '感官细节',
    snippet: '场景描写优先调用具体感官(温度、气味、声音),不要泛泛"环境很压抑"。',
  },
  {
    label: '允许冗余',
    snippet: '人类不会句句最精炼。允许有"嗯""那个""我说"等口头停顿,允许人物半截话被打断。',
  },
]

const loading = ref(false)
const saving = ref(false)
const profile = ref({ quirks: [], style_notes: '' })
const initial = ref({ quirks: [], style_notes: '' })
const quirkInput = ref('')

const dirty = computed(() => {
  const a = profile.value
  const b = initial.value
  if ((a.style_notes || '') !== (b.style_notes || '')) return true
  if (a.quirks.length !== b.quirks.length) return true
  for (let i = 0; i < a.quirks.length; i++) {
    if (a.quirks[i] !== b.quirks[i]) return true
  }
  return false
})

const charCount = computed(() => (profile.value.style_notes || '').length)
const hasContent = computed(
  () => profile.value.quirks.length > 0 || (profile.value.style_notes || '').trim().length > 0
)

async function load() {
  if (!props.projectId) return
  loading.value = true
  try {
    const data = await voiceProfileApi.get(props.projectId)
    if (data) {
      profile.value = {
        quirks: [...(data.quirks || [])],
        style_notes: data.style_notes || '',
      }
    } else {
      profile.value = { quirks: [], style_notes: '' }
    }
    initial.value = {
      quirks: [...profile.value.quirks],
      style_notes: profile.value.style_notes,
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

watch(
  () => props.modelValue,
  (v) => {
    if (v) load()
    else {
      quirkInput.value = ''
    }
  },
)

function addQuirk() {
  const v = (quirkInput.value || '').trim()
  if (!v) return
  if (profile.value.quirks.length >= 30) {
    ElMessage.warning('语癖最多 30 条')
    return
  }
  if (profile.value.quirks.includes(v)) {
    ElMessage.info('已存在')
    quirkInput.value = ''
    return
  }
  profile.value.quirks.push(v.slice(0, 200))
  quirkInput.value = ''
}

function addPreset(text) {
  if (profile.value.quirks.includes(text)) return
  if (profile.value.quirks.length >= 30) {
    ElMessage.warning('语癖最多 30 条')
    return
  }
  profile.value.quirks.push(text)
}

function removeQuirk(idx) {
  profile.value.quirks.splice(idx, 1)
}

function insertStylePreset(snippet) {
  const cur = (profile.value.style_notes || '').trimEnd()
  profile.value.style_notes = cur ? `${cur}\n${snippet}` : snippet
}

async function save() {
  if (!props.projectId) return
  saving.value = true
  try {
    const updated = await voiceProfileApi.upsert(props.projectId, {
      quirks: profile.value.quirks,
      style_notes: profile.value.style_notes || null,
    })
    initial.value = {
      quirks: [...updated.quirks],
      style_notes: updated.style_notes || '',
    }
    profile.value = {
      quirks: [...updated.quirks],
      style_notes: updated.style_notes || '',
    }
    ElMessage.success('已保存,下次生成会自动注入')
    emit('saved', updated)
    emit('update:modelValue', false)
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function onClear() {
  try {
    await ElMessageBox.confirm(
      '清空整个作者声音档案?此操作不可撤销。',
      '清空',
      { type: 'warning', confirmButtonText: '清空', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await voiceProfileApi.remove(props.projectId)
    profile.value = { quirks: [], style_notes: '' }
    initial.value = { quirks: [], style_notes: '' }
    ElMessage.success('已清空')
    emit('saved', null)
  } catch (e) {
    // 没建过 profile 时后端返回 404,这里当作"已经是空"
    if (e?.response?.status === 404) {
      profile.value = { quirks: [], style_notes: '' }
      initial.value = { quirks: [], style_notes: '' }
    } else {
      ElMessage.error(e?.response?.data?.detail || e.message || '清空失败')
    }
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
    title="作者声音"
    width="820px"
    :close-on-click-modal="false"
  >
    <div v-loading="loading" class="voice-body">
      <p class="intro">
        把作者的个人语癖和风格习惯记下来。每次 AI 生成 / 续写 / 改写本作时,
        会把这段附在 system prompt 末尾,让产物不被通用 AI 文风覆盖。
        <span class="intro-note">— 仅作用于当前工程</span>
      </p>

      <section class="section">
        <div class="section-head">
          <span class="section-title">语癖 ({{ profile.quirks.length }} / 30)</span>
          <span class="section-hint">短句清单形式。AI 会拿来当"个人标签"穿插进文本</span>
        </div>
        <div class="quirk-input-row">
          <el-input
            v-model="quirkInput"
            placeholder="一条一条加,如:他总把'当然了'挂在嘴边"
            maxlength="200"
            @keyup.enter="addQuirk"
            clearable
          />
          <el-button type="primary" :icon="Plus" @click="addQuirk" :disabled="!quirkInput.trim()">
            添加
          </el-button>
        </div>
        <div class="quirk-list" v-if="profile.quirks.length">
          <div v-for="(q, i) in profile.quirks" :key="i" class="quirk-row">
            <span class="quirk-text">{{ q }}</span>
            <el-button text size="small" :icon="Delete" class="quirk-del" @click="removeQuirk(i)" />
          </div>
        </div>
        <div v-else class="quirk-empty">还没添加语癖,可以从下面预设里挑几条起步 ↓</div>

        <div class="presets-row">
          <span class="presets-label">快速添加:</span>
          <el-button
            v-for="p in QUIRK_PRESETS"
            :key="p"
            size="small"
            class="preset-btn"
            :disabled="profile.quirks.includes(p)"
            @click="addPreset(p)"
          >
            + {{ p }}
          </el-button>
        </div>
      </section>

      <section class="section">
        <div class="section-head">
          <span class="section-title">风格描述</span>
          <span class="section-hint">整段写,描述节奏 / 句法 / 视角偏好等</span>
        </div>
        <el-input
          v-model="profile.style_notes"
          type="textarea"
          :rows="6"
          maxlength="4000"
          show-word-limit
          placeholder="例:偏白描,少形容词堆砌;允许段落节奏不均匀;场景描写优先调用具体感官"
        />
        <div class="char-meta">{{ charCount }} / 4000</div>
        <div class="presets-row">
          <span class="presets-label">风格预设:</span>
          <el-button
            v-for="p in STYLE_PRESETS"
            :key="p.label"
            size="small"
            class="preset-btn"
            @click="insertStylePreset(p.snippet)"
          >
            + {{ p.label }}
          </el-button>
        </div>
      </section>
    </div>

    <template #footer>
      <el-button v-if="hasContent" type="danger" link @click="onClear">清空整份档案</el-button>
      <span class="spacer" />
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :loading="saving" :disabled="!dirty" @click="save">
        保存
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.voice-body {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.intro {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: #4e5969;
  background: #f5f7fa;
  padding: 10px 14px;
  border-radius: 8px;
  border-left: 3px solid #4080ff;
}
.intro-note {
  color: #86909c;
  margin-left: 4px;
}
.section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.section-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2329;
}
.section-hint {
  font-size: 12px;
  color: #86909c;
}
.quirk-input-row {
  display: flex;
  gap: 8px;
}
.quirk-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  padding: 6px;
  background: #fafbfc;
  max-height: 180px;
  overflow-y: auto;
}
.quirk-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: #fff;
  border-radius: 6px;
  font-size: 13px;
  color: #1f2329;
}
.quirk-row:hover {
  background: #f2f3f5;
}
.quirk-text {
  flex: 1;
  line-height: 1.5;
}
.quirk-del {
  opacity: 0.6;
  color: #86909c !important;
}
.quirk-row:hover .quirk-del {
  opacity: 1;
  color: #f53f3f !important;
}
.quirk-empty {
  font-size: 12px;
  color: #86909c;
  padding: 12px;
  text-align: center;
  background: #fafbfc;
  border: 1px dashed #e5e6eb;
  border-radius: 8px;
}
.presets-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.presets-label {
  font-size: 12px;
  color: #86909c;
  margin-right: 4px;
}
.preset-btn {
  white-space: normal;
  height: auto;
  padding: 4px 10px;
  line-height: 1.4;
  text-align: left;
  font-weight: normal;
}
.char-meta {
  font-size: 12px;
  color: #86909c;
  text-align: right;
}
.spacer {
  flex: 1;
}
</style>
