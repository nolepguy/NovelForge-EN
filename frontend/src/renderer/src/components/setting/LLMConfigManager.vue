<template>
  <div class="llm-config-manager">
    <div class="header">
      <h4>{{ t('settings.llmConfigManagement') }}</h4>
      <el-button type="primary" size="small" @click="openEditDialog()">{{
        t('settings.addConfig')
      }}</el-button>
    </div>

    <el-table :data="llmConfigs" style="width: 100%" size="small">
      <el-table-column prop="display_name" :label="t('settings.displayName')" width="150" />
      <el-table-column prop="provider" :label="t('settings.provider')" width="130" />
      <el-table-column prop="model_name" :label="t('settings.modelName')" width="200" />
      <el-table-column label="API Base" width="240">
        <template #default="{ row }">
          <span v-if="row.provider === 'openai_compatible'">{{ row.api_base }}</span>
          <span v-else style="color: #909399; font-style: italic">{{
            t('settings.defaultWithProvider', { provider: row.provider })
          }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="token_limit" :label="t('settings.tokenLimit')" width="110" />
      <el-table-column prop="call_limit" :label="t('settings.callLimit')" width="110" />
      <el-table-column :label="t('settings.capabilityTags')" min-width="180">
        <template #default="{ row }">
          <el-popover v-if="capabilityTags(row).length" placement="top" width="320" trigger="hover">
            <template #reference>
              <div class="capability-cell">
                <el-tag
                  v-for="tag in capabilityTags(row).slice(0, 2)"
                  :key="tag"
                  size="small"
                  :type="capabilityTagType(tag)"
                >
                  {{ tag }}
                </el-tag>
                <span v-if="capabilityTags(row).length > 2" class="more-tags"
                  >+{{ capabilityTags(row).length - 2 }}</span
                >
              </div>
            </template>
            <div class="capability-popover">
              <div class="capability-summary">{{ capabilitySummary(row) }}</div>
              <div class="capability-popover-tags">
                <el-tag
                  v-for="tag in capabilityTags(row)"
                  :key="tag"
                  size="small"
                  :type="capabilityTagType(tag)"
                >
                  {{ tag }}
                </el-tag>
              </div>
            </div>
          </el-popover>
          <el-button v-else size="small" text type="primary" @click="openEditDialog(row)">{{
            t('settings.capabilityTest')
          }}</el-button>
        </template>
      </el-table-column>
      <el-table-column width="240">
        <template #header>
          <span>
            {{ t('settings.usedHeader') }}
            <el-tooltip placement="top" effect="dark">
              <template #content>
                {{ t('settings.tokenEstimationTitle') }}<br />
                {{ t('settings.tokenRuleChinese') }}<br />
                {{ t('settings.tokenRuleEnglish') }}<br />
                {{ t('settings.tokenRuleNumber') }}<br />
                {{ t('settings.tokenRuleSymbol') }}<br />
                {{ t('settings.tokenEstimationNote') }}<br />
                <br />
                {{ t('settings.displayFormat') }}<br />
                {{ t('settings.displayFormat10k') }}<br />
                {{ t('settings.displayFormat1m') }}<br />
                {{ t('settings.displayFormatPrecision') }}
              </template>
              <el-icon style="margin-left: 4px; cursor: help"><QuestionFilled /></el-icon>
            </el-tooltip>
          </span>
        </template>
        <template #default="{ row }">
          {{ formatNumber((row as any).used_tokens_input || 0) }} /
          {{ formatNumber((row as any).used_tokens_output || 0) }} /
          {{ formatNumber((row as any).used_calls || 0) }}
        </template>
      </el-table-column>
      <el-table-column :label="t('common.action')" width="300">
        <template #default="{ row }">
          <el-button size="small" @click="openEditDialog(row)">{{ t('common.edit') }}</el-button>
          <el-button size="small" type="primary" plain @click="handleCopy(row)">{{
            t('common.copy')
          }}</el-button>
          <el-button size="small" type="danger" @click="deleteConfig(row.id)">{{
            t('common.delete')
          }}</el-button>
          <el-button size="small" type="warning" plain @click="handleReset(row)">{{
            t('common.reset')
          }}</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Edit dialog -->
    <el-dialog
      v-model="editDialogVisible"
      :title="editConfig ? t('settings.editLLMConfig') : t('settings.newLLMConfig')"
      width="560px"
    >
      <LLMConfigForm
        v-if="editDialogVisible"
        :initial-data="editConfig"
        @save="handleSave"
        @refresh="loadLLMConfigs"
        @cancel="editDialogVisible = false"
      />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { QuestionFilled } from '@element-plus/icons-vue'
import LLMConfigForm from './LLMConfigForm.vue'
import type { components } from '@renderer/types/generated'
import {
  listLLMConfigs,
  createLLMConfig,
  updateLLMConfig,
  deleteLLMConfig,
  resetLLMUsage,
  copyLLMConfig
} from '@renderer/api/setting'

const { t } = useI18n()

type LLMConfig = components['schemas']['LLMConfigRead']

const llmConfigs = ref<LLMConfig[]>([])
const editDialogVisible = ref(false)
const editConfig = ref<LLMConfig | null>(null)

/**
 * Format number display
 * @param num number
 * @returns formatted string
 */
function formatNumber(num: number): string {
  if (num >= 1000000) {
    // >= 1 million, display as X.XXX million
    const millions = num / 1000000
    const formatted = millions.toFixed(3)
    // Trim trailing zeros
    const trimmed = parseFloat(formatted).toString()
    return `${trimmed} ${t('settings.unitMillion')}`
  } else if (num >= 10000) {
    // >= 10000, display as X.XXX ten-thousand
    const tenThousands = num / 10000
    const formatted = tenThousands.toFixed(3)
    // Trim trailing zeros
    const trimmed = parseFloat(formatted).toString()
    return `${trimmed} ${t('settings.unitTenThousand')}`
  } else {
    // < 10000, display the original number directly
    return num.toString()
  }
}

function capabilityTags(row: LLMConfig): string[] {
  const tags = (row as any).capability_summary?.tags
  return Array.isArray(tags) ? tags.filter((item) => typeof item === 'string') : []
}

function capabilitySummary(row: LLMConfig): string {
  return (row as any).capability_summary?.summary || t('settings.noCapabilitySummary')
}

function capabilityTagType(tag: string) {
  if (tag.includes('Failed') || tag.includes('Blocked') || tag.includes('Unavailable')) return 'danger'
  if (tag.includes('Suggestion') || tag.includes('Fix') || tag.includes('Standard Only')) return 'warning'
  return 'success'
}

async function loadLLMConfigs() {
  try {
    llmConfigs.value = await listLLMConfigs()
  } catch (error) {
    console.error('Failed to load LLM configs:', error)
    ElMessage.error(t('settings.loadLLMConfigFailed'))
  }
}

function openEditDialog(config?: LLMConfig) {
  if (config) {
    // Edit existing config
    editConfig.value = config
  } else {
    // Add new config
    editConfig.value = null
  }
  editDialogVisible.value = true
}

async function handleSave(data: any) {
  try {
    if (data.id) {
      await updateLLMConfig(data.id, data)
      ElMessage.success(t('settings.llmConfigUpdateSuccess'))
    } else {
      await createLLMConfig(data)
      ElMessage.success(t('settings.llmConfigCreateSuccess'))
    }
    editDialogVisible.value = false
    await loadLLMConfigs() // Reload the list
  } catch (error) {
    ElMessage.error(t('settings.saveFailedCheckInput'))
  }
}

async function deleteConfig(id: number) {
  try {
    await ElMessageBox.confirm(t('settings.confirmDeleteLLMConfig'), t('common.confirmDelete'), {
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
      type: 'warning'
    })
    await deleteLLMConfig(id)
    ElMessage.success(t('common.deleteSuccess'))
    await loadLLMConfigs() // Reload the list
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(t('settings.deleteFailed'))
    }
  }
}

