<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import LLMConfigManager from '../setting/LLMConfigManager.vue'
import Versions from '../Versions.vue'
import PromptWorkshop from '../setting/PromptWorkshop.vue'
import CardTypeManager from '../setting/CardTypeManager.vue'
import KnowledgeManager from '../setting/KnowledgeManager.vue'
import AssistantSettings from '../setting/AssistantSettings.vue'
import { useUpdateStore } from '@renderer/stores/useUpdateStore'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; close: [] }>()

const { t } = useI18n()
const { locale } = useI18n()

const activeTab = ref('llm')
// Read the initial tab preset by the global store
import { useAppStore } from '@renderer/stores/useAppStore'
const appStore = useAppStore()
const updateStore = useUpdateStore()
activeTab.value = appStore.settingsInitialTab || 'llm'

function handleLocaleChange(val: string) {
  appStore.setLocale(val as 'en' | 'zh-CN')
  locale.value = val as 'en' | 'zh-CN'
}

function handleClose() {
  emit('update:modelValue', false)
  emit('close')
}

// When switching to the LLM tab or first showing, let the child component refresh
import { onMounted, watch, nextTick } from 'vue'
const llmManagerRef = ref()
function emitRefreshIfLLM() {
  if (activeTab.value === 'llm' && llmManagerRef.value?.refresh) {
    llmManagerRef.value.refresh()
  }
}
onMounted(() => emitRefreshIfLLM())
watch(
  () => activeTab.value,
  () => emitRefreshIfLLM()
)
// Refresh once each time the dialog opens (wait for child component to finish rendering)
watch(
  () => props.modelValue,
  async (open) => {
    if (open) {
      await nextTick()
      emitRefreshIfLLM()
    }
  }
)
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="t('settings.appSettings')"
    width="85%"
    top="4vh"
    @update:model-value="(val) => emit('update:modelValue', val)"
    @close="handleClose"
  >
    <div class="settings-container">
      <el-tabs v-model="activeTab" tab-position="left" class="settings-tabs">
        <el-tab-pane :label="t('settings.tabLLM')" name="llm">
          <LLMConfigManager ref="llmManagerRef" />
        </el-tab-pane>
        <el-tab-pane :label="t('settings.tabKnowledge')" name="knowledge">
          <KnowledgeManager />
        </el-tab-pane>
        <el-tab-pane :label="t('settings.tabPromptWorkshop')" name="prompts">
          <PromptWorkshop />
        </el-tab-pane>
        <el-tab-pane :label="t('settings.tabCardTypes')" name="card-types">
          <CardTypeManager />
        </el-tab-pane>
        <el-tab-pane :label="t('settings.tabAssistant')" name="assistant">
          <AssistantSettings />
        </el-tab-pane>
        <el-tab-pane name="about">
          <template #label>
            <el-badge :is-dot="updateStore.hasUpdate" type="warning">
              <span>{{ t('common.about') }}</span>
            </el-badge>
          </template>
          <div class="about-section">
            <div class="language-switcher">
              <span class="language-label">{{ t('settings.language') }}</span>
              <el-select :model-value="appStore.locale" @change="handleLocaleChange" size="small" style="width: 160px;">
                <el-option label="English" value="en" />
                <el-option label="简体中文" value="zh-CN" />
              </el-select>
            </div>
            <Versions />
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>
  </el-dialog>
</template>

<style scoped>
.settings-container {
  height: 78vh;
}
.settings-tabs {
  height: 100%;
}
:deep(.el-dialog__body) {
  padding-top: 8px;
}
:deep(.el-tabs__content) {
  height: 100%;
  overflow-y: auto;
}
:deep(.el-tabs__item) {
  white-space: nowrap;
}
.about-section {
  padding: 10px 0;
}
.language-switcher {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.language-label {
  font-weight: 500;
  white-space: nowrap;
}
</style>
