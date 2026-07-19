import { defineStore } from 'pinia'
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import i18n from '@renderer/i18n'
import { listLLMConfigs, type LLMConfigRead } from '@renderer/api/setting'

export const useLLMConfigStore = defineStore('llmConfig', () => {
  // State
  const llmConfigs = ref<LLMConfigRead[]>([])
  const isLoading = ref(false)

  // Actions
  async function fetchLLMConfigs() {
    isLoading.value = true
    try {
      const list = await listLLMConfigs()
      llmConfigs.value = list || []
    } catch (error) {
      console.error('Failed to fetch LLM config list:', error)
      ElMessage.error(i18n.global.t('app.llm.fetchConfigsFailed'))
      throw error
    } finally {
      isLoading.value = false
    }
  }

  return {
    llmConfigs,
    isLoading,
    fetchLLMConfigs
  }
})
