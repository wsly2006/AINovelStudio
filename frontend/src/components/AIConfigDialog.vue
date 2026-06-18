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

const activeTab = ref('writing')

const writingForm = ref({
  provider: 'claude',
  model: '',
  base_url: '',
  api_key: '',
  temperature: 0.7,
  max_tokens: 4096,
})
const writingApiKeyExisting = ref(false)

const reviewEnabled = ref(false)
const reviewForm = ref({
  provider: 'claude',
  model: '',
  base_url: '',
  api_key: '',
  temperature: 0.3,
  max_tokens: 2000,
})
const reviewApiKeyExisting = ref(false)

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const testResult = ref(null)

// 当前 tab 对应的表单引用,简化模板
const form = computed(() => (activeTab.value === 'writing' ? writingForm.value : reviewForm.value))
const apiKeyExisting = computed(() =>
  activeTab.value === 'writing' ? writingApiKeyExisting.value : reviewApiKeyExisting.value
)
const currentPreset = computed(() => PRESETS.find((p) => p.key === form.value.provider))

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
      writingForm.value = {
        provider: data.provider || 'claude',
        model: data.model || 'claude-opus-4-7',
        base_url: data.base_url || '',
        api_key: '',
        temperature: data.temperature ?? 0.7,
        max_tokens: data.max_tokens ?? 4096,
      }
      writingApiKeyExisting.value = data.api_key_set
      reviewEnabled.value = data.review_configured
      // 即便后端未配置审稿(review_configured=false),也把已有字段回填,
      // 用户切到 tab 后改起来更顺手
      reviewForm.value = {
        provider: data.review_provider || data.provider || 'claude',
        model: data.review_model || '',
        base_url: data.review_base_url || '',
        api_key: '',
        temperature: data.review_temperature ?? 0.3,
        max_tokens: data.review_max_tokens ?? 2000,
      }
      reviewApiKeyExisting.value = data.review_api_key_set
      testResult.value = null
      activeTab.value = 'writing'
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
  if (preset.defaultModel) form.value.model = preset.defaultModel
  if (preset.defaultBaseUrl) form.value.base_url = preset.defaultBaseUrl
}

// 保存当前 tab 对应的角色;其余 tab 不动
async function persist({ silent = false } = {}) {
  if (activeTab.value === 'writing') {
    if (!writingForm.value.model.trim()) {
      ElMessage.warning(t('aiConfig.modelLabel'))
      return false
    }
    const payload = {
      provider: writingForm.value.provider,
      model: writingForm.value.model.trim(),
      base_url: writingForm.value.base_url.trim() || null,
      temperature: Number(writingForm.value.temperature),
      max_tokens: Number(writingForm.value.max_tokens),
    }
    if (writingForm.value.api_key) payload.api_key = writingForm.value.api_key
    else payload.keep_existing_key = true
    await settingsApi.updateAI(payload)
    if (writingForm.value.api_key) {
      writingApiKeyExisting.value = true
      writingForm.value.api_key = ''
    }
  } else {
    if (!reviewEnabled.value) {
      await settingsApi.updateReview({ enabled: false })
      reviewApiKeyExisting.value = false
    } else {
      if (!reviewForm.value.model.trim()) {
        ElMessage.warning(t('aiConfig.modelLabel'))
        return false
      }
      const payload = {
        enabled: true,
        provider: reviewForm.value.provider,
        model: reviewForm.value.model.trim(),
        base_url: reviewForm.value.base_url.trim() || null,
        temperature: Number(reviewForm.value.temperature),
        max_tokens: Number(reviewForm.value.max_tokens),
      }
      if (reviewForm.value.api_key) payload.api_key = reviewForm.value.api_key
      else payload.keep_existing_key = true
      await settingsApi.updateReview(payload)
      if (reviewForm.value.api_key) {
        reviewApiKeyExisting.value = true
        reviewForm.value.api_key = ''
      }
    }
  }
  if (!silent) ElMessage.success(t('aiConfig.saved'))
  emit('saved')
  return true
}

async function onSave() {
  saving.value = true
  try {
    const ok = await persist()
    if (ok) emit('update:modelValue', false)
  } catch (e) {
    ElMessage.error(e.message || t('common.failed'))
  } finally {
    saving.value = false
  }
}

// 测试连接:跟以前一样,先静默保存当前 tab 再测,不强迫用户先点保存
async function onTest() {
  testing.value = true
  testResult.value = null
  try {
    const ok = await persist({ silent: true })
    if (!ok) {
      testing.value = false
      return
    }
    const res = await settingsApi.testAI(activeTab.value)
    testResult.value = res
    if (res.ok) ElMessage.success(t('aiConfig.testOk'))
    else ElMessage.error(res.message || t('aiConfig.testFailed'))
  } catch (e) {
    testResult.value = { ok: false, message: e.message || t('aiConfig.testFailed') }
    ElMessage.error(e.message || t('aiConfig.testFailed'))
  } finally {
    testing.value = false
  }
}

// 切 tab 时清掉上一个 tab 的测试结果,免得两边的状态混在一起
watch(activeTab, () => {
  testResult.value = null
})
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    :title="t('aiConfig.title')"
    width="680px"
  >
    <div v-loading="loading">
    <el-tabs v-model="activeTab" class="role-tabs">
      <el-tab-pane :label="t('aiConfig.tabWriting')" name="writing" />
      <el-tab-pane :label="t('aiConfig.tabReview')" name="review" />
    </el-tabs>

    <p class="tab-hint">
      {{ activeTab === 'writing' ? t('aiConfig.tabWritingHint') : t('aiConfig.tabReviewHint') }}
    </p>

    <!-- 审稿启用开关 + 未启用提示 -->
    <div v-if="activeTab === 'review'" class="review-toggle">
      <el-switch v-model="reviewEnabled" />
      <span class="toggle-label">{{ t('aiConfig.reviewEnabledLabel') }}</span>
      <span class="toggle-hint">{{ t('aiConfig.reviewEnabledHint') }}</span>
    </div>
    <p v-if="activeTab === 'review' && !reviewEnabled" class="fallback-tip">
      {{ t('aiConfig.reviewFallbackTip') }}
    </p>

    <template v-if="activeTab === 'writing' || reviewEnabled">
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
    </template>
    </div>

    <template #footer>
      <div class="footer">
        <div class="footer-left">
          <el-button
            v-if="activeTab === 'writing' || reviewEnabled"
            :loading="testing"
            :disabled="saving"
            @click="onTest"
          >
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
.role-tabs {
  margin-bottom: 4px;
}
.tab-hint {
  margin: 0 0 16px;
  font-size: 12px;
  color: #86909c;
  line-height: 1.5;
}
.review-toggle {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #f7f8fa;
  border-radius: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.toggle-label {
  font-size: 13px;
  color: #1f2329;
  font-weight: 500;
}
.toggle-hint {
  font-size: 12px;
  color: #86909c;
  flex-basis: 100%;
  padding-left: 50px;
}
.fallback-tip {
  margin: 0 0 16px;
  padding: 8px 12px;
  background: #fff7e6;
  color: #ff7d00;
  font-size: 12px;
  border-radius: 6px;
}
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
