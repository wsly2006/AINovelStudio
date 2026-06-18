<script setup>
import { onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElTooltip } from 'element-plus'
import { MagicStick, Edit, EditPen, Document } from '@element-plus/icons-vue'
import { useAIInfoStore } from '../stores/aiInfo'

const emit = defineEmits(['generate', 'continue', 'rewrite', 'summarize'])

const { t } = useI18n()
const info = useAIInfoStore()

onMounted(() => {
  if (!info.loaded) info.refresh()
})

const disabled = computed(() => !info.configured)
const tooltip = computed(() =>
  disabled.value ? t('ai.notConfigured') : `${t('ai.model')}: ${info.model}`
)
</script>

<template>
  <div class="ai-toolbar">
    <el-tooltip :content="tooltip" placement="bottom">
      <span class="badge" :class="{ off: disabled }">
        <el-icon><MagicStick /></el-icon>
        <span class="model">{{ disabled ? t('ai.notConfiguredShort') : info.model }}</span>
      </span>
    </el-tooltip>

    <el-button :disabled="disabled" :icon="MagicStick" @click="emit('generate')">
      {{ t('ai.generate') }}
    </el-button>
    <el-button :disabled="disabled" :icon="EditPen" @click="emit('continue')">
      {{ t('ai.continueWriting') }}
    </el-button>
    <el-button :disabled="disabled" :icon="Edit" @click="emit('rewrite')">
      {{ t('ai.rewrite') }}
    </el-button>
    <el-button :disabled="disabled" :icon="Document" @click="emit('summarize')">
      {{ t('ai.summarize') }}
    </el-button>
  </div>
</template>

<style scoped>
.ai-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  flex-wrap: wrap;
}
.badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 14px;
  background: #ecf5ff;
  color: #4080ff;
  font-size: 12px;
  font-weight: 500;
  margin-right: 4px;
}
.badge.off {
  background: #f7f8fa;
  color: #c9cdd4;
}
.badge .model {
  font-variant-numeric: tabular-nums;
  font-family: ui-monospace, monospace;
  font-size: 11px;
}
</style>
