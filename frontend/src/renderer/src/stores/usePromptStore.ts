import { defineStore } from 'pinia'
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import i18n from '@renderer/i18n'
import { listPrompts, type Prompt } from '@renderer/api/setting'

export const usePromptStore = defineStore('prompt', () => {
  // State
  const prompts = ref<Prompt[]>([])
  const isLoading = ref(false)

  // Actions
  async function fetchPrompts() {
    isLoading.value = true
    try {
      const list = await listPrompts()
      prompts.value = list || []
    } catch (error) {
      console.error('Failed to fetch prompt list:', error)
      ElMessage.error(i18n.global.t('app.prompt.fetchPromptsFailed'))
      throw error
    } finally {
      isLoading.value = false
    }
  }

  return {
    prompts,
    isLoading,
    fetchPrompts
  }
})
