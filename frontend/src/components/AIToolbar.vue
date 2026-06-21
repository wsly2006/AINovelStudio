<script setup>
import { onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { MagicStick, Edit, EditPen, Document, Connection, StarFilled, View, Tickets, ChatLineRound, VideoPlay, Aim } from '@element-plus/icons-vue'
import { useAIInfoStore } from '../stores/aiInfo'

const props = defineProps({
  indexing: { type: Boolean, default: false },
})
const emit = defineEmits(['generate', 'continue', 'rewrite', 'summarize', 'index', 'score', 'styleCheck', 'beats', 'assistant', 'autoWrite', 'outlineAlign'])

const { t } = useI18n()
const info = useAIInfoStore()

onMounted(() => {
  if (!info.loaded) info.refresh()
})

const disabled = computed(() => !info.configured)
</script>

<template>
  <div class="ai-toolbar">
    <el-tooltip content="列 3-5 个本章节拍(开头/转折/结尾),AI 生成时按拍推进,写后还会逐拍对账" placement="top" :show-after="300">
      <el-button :icon="Tickets" @click="emit('beats')">
        节拍
      </el-button>
    </el-tooltip>
    <el-tooltip content="整章 AI 生成,自动注入总纲/主线/节拍/人物/世界观" placement="top" :show-after="300">
      <el-button :disabled="disabled" :icon="MagicStick" @click="emit('generate')">
        {{ t('ai.generate') }}
      </el-button>
    </el-tooltip>
    <el-tooltip content="选起点 + 章数,后台连续生成,每章自动索引/对账/评分,质量不达标按模式重试或停下" placement="top" :show-after="300">
      <el-button :disabled="disabled" :icon="VideoPlay" @click="emit('autoWrite')">
        自动连写
      </el-button>
    </el-tooltip>
    <el-tooltip content="挑出读起来「像 AI 写」的段落,给出改写方向,可一键定位编辑器" placement="top" :show-after="300">
      <el-button :disabled="disabled" :icon="View" @click="emit('styleCheck')">
        AI 文风检查
      </el-button>
    </el-tooltip>
    <el-tooltip content="从光标处往下续写,自动带上前文上下文" placement="top" :show-after="300">
      <el-button :disabled="disabled" :icon="EditPen" @click="emit('continue')">
        {{ t('ai.continueWriting') }}
      </el-button>
    </el-tooltip>
    <el-tooltip content="改写当前选中的段落(先在编辑器里选中文字)" placement="top" :show-after="300">
      <el-button :disabled="disabled" :icon="Edit" @click="emit('rewrite')">
        {{ t('ai.rewrite') }}
      </el-button>
    </el-tooltip>
    <el-tooltip content="让 AI 为本章生成简短概述,写回章节摘要" placement="top" :show-after="300">
      <el-button :disabled="disabled" :icon="Document" @click="emit('summarize')">
        {{ t('ai.summarize') }}
      </el-button>
    </el-tooltip>
    <el-tooltip content="从本章正文抽取人物 / 世界观 / 物品 / 关系 / 情节,落到知识库" placement="top" :show-after="300">
      <el-button
        :disabled="disabled"
        :loading="indexing"
        :icon="Connection"
        @click="emit('index')"
      >
        {{ t('ai.indexChapter') }}
      </el-button>
    </el-tooltip>
    <el-tooltip content="文笔 / 情节 / 人物 / 综合 4 维 AI 评分,留历史曲线" placement="top" :show-after="300">
      <el-button :disabled="disabled" :icon="StarFilled" @click="emit('score')">
        评分
      </el-button>
    </el-tooltip>
    <el-tooltip content="把章节正文与大纲(梗概 + 节拍)对账,逐项 covered / partial / missing" placement="top" :show-after="300">
      <el-button :disabled="disabled" :icon="Aim" @click="emit('outlineAlign')">
        {{ t('outlineAlign.button') }}
      </el-button>
    </el-tooltip>
    <el-tooltip content="打开 AI 助手对话:基于当前工程 / 章节 / 选区多轮交流,可一键插入到编辑器" placement="top" :show-after="300">
      <el-button :disabled="disabled" :icon="ChatLineRound" @click="emit('assistant')">
        AI 助手
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
