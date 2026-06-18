import { createApp } from 'vue'
import { createPinia } from 'pinia'
import 'element-plus/dist/index.css'
import './styles/global.css'
import './styles/themes.css'

import App from './App.vue'
import router from './router'
import i18n from './i18n'
import { useThemeStore } from './stores/theme'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(router)
app.use(i18n)

// 在挂载前把已保存的皮肤应用到 <html>,避免首屏先用默认皮肤再"闪"成高对比度
useThemeStore(pinia).init()

app.mount('#app')
