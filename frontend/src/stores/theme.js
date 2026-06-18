import { defineStore } from 'pinia'

const STORAGE_KEY = 'ai-novel.theme'
const THEMES = ['default', 'high-contrast']

function readInitial() {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    if (v && THEMES.includes(v)) return v
  } catch {
    // 隐私模式 / 禁用 storage 时静默兜底
  }
  return 'default'
}

function applyToDom(theme) {
  // 默认皮肤不写 data-theme,留空给 :root 默认变量
  if (theme === 'default') {
    document.documentElement.removeAttribute('data-theme')
  } else {
    document.documentElement.setAttribute('data-theme', theme)
  }
}

export const useThemeStore = defineStore('theme', {
  state: () => ({
    current: readInitial(),
  }),
  actions: {
    init() {
      applyToDom(this.current)
    },
    set(theme) {
      if (!THEMES.includes(theme)) return
      this.current = theme
      applyToDom(theme)
      try {
        localStorage.setItem(STORAGE_KEY, theme)
      } catch {
        // 同上,持久化失败不影响本次切换
      }
    },
    toggle() {
      this.set(this.current === 'default' ? 'high-contrast' : 'default')
    },
  },
})
