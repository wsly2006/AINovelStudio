// vue-i18n 实例
// 已启用 zh-CN + en-US,en-US 目前为占位,缺失键会 fallback 到 zh-CN。
// 后续新增语种:在 locales/ 复制 zh-CN.js 改键名,import 进来加到 messages,再加到 SUPPORTED_LOCALES。
import { createI18n } from 'vue-i18n'
import zhCN from './locales/zh-CN'
import enUS from './locales/en-US'

export const SUPPORTED_LOCALES = ['zh-CN', 'en-US']
export const DEFAULT_LOCALE = 'zh-CN'
const STORAGE_KEY = 'ai-novel-locale'

// 优先读 localStorage,其次浏览器语言,再退回默认;非法值忽略。
function resolveInitialLocale() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved && SUPPORTED_LOCALES.includes(saved)) return saved
  } catch {
    // localStorage 不可用(隐私模式等)时按默认走
  }
  const nav = (typeof navigator !== 'undefined' && navigator.language) || ''
  if (nav.toLowerCase().startsWith('en')) return 'en-US'
  return DEFAULT_LOCALE
}

const i18n = createI18n({
  legacy: false,
  locale: resolveInitialLocale(),
  fallbackLocale: DEFAULT_LOCALE,
  messages: {
    'zh-CN': zhCN,
    'en-US': enUS,
  },
})

export function setLocale(locale) {
  if (!SUPPORTED_LOCALES.includes(locale)) return
  i18n.global.locale.value = locale
  try {
    localStorage.setItem(STORAGE_KEY, locale)
  } catch {
    // 忽略写入失败:切换本次会话仍生效
  }
  if (typeof document !== 'undefined') {
    document.documentElement.lang = locale
  }
}

export default i18n
