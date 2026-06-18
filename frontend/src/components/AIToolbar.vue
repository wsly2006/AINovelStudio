<script setup>
import { onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { MagicStick, Edit, EditPen, Document, Connection } from '@element-plus/icons-vue'
import { useAIInfoStore } from '../stores/aiInfo'

const props = defineProps({
  indexing: { type: Boolean, default: false },
})
const emit = defineEmits(['generate', 'continue', 'rewrite', 'summarize', 'index'])

const { t } = useI18n()
const info = useAIInfoStore()

onMounted(() => {
  if (!info.loaded) info.refresh()
})

const disabled = computed(() => !info.configured)
</script>

<template>
  <div class="ai-toolbar">
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
    <el-button
      :disabled="disabled"
      :loading="indexing"
      :icon="Connection"
      @click="emit('index')"
    >
      {{ t('ai.indexChapter') }}
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
</style>
