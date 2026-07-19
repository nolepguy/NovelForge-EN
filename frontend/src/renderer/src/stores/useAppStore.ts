import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import i18n, { getStoredLocale, storeLocale, type AppLocale } from '@renderer/i18n'

export const useAppStore = defineStore('app', () => {
  // Current view
  const currentView = ref<'dashboard' | 'editor' | 'ideas' | 'workflows' | 'code-workflows' | 'triggers'>('dashboard')

  // Theme state
  const isDarkMode = ref(false)

  // Settings dialog state
  const settingsDialogVisible = ref(false)
  const settingsInitialTab = ref<string>('llm')

  // Global loading state
  const globalLoading = ref(false)

  // Global error state
  const globalError = ref<string | null>(null)

  // Locale state
  const locale = ref<AppLocale>(getStoredLocale())

  // Computed
  const isDashboard = computed(() => currentView.value === 'dashboard')
  const isEditor = computed(() => currentView.value === 'editor')
  const isWorkflows = computed(() => currentView.value === 'workflows')

  // Actions
  function setCurrentView(view: 'dashboard' | 'editor' | 'ideas' | 'workflows' | 'code-workflows' | 'triggers') {
    currentView.value = view
  }

  function goToDashboard() {
    currentView.value = 'dashboard'
  }

  function goToEditor() {
    currentView.value = 'editor'
  }

  function goToIdeas() {
    currentView.value = 'ideas'
  }

  function goToWorkflows() {
    currentView.value = 'workflows'
  }

  function goToCodeWorkflows() {
    currentView.value = 'code-workflows'
  }

  function goToTriggers() {
    currentView.value = 'triggers'
  }

  function toggleTheme() {
    isDarkMode.value = !isDarkMode.value
    localStorage.setItem('theme', isDarkMode.value ? 'dark' : 'light')
    applyTheme()
  }

  function setTheme(dark: boolean) {
    isDarkMode.value = dark
    localStorage.setItem('theme', dark ? 'dark' : 'light')
    applyTheme()
  }

  function applyTheme() {
    const html = document.documentElement
    if (isDarkMode.value) {
      html.classList.add('dark')
    } else {
      html.classList.remove('dark')
    }
  }

  function initTheme() {
    const savedTheme = localStorage.getItem('theme')
    isDarkMode.value = savedTheme === 'dark'
    applyTheme()
  }

  function openSettings(tab?: string) {
    if (tab) settingsInitialTab.value = tab
    settingsDialogVisible.value = true
  }

  function closeSettings() {
    settingsDialogVisible.value = false
  }

  function setGlobalLoading(loading: boolean) {
    globalLoading.value = loading
  }

  function setGlobalError(error: string | null) {
    globalError.value = error
  }

  function clearGlobalError() {
    globalError.value = null
  }

  function reset() {
    currentView.value = 'dashboard'
    settingsDialogVisible.value = false
    globalLoading.value = false
    globalError.value = null
  }

  function setLocale(next: AppLocale) {
    locale.value = next
    storeLocale(next)
    ;(i18n.global.locale as unknown as { value: string }).value = next
    document.documentElement.lang = next === 'zh-CN' ? 'zh-CN' : 'en'
  }

  function initLocale() {
    setLocale(locale.value)
  }

  return {
    // State
    currentView,
    isDarkMode,
    settingsDialogVisible,
    settingsInitialTab,
    globalLoading,
    globalError,

    // Computed
    isDashboard,
    isEditor,
    isWorkflows,

    // Actions
    setCurrentView,
    goToDashboard,
    goToEditor,
    goToIdeas,
    goToWorkflows,
    goToCodeWorkflows,
    goToTriggers,
    toggleTheme,
    setTheme,
    applyTheme,
    initTheme,
    openSettings,
    closeSettings,
    setGlobalLoading,
    setGlobalError,
    clearGlobalError,
    reset,
    locale,
    setLocale,
    initLocale
  }
}) 
