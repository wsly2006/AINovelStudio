<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import draggable from 'vuedraggable'
import { Plus } from '@element-plus/icons-vue'
import ChapterItem from './ChapterItem.vue'

const props = defineProps({
  chapters: { type: Array, required: true },
  selectedId: { type: Number, default: null },
})
const emit = defineEmits(['select', 'create', 'rename', 'delete', 'reorder', 'edit'])

const { t } = useI18n()

const list = computed({
  get: () => props.chapters,
  set: (v) => emit('reorder', v),
})

const countText = computed(() => t('workspace.chapterCount', { n: props.chapters.length }))
</script>

<template>
  <div class="chapter-list">
    <div class="header">
      <span class="title">{{ t('workspace.chapterListTitle') }} <span class="count">({{ countText }})</span></span>
      <el-button type="primary" size="small" :icon="Plus" @click="emit('create')">
        {{ t('workspace.newChapter') }}
      </el-button>
    </div>

    <div class="body">
      <div v-if="chapters.length === 0" class="empty">
        {{ t('workspace.emptyChapters') }}
      </div>

      <draggable
        v-else
        v-model="list"
        item-key="id"
        handle=".chapter-item"
        animation="150"
        ghost-class="ghost"
      >
        <template #item="{ element }">
          <ChapterItem
            :chapter="element"
            :active="element.id === selectedId"
            @select="emit('select', $event)"
            @rename="emit('rename', $event)"
            @delete="emit('delete', $event)"
            @edit="emit('edit', $event)"
          />
        </template>
      </draggable>
    </div>
  </div>
</template>

<style scoped>
.chapter-list {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
  border-right: 1px solid #e5e6eb;
}
.header {
  padding: 12px 16px;
  border-bottom: 1px solid #e5e6eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}
.header .title {
  font-size: 14px;
  font-weight: 600;
}
.header .count {
  font-weight: normal;
  color: #86909c;
  font-size: 12px;
}
.body {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.empty {
  text-align: center;
  color: #86909c;
  font-size: 13px;
  padding: 40px 16px;
}
.ghost {
  opacity: 0.4;
  background: #e8f0ff;
}
</style>