async function handleReset(row: LLMConfig) {
  try {
    await ElMessageBox.confirm(t('settings.confirmResetStats'), t('settings.resetStats'), {
      type: 'warning',
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel')
    })
  } catch (e) {
    return
  }
  try {
    await resetLLMUsage(row.id)
    ElMessage.success(t('settings.resetDone'))
    await loadLLMConfigs()
  } catch (e) {
    ElMessage.error(t('settings.resetFailed'))
  }
}

async function handleCopy(row: LLMConfig) {
  try {
    await copyLLMConfig(row.id)
    ElMessage.success(t('settings.configCopySuccess'))
    await loadLLMConfigs()
  } catch (error) {
    console.error('Failed to copy config:', error)
    ElMessage.error(t('settings.copyConfigFailed'))
  }
}

// Expose refresh for parent component to call
defineExpose({ refresh: loadLLMConfigs })
onMounted(loadLLMConfigs)
</script>

<style scoped>
:deep(.el-button) {
  white-space: nowrap;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.header :deep(.el-button) {
  white-space: nowrap;
}

.capability-cell {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}

.more-tags {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.capability-popover {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.capability-summary {
  overflow-wrap: anywhere;
  color: var(--el-text-color-regular);
}

.capability-popover-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

:deep(.el-table .el-button) {
  white-space: nowrap;
}
</style>
