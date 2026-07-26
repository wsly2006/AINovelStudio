<script setup>
import { onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { MagicStick, Edit, EditPen, Document, Connection, StarFilled, View, Tickets, ChatLineRound, VideoPlay, Aim, Promotion, Notebook } from '@element-plus/icons-vue'
import { useAIInfoStore } from '../stores/aiInfo'

const props = defineProps({
  indexing: { type: Boolean, default: false },
})
const emit = defineEmits(['generate', 'continue', 'rewrite', 'summarize', 'index', 'score', 'styleCheck', 'beats', 'assistant', 'autoWrite', 'outlineAlign', 'translate', 'batchOutline'])

const { t } = useI18n()
const info = useAIInfoStore()

onMounted(() => {
  if (!info.loaded) info.refresh()
})

const disabled = computed(() => !info.configured)
</script>

<template>
  <div class="ai-toolbar">
    <el-tooltip :content="t('ai.generateTip')" placement="top" :show-after="300">
      <el-button :disabled="disabled" :icon="MagicStick" @click="emit('generate')">
        {{ t('ai.generate') }}
      </el-button>
    </el-tooltip>
    <el-tooltip :content="t('ai.styleCheckTip')" placement="top" :show-after="300">
      <el-button :disabled="disabled" :icon="View" @click="emit('styleCheck')">
        {{ t('ai.styleCheck') }}
      </el-button>
    </el-tooltip>
    <el-tooltip :content="t('ai.scoreTip')" placement="top" :show-after="300">
      <el-button :disabled="disabled" :icon="StarFilled" @click="emit('score')">
        {{ t('ai.score') }}
      </el-button>
    </el-tooltip>
    <el-tooltip :content="t('ai.batchOutlineTip')" placement="top" :show-after="300">
      <el-button :disabled="disabled" :icon="Notebook" @click="emit('batchOutline')">
        {{ t('ai.batchOutline') }}
      </el-button>
    </el-tooltip>
    <el-tooltip :content="t('ai.beatsTip')" placement="top" :show-after="300">
      <el-button :icon="Tickets" @click="emit('beats')">
        {{ t('ai.beats') }}
      </el-button>
    </el-tooltip>
    <el-tooltip :content="t('ai.autoWriteTip')" placement="top" :show-after="300">
      <el-button :disabled="disabled" :icon="VideoPlay" @click="emit('autoWrite')">
        {{ t('ai.autoWrite') }}
      </el-button>
    </el-tooltip>
    <el-tooltip :content="t('ai.continueWritingTip')" placement="top" :show-after="300">
      <el-button :disabled="disabled" :icon="EditPen" @click="emit('continue')">
        {{ t('ai.continueWriting') }}
      </el-button>
    </el-tooltip>
    <el-tooltip :content="t('ai.rewriteTip')" placement="top" :show-after="300">
      <el-button :disabled="disabled" :icon="Edit" @click="emit('rewrite')">
        {{ t('ai.rewrite') }}
      </el-button>
    </el-tooltip>
    <el-tooltip :content="t('ai.summarizeTip')" placement="top" :show-after="300">
      <el-button :disabled="disabled" :icon="Document" @click="emit('summarize')">
        {{ t('ai.summarize') }}
      </el-button>
    </el-tooltip>
    <el-tooltip :content="t('ai.indexChapterTip')" placement="top" :show-after="300">
      <el-button
        :disabled="disabled"
        :loading="indexing"
        :icon="Connection"
        @click="emit('index')"
      >
        {{ t('ai.indexChapter') }}
      </el-button>
    </el-tooltip>
    <el-tooltip :content="t('ai.outlineAlignTip')" placement="top" :show-after="300">
      <el-button :disabled="disabled" :icon="Aim" @click="emit('outlineAlign')">
        {{ t('outlineAlign.button') }}
      </el-button>
    </el-tooltip>
    <el-tooltip :content="t('ai.translateTip')" placement="top" :show-after="300">
      <el-button :disabled="disabled" :icon="Promotion" @click="emit('translate')">
        {{ t('translate.button') }}
      </el-button>
    </el-tooltip>
    <el-tooltip :content="t('ai.assistantTip')" placement="top" :show-after="300">
      <el-button :disabled="disabled" :icon="ChatLineRound" @click="emit('assistant')">
        {{ t('ai.assistant') }}
      </el-button>
    </el-tooltip>
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
