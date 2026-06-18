<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { settingsApi } from '../api/settings'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const { t } = useI18n()

// 各预设的默认值,选中后填入表单(model/base_url 可继续修改)
const PRESETS = [
  {
    key: 'claude',
    descKey: 'aiConfig.presetClaudeDesc',
    defaultModel: 'claude-opus-4-7',
    defaultBaseUrl: '',
    needsKey: true,
  },
  {
    key: 'openai',
    descKey: 'aiConfig.presetCustomDesc',
    defaultModel: 'gpt-4o',
    defaultBaseUrl: '',
    needsKey: true,
  },
  {
    key: 'deepseek',
    descKey: 'aiConfig.presetDeepseekDesc',
    defaultModel: 'deepseek/deepseek-chat',
    defaultBaseUrl: '',
    needsKey: true,
  },
  {
    key: 'qwen',
    descKey: 'aiConfig.presetQwenDesc',
    defaultModel: 'dashscope/qwen-max',
    defaultBaseUrl: '',
    needsKey: true,
  },
  {
    key: 'ollama',
    descKey: 'aiConfig.presetOllamaDesc',
    defaultModel: 'ollama/qwen2.5:14b',
    defaultBaseUrl: 'http://localhost:11434',
    needsKey: false,
  },
  {
    key: 'gemma_e4b',
    descKey: 'aiConfig.presetGemmaE4bDesc',
    defaultModel: 'ollama/ge4e4b_un:latest',
    defaultBaseUrl: 'http://localhost:11434',
    needsKey: false,
  },
  {
    key: 'gemma_26b',
    descKey: 'aiConfig.presetGemma26bDesc',
    defaultModel: 'ollama/ge426b:latest',
    defaultBaseUrl: 'http://localhost:11434',
    needsKey: false,
  },
  {
    key: 'custom',
    descKey: 'aiConfig.presetCustomDesc',
    defaultModel: '',
    defaultBaseUrl: '',
    needsKey: true,
  },
]

const form = ref({
  provider: 'claude',
  model: '',
  base_url: '',
  api_key: '',
  temperature: 0.7,
  max_tokens: 4096,
})
const apiKeyExisting = ref(false)
const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const testResult = ref(null) // {ok: boolean, message?: string, sample?: string}

const currentPreset = computed(() => PRESETS.find((p) => p.key === form.value.provider))
// 预设 key 形如 gemma_e4b → 拼成 i18n key presetGemmaE4b。
// 这里把下划线段首字母大写后拼起来。
function presetLabel(key) {
  const camel = key.replace(/(^|_)([a-z0-9])/g, (_, __, ch) => ch.toUpperCase())
  return t(`aiConfig.preset${camel}`)
}

watch(
  () => props.modelValue,
  async (v) => {
    if (!v) return
    loading.value = true
    try {
      const data = await settingsApi.getAI()
      form.value = {
        provider: data.provider || 'claude',
        model: data.model || 'claude-opus-4-7',
        base_url: data.base_url || '',
        api_key: '',
        temperature: data.temperature ?? 0.7,
        max_tokens: data.max_tokens ?? 4096,
      }
      apiKeyExisting.value = data.api_key_set
      testResult.value = null
    } catch (e) {
      ElMessage.error(e.message || t('common.failed'))
    } finally {
      loading.value = false
    }
  }
)

function selectPreset(key) {
  const preset = PRESETS.find((p) => p.key === key)
  if (!preset) return
  form.value.provider = key
  testResult.value = null
  // 切换预设时,把模型名直接覆盖成预设值。如果用户改过模型名又切预设,
  // 切换的语义就是"用这个预设的默认模型",所以无脑覆盖。
  if (preset.defaultModel) {
    form.value.model = preset.defaultModel
  }
  if (preset.defaultBaseUrl) {
    form.value.base_url = preset.defaultBaseUrl
  }
}

async function onSave() {
  if (!form.value.model.trim()) {
    ElMessage.warning(t('aiConfig.modelLabel'))
    return
  }
  saving.value = true
  try {
    const payload = {
      provider: form.value.provider,
      model: form.value.model.trim(),
      base_url: form.value.base_url.trim() || null,
      temperature: Number(form.value.temperature),
      max_tokens: Number(form.value.max_tokens),
    }
    if (form.value.api_key) {
      payload.api_key = form.value.api_key
    } else {
      payload.keep_existing_key = true
    }
    await settingsApi.updateAI(payload)
    ElMessage.success(t('aiConfig.saved'))
    emit('saved')
    emit('update:modelValue', false)
  } catch (e) {
    ElMessage.error(e.message || t('common.failed'))
  } finally {
    saving.value = false
  }
}

