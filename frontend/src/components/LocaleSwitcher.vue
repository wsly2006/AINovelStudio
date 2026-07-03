<script setup>
import { useI18n } from 'vue-i18n'
import { setLocale, SUPPORTED_LOCALES } from '../i18n'

// 只展示语言名,不显示图标 —— 右上角空间紧张,尽量轻
const LABELS = {
  'zh-CN': '中文',
  'en-US': 'English',
}

const { locale } = useI18n()

function onCommand(next) {
  if (next === locale.value) return
  setLocale(next)
}
</script>

<template>
  <el-dropdown trigger="click" @command="onCommand">
    <button class="locale-btn" :title="LABELS[locale]" :aria-label="LABELS[locale]">
      <span>{{ LABELS[locale] || locale }}</span>
    </button>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item
          v-for="l in SUPPORTED_LOCALES"
          :key="l"
          :command="l"
          :disabled="l === locale"
        >
          {{ LABELS[l] || l }}
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<style scoped>
.locale-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 28px;
  padding: 0 10px;
  border: 1px solid var(--el-border-color, #dcdfe6);
  background: var(--el-bg-color, #fff);
  color: var(--el-text-color-regular, #606266);
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}
.locale-btn:hover {
  border-color: var(--el-color-primary, #409eff);
  color: var(--el-color-primary, #409eff);
}
</style>
