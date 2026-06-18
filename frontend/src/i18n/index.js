// vue-i18n 实例
// 当前仅启用 zh-CN,新增语种步骤:
// 1. 在 locales/ 下复制 zh-CN.js,改键名(如 en-US.js)
// 2. import 进来加到 messages
// 3. (可选)从 localStorage 或 navigator.language 决定 locale
import { createI18n } from 'vue-i18n'
import zhCN from './locales/zh-CN'

export const SUPPORTED_LOCALES = ['zh-CN']
export const DEFAULT_LOCALE = 'zh-CN'

const i18n = createI18n({
  legacy: false,
  locale: DEFAULT_LOCALE,
  fallbackLocale: DEFAULT_LOCALE,
  messages: {
    'zh-CN': zhCN,
  },
})

export default i18n
