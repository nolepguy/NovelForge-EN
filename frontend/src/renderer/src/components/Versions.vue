<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUpdateStore } from '@renderer/stores/useUpdateStore'
import { ElMessage } from 'element-plus'
import { Refresh, Download } from '@element-plus/icons-vue'

const updateStore = useUpdateStore()
const { t } = useI18n()

// Electron runtime info display was previously here; removed per requirements, only update-related content remains

// Manually check for updates
const handleManualCheck = async () => {
  try {
    const result = await updateStore.manualCheck()
    if (result.hasUpdate) {
      ElMessage.success(t('misc.newVersionFound', { version: result.latestVersion }))
    } else {
      ElMessage.info(t('misc.alreadyLatest'))
    }
  } catch (error: any) {
    ElMessage.error(error.message || t('misc.checkFailedNetwork'))
  }
}

// Toggle auto-check
const handleAutoCheckToggle = (value: boolean) => {
  updateStore.setAutoCheckEnabled(value)
  ElMessage.success(value ? t('misc.autoCheckEnabled') : t('misc.autoCheckDisabled'))
}

// Open the Release page
const openReleasePage = () => {
  if (updateStore.releaseInfo?.htmlUrl) {
    window.open(updateStore.releaseInfo.htmlUrl, '_blank')
  }
}

// Format time
const formatTime = (date: Date | null) => {
  if (!date) return t('misc.neverChecked')
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(date)
}
</script>

<template>
  <div class="about-page">
    <!-- Current version info -->
    <el-card shadow="never" class="version-card">
      <template #header>
        <div class="card-header">
          <span>{{ t('misc.currentVersion') }}</span>
        </div>
      </template>
      <div class="version-info">
        <div class="version-number">{{ updateStore.currentVersion }}</div>
        <div class="version-meta">
          <div v-if="updateStore.lastCheckTime" class="last-check">
            {{ t('misc.lastCheck', { time: formatTime(updateStore.lastCheckTime) }) }}
          </div>
        </div>
      </div>
    </el-card>

    <!-- Auto-update settings -->
    <el-card shadow="never" class="update-settings-card">
      <template #header>
        <div class="card-header">
          <span>{{ t('misc.updateSettings') }}</span>
        </div>
      </template>
      <div class="settings-row">
        <div class="setting-item">
          <span class="setting-label">{{ t('misc.autoCheckUpdate') }}</span>
          <el-switch
            :model-value="updateStore.autoCheckEnabled"
            @change="handleAutoCheckToggle"
          />
        </div>
        <div class="setting-item">
          <span class="setting-label">{{ t('misc.manualCheck') }}</span>
          <el-button
            type="primary"
            :icon="Refresh"
            :loading="updateStore.isChecking"
            @click="handleManualCheck"
          >
            {{ updateStore.isChecking ? t('misc.checking') : t('misc.checkUpdate') }}
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- Latest version info: title + Release note text + {{ t('misc.viewDetails') }} button -->
    <el-card v-if="updateStore.hasUpdate" shadow="never" class="new-version-card">
      <template #header>
        <div class="card-header">
          <span>{{ t('misc.latestRelease') }}</span>
          <el-tag type="warning" effect="dark">v{{ updateStore.latestVersion }}</el-tag>
        </div>
      </template>
      <div class="release-info">
        <div class="release-meta">
          <span class="release-name">{{ updateStore.releaseInfo?.name }}</span>
          <el-button
            type="primary"
            size="small"
            :icon="Download"
            @click="openReleasePage"
          >
            {{ t('misc.viewDetails') }}
          </el-button>
        </div>
        <div class="release-notes">
          <div class="notes-title">{{ t('misc.updateContent') }}</div>
          <div class="notes-content">{{ updateStore.releaseInfo?.body || t('misc.noUpdateNotes') }}</div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.about-page {
  padding: 20px;
  max-width: 900px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
}

.version-card .version-info {
  text-align: center;
  padding: 20px 0;
}

.version-number {
  font-size: 48px;
  font-weight: 700;
  color: var(--el-color-primary);
  margin-bottom: 12px;
}

.version-meta {
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.update-settings-card .settings-row {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.setting-item:last-child {
  border-bottom: none;
}

.setting-label {
  font-size: 14px;
  color: var(--el-text-color-regular);
}

.new-version-card {
  border: 2px solid var(--el-color-warning);
}

.release-info {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.release-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.release-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.release-notes {
  background-color: var(--el-fill-color-lighter);
  border-radius: 6px;
  padding: 16px;
}

.notes-title {
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--el-text-color-primary);
}

.notes-content {
  color: var(--el-text-color-regular);
  line-height: 1.6;
  white-space: pre-line; /* Break on newlines, collapse multiple spaces */
  max-height: 200px;
  overflow-y: auto;
  font-size: 14px;
}

.runtime-card .versions li:last-child {
  border-bottom: none;
}
</style>