// 测试连接:先把当前表单保存(否则后端拿不到刚填的 key/model),再调 /test。
// 这里的代价是用户即便没点保存,只要点了测试,配置就被持久化。
// 这是有意为之——绝大多数用户测试通过后想要保留这份配置。
async function onTest() {
  if (!form.value.model.trim()) {
    ElMessage.warning(t('aiConfig.modelLabel'))
    return
  }
  testing.value = true
  testResult.value = null
  try {
    const payload = {
      provider: form.value.provider,
      model: form.value.model.trim(),
      base_url: form.value.base_url.trim() || null,
      temperature: Number(form.value.temperature),
      max_tokens: Number(form.value.max_tokens),
    }
    if (form.value.api_key) {
      payload.api_key = form.value.api_key
    } else {
      payload.keep_existing_key = true
    }
    await settingsApi.updateAI(payload)
    apiKeyExisting.value = apiKeyExisting.value || !!form.value.api_key
    form.value.api_key = ''
    const res = await settingsApi.testAI()
    testResult.value = res
    if (res.ok) {
      ElMessage.success(t('aiConfig.testOk'))
      emit('saved')
    } else {
      ElMessage.error(res.message || t('aiConfig.testFailed'))
    }
  } catch (e) {
    testResult.value = { ok: false, message: e.message || t('aiConfig.testFailed') }
    ElMessage.error(e.message || t('aiConfig.testFailed'))
  } finally {
    testing.value = false
  }
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    :title="t('aiConfig.title')"
    width="640px"
    v-loading="loading"
  >
    <div class="presets">
      <div
        v-for="p in PRESETS"
        :key="p.key"
        class="preset"
        :class="{ active: form.provider === p.key }"
        @click="selectPreset(p.key)"
      >
        <span class="preset-check" :class="{ checked: form.provider === p.key }">
          <svg v-if="form.provider === p.key" viewBox="0 0 16 16" width="12" height="12">
            <path
              d="M3.5 8.5l3 3 6-7"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </span>
        <div class="preset-name">{{ presetLabel(p.key) }}</div>
        <div class="preset-desc">{{ t(p.descKey) }}</div>
      </div>
    </div>

    <el-form label-position="top" class="form">
      <el-form-item :label="t('aiConfig.modelLabel')" required>
        <el-input v-model="form.model" placeholder="model name" />
        <div class="hint">{{ t('aiConfig.modelHint') }}</div>
      </el-form-item>

      <el-form-item :label="t('aiConfig.baseUrlLabel')">
        <el-input v-model="form.base_url" placeholder="https://..." />
        <div class="hint">{{ t('aiConfig.baseUrlHint') }}</div>
      </el-form-item>

      <el-form-item v-if="currentPreset?.needsKey" :label="t('aiConfig.apiKeyLabel')">
        <el-input
          v-model="form.api_key"
          type="password"
          show-password
          :placeholder="apiKeyExisting ? t('aiConfig.apiKeyExisting') : t('aiConfig.apiKeyPlaceholder')"
        />
      </el-form-item>

      <div class="grid">
        <el-form-item :label="t('aiConfig.temperatureLabel')">
          <el-input-number
            v-model="form.temperature"
            :min="0"
            :max="2"
            :step="0.1"
            :precision="1"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item :label="t('aiConfig.maxTokensLabel')">
          <el-input-number
            v-model="form.max_tokens"
            :min="128"
            :max="32768"
            :step="512"
            style="width: 100%"
          />
        </el-form-item>
      </div>

      <p class="docs">
        {{ t('aiConfig.docsHint') }}
        <a href="https://docs.litellm.ai/docs/providers" target="_blank" rel="noopener">
          docs.litellm.ai
        </a>
      </p>
    </el-form>

    <template #footer>
      <div class="footer">
        <div class="footer-left">
          <el-button :loading="testing" :disabled="saving" @click="onTest">
            {{ t('aiConfig.testButton') }}
          </el-button>
          <span
            v-if="testResult"
            class="test-result"
            :class="{ ok: testResult.ok, fail: !testResult.ok }"
          >
            <template v-if="testResult.ok">
              ✓ {{ t('aiConfig.testOk') }}{{ testResult.sample ? ` · ${testResult.sample}` : '' }}
            </template>
            <template v-else>
              ✗ {{ testResult.message || t('aiConfig.testFailed') }}
            </template>
          </span>
        </div>
        <div class="footer-right">
          <el-button :disabled="testing" @click="emit('update:modelValue', false)">
            {{ t('common.cancel') }}
          </el-button>
          <el-button type="primary" :loading="saving" :disabled="testing" @click="onSave">
            {{ t('common.save') }}
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.presets {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 20px;
}
.preset {
  position: relative;
  padding: 10px 12px;
  padding-right: 32px;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.preset:hover {
  border-color: #c9d2ff;
}
.preset.active {
  border-color: #4080ff;
  background: #ecf5ff;
}
.preset-check {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 16px;
  height: 16px;
  border: 1px solid #c9cdd4;
  border-radius: 4px;
  background: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  transition: background 0.15s, border-color 0.15s;
}
.preset-check.checked {
  background: #4080ff;
  border-color: #4080ff;
}
.preset-name {
  font-size: 13px;
  font-weight: 600;
  color: #1f2329;
  margin-bottom: 2px;
}
.preset-desc {
  font-size: 11px;
  color: #86909c;
  line-height: 1.4;
}
.form .hint {
  color: #86909c;
  font-size: 12px;
  margin-top: 2px;
}
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.docs {
  margin: 8px 0 0;
  font-size: 12px;
  color: #86909c;
}
.docs a {
  color: #4080ff;
  text-decoration: none;
}
.docs a:hover {
  text-decoration: underline;
}

.footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.footer-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}
.footer-right {
  display: flex;
  gap: 8px;
}
.test-result {
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.test-result.ok {
  color: #10b981;
}
.test-result.fail {
  color: #ef4444;
}
</style>
