import { defineStore } from 'pinia'
import { ref } from 'vue'
import { aiApi } from '../api/ai'

/**
 * 共享的 AI 配置探活信息。
 * 任何修改了 /api/settings/ai 的地方,save 完调一下 refresh()。
 */
export const useAIInfoStore = defineStore('aiInfo', () => {
  const configured = ref(false)
  const model = ref('')
  const provider = ref('env')
  const loaded = ref(false)

  async function refresh() {
    try {
      const data = await aiApi.info()
      configured.value = !!data.configured
      model.value = data.model || ''
      provider.value = data.provider || 'env'
    } catch {
      configured.value = false
    } finally {
      loaded.value = true
    }
  }

  return { configured, model, provider, loaded, refresh }
})
