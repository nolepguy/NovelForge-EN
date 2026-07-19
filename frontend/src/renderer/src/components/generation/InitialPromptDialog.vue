<template>
  <el-dialog
    v-model="dialogVisible"
    :title="t('generation.startGenerateCardTitle')"
    width="500px"
    :close-on-click-modal="false"
  >
    <div class="dialog-content">
      <p class="hint-text">
        {{ t('generation.hintText') }}
      </p>
      <p class="hint-subtext">
        {{ t('generation.hintSubtext') }}
      </p>

      <el-checkbox v-model="useExistingContent" class="content-option">
        {{ t('generation.useExistingContent') }}
      </el-checkbox>

      <el-input
        v-model="userPrompt"
        type="textarea"
        :rows="4"
        :placeholder="t('generation.placeholderExample')"
        
        @keyup.ctrl.enter="handleStartGenerate"
      />

      <div class="example-hints">
        <span class="example-label">{{ t('generation.exampleLabel') }}</span>
        <el-tag
          v-for="example in examples"
          :key="example"
          size="small"
          class="example-tag"
          @click="userPrompt = example"
        >
          {{ example }}
        </el-tag>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleCancel">
          {{ t('common.cancel') }}
        </el-button>
        <el-button @click="handleSkip">
          {{ t('generation.skipAndGenerate') }}
        </el-button>
        <el-button type="primary" :disabled="!userPrompt.trim()" @click="handleStartGenerate">
          {{ t('generation.startGenerate') }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

// ==================== Props & Emits ====================

const props = defineProps<{
  visible: boolean
  cardTypeName?: string
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  confirm: [userPrompt: string, useExistingContent: boolean]
  cancel: []
}>()

// ==================== State management ====================

const { t } = useI18n()

const dialogVisible = ref(false)
const userPrompt = ref('')
const useExistingContent = ref(false)

// Example prompts (adjusted dynamically by card type)
const examples = ref<string[]>([
  t('generation.exampleCharacter1'),
  t('generation.exampleCharacter2'),
  t('generation.exampleCharacter3')
])

// ==================== Methods ====================

/**
 * Handle start generate
 */
function handleStartGenerate() {
  emit('confirm', userPrompt.value.trim(), useExistingContent.value)
  dialogVisible.value = false
  userPrompt.value = ''
  useExistingContent.value = false
}

/**
 * Handle skip
 */
function handleSkip() {
  emit('confirm', '', useExistingContent.value)
  dialogVisible.value = false
  userPrompt.value = ''
  useExistingContent.value = false
}

/**
 * Handle cancel
 */
function handleCancel() {
  emit('cancel')
  dialogVisible.value = false
  userPrompt.value = ''
}

// ==================== Watchers ====================

watch(
  () => props.visible,
  (val) => {
    dialogVisible.value = val
  }
)

watch(dialogVisible, (val) => {
  emit('update:visible', val)
})

// Adjust examples by card type
watch(
  () => props.cardTypeName,
  (typeName) => {
    if (!typeName) return

    // Different examples can be provided for different card types
    if (typeName.includes('Character')) {
      examples.value = [
        t('generation.exampleCharacter1'),
        t('generation.exampleCharacter2'),
        t('generation.exampleCharacter3')
      ]
    } else if (typeName.includes('Chapter')) {
      examples.value = [
        t('generation.exampleChapter1'),
        t('generation.exampleChapter2'),
        t('generation.exampleChapter3')
      ]
    } else if (typeName.includes('Outline')) {
      examples.value = [
        t('generation.exampleOutline1'),
        t('generation.exampleOutline2'),
        t('generation.exampleOutline3')
      ]
    } else {
      examples.value = [
        t('generation.exampleDefault1'),
        t('generation.exampleDefault2'),
        t('generation.exampleDefault3')
      ]
    }
  }
)
</script>

<style scoped>
.dialog-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.hint-text {
  margin: 0;
  font-size: 14px;
  color: var(--el-text-color-primary);
}

.hint-subtext {
  margin: -8px 0 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.example-hints {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.example-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.example-tag {
  cursor: pointer;
  transition: all 0.2s;
}

.example-tag:hover {
  transform: translateY(-2px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
/* i18n: english-length css fixes */

.dialog-footer .el-button {
  white-space: nowrap;
}
.example-tag {
  white-space: nowrap;
}
</style>
