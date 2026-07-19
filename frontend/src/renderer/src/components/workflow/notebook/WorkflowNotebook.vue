<template>
  <div class="workflow-notebook">
    <div class="notebook-header">
      <div class="header-left">
        <span class="notebook-title">{{ t('misc.executionResult') }}</span>
        <el-tag v-if="isRunning" type="primary" size="small">{{ t('misc.statusRunning') }}</el-tag>
      </div>
      <el-button
        text
        size="small"
        @click="handleClearOutput"
        :icon="Delete"
      >
        {{ t('misc.clearOutput') }}
      </el-button>
    </div>

    <div ref="notebookContent" class="notebook-content">
      <div v-if="cells.length === 0" class="empty-state">
        <el-empty :description="t('misc.clickRunHint')" />
      </div>

      <div v-else class="cells-container">
        <notebook-cell
          v-for="cell in cells"
          :key="cell.id"
          :cell="cell"
          @output="handleCellOutput"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, nextTick } from 'vue'
import { Delete } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import NotebookCell from './NotebookCell.vue'

const props = defineProps({
  cells: {
    type: Array,
    default: () => []
  },
  isRunning: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['cell-output', 'clear-output'])
const { t } = useI18n()

const notebookContent = ref(null)

const handleCellOutput = (output) => {
  emit('cell-output', output)
}

const handleClearOutput = () => {
  emit('clear-output')
}

// Watch cells changes and auto-scroll to the bottom
watch(() => props.cells.length, () => {
  nextTick(() => {
    if (notebookContent.value) {
      notebookContent.value.scrollTop = notebookContent.value.scrollHeight
    }
  })
})
</script>

<style scoped>
.workflow-notebook {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color);
}

.notebook-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-lighter);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.notebook-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-regular);
}

.notebook-content {
  flex: 1;
  overflow-y: auto;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--el-text-color-secondary);
}

.cells-container {
  padding: 16px;
}
</style>