/**
 * Update detection state management store
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ReleaseInfo, UpdateCheckResult } from '@renderer/services/updateService'
import { autoCheckForUpdates, manualCheckForUpdates, getCurrentVersion } from '@renderer/services/updateService'
import i18n from '@renderer/i18n'

export const useUpdateStore = defineStore('update', () => {
  // Current version
  const currentVersion = ref(getCurrentVersion())

  // Latest version info
  const latestVersion = ref<string | null>(null)
  const releaseInfo = ref<ReleaseInfo | null>(null)

  // Whether an update is available
  const hasUpdate = computed(() => {
    return latestVersion.value !== null && releaseInfo.value !== null
  })

  // Detection status
  const isChecking = ref(false)
  const lastCheckTime = ref<Date | null>(null)
  const lastCheckError = ref<string | null>(null)

  // Auto-check toggle (persisted to localStorage)
  const autoCheckEnabled = ref(true)

  // Read settings from localStorage on init
  const STORAGE_KEY = 'novelforge_auto_update_enabled'
  const storedSetting = localStorage.getItem(STORAGE_KEY)
  if (storedSetting !== null) {
    autoCheckEnabled.value = storedSetting === 'true'
  }

  // Watch auto-check toggle changes and sync to localStorage
  function setAutoCheckEnabled(enabled: boolean) {
    autoCheckEnabled.value = enabled
    localStorage.setItem(STORAGE_KEY, String(enabled))
  }
  
  /**
   * Perform update detection (internal method)
   */
  async function performCheck(checkFn: () => Promise<UpdateCheckResult>): Promise<UpdateCheckResult> {
    isChecking.value = true
    lastCheckError.value = null
    
    try {
      const result = await checkFn()
      
      lastCheckTime.value = new Date()
      
      if (result.hasUpdate && result.releaseInfo) {
        latestVersion.value = result.latestVersion || null
        releaseInfo.value = result.releaseInfo
      } else {
        latestVersion.value = null
        releaseInfo.value = null
      }
      
      return result
    } catch (error: any) {
      lastCheckError.value = error.message || i18n.global.t('app.update.detectionFailed')
      throw error
    } finally {
      isChecking.value = false
    }
  }
  
  /**
   * Auto-check for updates (with retry)
   */
  async function autoCheck(): Promise<UpdateCheckResult> {
    return performCheck(autoCheckForUpdates)
  }
  
  /**
   * Manually check for updates (no retry)
   */
  async function manualCheck(): Promise<UpdateCheckResult> {
    return performCheck(manualCheckForUpdates)
  }
  
  /**
   * Clear update state (can be called after the user acknowledges the update)
   */
  function clearUpdateNotification() {
    // Note: latestVersion and releaseInfo are not cleared here,
    // this is only for UI logic (e.g. closing the notification popup)
    // If a real clear is needed, implement it here
  }

  /**
   * Reset error state
   */
  function clearError() {
    lastCheckError.value = null
  }
  
  return {
    // State
    currentVersion,
    latestVersion,
    releaseInfo,
    hasUpdate,
    isChecking,
    lastCheckTime,
    lastCheckError,
    autoCheckEnabled,

    // Methods
    autoCheck,
    manualCheck,
    setAutoCheckEnabled,
    clearUpdateNotification,
    clearError
  }
})
