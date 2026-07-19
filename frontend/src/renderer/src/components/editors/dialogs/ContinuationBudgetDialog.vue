<template>
  <el-dialog
    :model-value="visible"
    :title="t('misc.continuationConfig')"
    width="560px"
    @close="handleCancel"
  >
    <div class="dialog-body">
      <el-form label-position="top" size="small">
        <el-form-item :label="t('misc.continuationGuidance')">
          <el-input
            v-model="localGuidance"
            type="textarea"
            :rows="4"
            :placeholder="t('misc.continuationGuidancePlaceholder')"
          />
        </el-form-item>
        <el-form-item :label="t('misc.targetWordCount')">
          <el-input-number
            v-model="localTargetWordCount"
            :min="200"
            :max="200000"
            :step="100"
            :controls-position="'right'"
          />
          <span class="helper-text">{{ t('misc.targetWordCountHelper') }}</span>
        </el-form-item>
        <el-form-item :label="t('misc.wordControlMode')">
          <el-radio-group v-model="localWordControlMode">
            <el-radio-button label="prompt_only">{{ t('misc.promptOnly') }}</el-radio-button>
            <el-radio-button label="balanced">{{ t('misc.balancedMode') }}</el-radio-button>
          </el-radio-group>
          <div class="mode-help">
            <p v-if="localWordControlMode === 'prompt_only'">{{ t('misc.promptOnlyHelp') }}</p>
            <p v-else>{{ t('misc.balancedHelp') }}</p>
            <p v-if="localWordControlMode === 'balanced'">{{ t('misc.balancedTokenNote') }}</p>
          </div>
        </el-form-item>
      </el-form>
    </div>
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleCancel">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="handleConfirm">{{ t('misc.startContinuation') }}</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

export type ContinuationWordControlMode = 'prompt_only' | 'balanced'
const { t } = useI18n()

const props = defineProps<{
  visible: boolean
  targetWordCount: number
  wordControlMode: ContinuationWordControlMode
  guidance: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (
    e: 'confirm',
    payload: {
      targetWordCount: number
      wordControlMode: ContinuationWordControlMode
      guidance: string
    }
  ): void
}>()

const localTargetWordCount = ref<number>(3000)
const localWordControlMode = ref<ContinuationWordControlMode>('balanced')
const localGuidance = ref<string>('')

watch(
  () => props.visible,
  (visible) => {
    if (!visible) return
    localTargetWordCount.value = props.targetWordCount || 3000
    localWordControlMode.value = props.wordControlMode || 'balanced'
    localGuidance.value = props.guidance || ''
  },
  { immediate: true }
)

function handleCancel() {
  emit('update:visible', false)
}

function handleConfirm() {
  emit('confirm', {
    targetWordCount: Math.max(200, Math.floor(localTargetWordCount.value || 3000)),
    wordControlMode: localWordControlMode.value,
    guidance: localGuidance.value.trim(),
  })
  emit('update:visible', false)
}
</script>

<style scoped>
.dialog-body {
  padding: 4px 0;
}

.helper-text {
  margin-left: 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.mode-help {
  margin-top: 10px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
}

.mode-help p {
  margin: 0;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.dialog-footer :deep(.el-button) { white-space: nowrap; }
</style>
