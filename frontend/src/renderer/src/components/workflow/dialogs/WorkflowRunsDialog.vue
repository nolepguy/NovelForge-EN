<template>
  <el-dialog
    v-model="visible"
    :title="t('workflow.runRecords')"
    width="90%"
    :close-on-click-modal="false"
  >
    <div class="runs-dialog-content">
      <!-- Filter -->
      <div class="filters">
        <el-select v-model="statusFilter" :placeholder="t('workflow.statusFilter')" clearable @change="loadRuns" style="width: 150px">
          <el-option :label="t('common.all')" value="" />
          <el-option :label="t('workflow.statusRunning')" value="running" />
          <el-option :label="t('workflow.statusPaused')" value="paused" />
          <el-option :label="t('workflow.statusCompleted')" value="succeeded" />
          <el-option :label="t('workflow.statusFailed')" value="failed" />
        </el-select>
        <el-button @click="loadRuns" :icon="Refresh">{{ t('common.refresh') }}</el-button>
      </div>

      <!-- Run list -->
      <el-table :data="runs" v-loading="loading" stripe style="margin-top: 10px">
        <el-table-column prop="id" label="ID" width="60" />
        
        <el-table-column :label="t('workflow.workflow')" width="220">
          <template #default="{ row }">
            {{ row.workflow?.name || t('workflow.workflowLabel', { id: row.workflow_id }) }}
          </template>
        </el-table-column>

        <el-table-column :label="t('common.status')" width="110">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column :label="t('workflow.progress')" width="160">
          <template #default="{ row }">
            <el-progress 
              v-if="row.status === 'running' || row.status === 'paused'"
              :percentage="getProgress(row.id)" 
              :status="row.status === 'paused' ? 'warning' : undefined"
              :stroke-width="8"
            />
            <el-progress 
              v-else-if="row.status === 'succeeded'"
              :percentage="100" 
              status="success"
              :stroke-width="8"
            />
            <el-progress 
              v-else-if="row.status === 'failed'"
              :percentage="100" 
              status="exception"
              :stroke-width="8"
            />
          </template>
        </el-table-column>

        <el-table-column :label="t('common.createdAt')" width="170">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>

        <el-table-column :label="t('common.action')" fixed="right" width="360">
          <template #default="{ row }">
            <div style="display: flex; gap: 4px; flex-wrap: nowrap;">
              <el-button
                v-if="row.status === 'running'"
                @click="pauseRun(row.id)"
                :icon="VideoPause"
                size="small"
              >
                {{ t('workflow.pause') }}
              </el-button>

              <el-button
                v-if="row.status === 'paused' || row.status === 'failed'"
                type="primary"
                @click="resumeRunFromDialog(row)"
                :icon="VideoPlay"
                size="small"
              >
                {{ t('workflow.resume') }}
              </el-button>

              <el-button
                @click="viewNodeStatus(row.id)"
                :icon="List"
                size="small"
              >
                {{ t('common.status') }}
              </el-button>
              
              <el-button
                type="danger"
                @click="deleteRun(row.id)"
                :icon="Delete"
                plain
                size="small"
              >
                {{ t('common.delete') }}
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- Node status dialog -->
    <el-dialog
      v-model="nodeStatusVisible"
      :title="t('workflow.nodeExecutionStatus')"
      width="760px"
      append-to-body
    >
      <el-table :data="nodeStatuses" v-loading="loadingNodeStatus" size="small">
        <el-table-column prop="node_id" :label="t('workflow.nodeId')" width="140" />
        <el-table-column prop="node_type" :label="t('workflow.nodeType')" width="170" />
        <el-table-column :label="t('common.status')" width="110">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('workflow.progress')" width="130">
          <template #default="{ row }">
            <el-progress :percentage="row.progress" :stroke-width="6" />
          </template>
        </el-table-column>
        <el-table-column prop="error" :label="t('common.error')" show-overflow-tooltip />
      </el-table>
    </el-dialog>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, VideoPause, VideoPlay, Close, List, Delete } from '@element-plus/icons-vue'
import { deleteRun as deleteRunApi } from '@renderer/api/workflows'
import request from '@renderer/api/request'

interface WorkflowRun {
  id: number
  workflow_id: number
  status: string
  created_at: string
  workflow?: {
    id: number
    name: string
  }
}

interface NodeStatus {
  node_id: string
  node_type: string
  status: string
  progress: number
  error?: string
}

interface RunStatusResponse {
  nodes: NodeStatus[]
}

const props = defineProps<{
  modelValue: boolean
  workflowId?: number
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'resume-run', run: WorkflowRun): void
}>()

const visible = ref(props.modelValue)
const { t } = useI18n()
const runs = ref<WorkflowRun[]>([])
const loading = ref(false)
const statusFilter = ref('')
const progressCache = ref<Record<number, number>>({})

const nodeStatusVisible = ref(false)
const nodeStatuses = ref<NodeStatus[]>([])
const loadingNodeStatus = ref(false)

let refreshTimer: number | null = null

watch(() => props.modelValue, (val) => {
  visible.value = val
  if (val) {
    loadRuns()
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
})

watch(visible, (val) => {
  emit('update:modelValue', val)
  if (!val) {
    stopAutoRefresh()
  }
})

onUnmounted(() => {
  stopAutoRefresh()
})

function startAutoRefresh() {
  stopAutoRefresh()
  refreshTimer = window.setInterval(() => {
    if (runs.value.some(r => r.status === 'running' || r.status === 'paused')) {
      loadRuns(true)
    }
  }, 3000)
}

function stopAutoRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

async function loadRuns(silent = false) {
  if (!silent) {
    loading.value = true
  }

  try {
    const params: any = { limit: 50, offset: 0 }
    if (statusFilter.value) {
      params.status = statusFilter.value
    }

    // If workflowId is specified, only load runs for that workflow
    const url = props.workflowId 
      ? `/workflows/${props.workflowId}/runs`
      : '/runs'
    
    const response = await request.get<WorkflowRun[]>(url, params, '/api')
    runs.value = response

    // Load progress for running tasks
    for (const run of runs.value) {
      if (run.status === 'running' || run.status === 'paused') {
        loadProgress(run.id)
      }
    }
  } catch (error: any) {
    if (!silent) {
      ElMessage.error(t('workflow.loadRunsFailed', { reason: error.message || error }))
    }
  } finally {
    if (!silent) {
      loading.value = false
    }
  }
}

async function loadProgress(runId: number) {
  try {
    const status = await request.get<RunStatusResponse>(
      `/workflows/runs/${runId}/status`,
      {},
      '/api',
      { showLoading: false }
    )
    
    if (status.nodes && status.nodes.length > 0) {
      const totalProgress = status.nodes.reduce((sum: number, node: NodeStatus) => {
        return sum + node.progress
      }, 0)
      progressCache.value[runId] = Math.round(totalProgress / status.nodes.length)
    }
  } catch (error) {
    // Fail silently to avoid disturbing the user
    console.warn(`[WorkflowRunsDialog] Failed to load progress: runId=${runId}`, error)
  }
}

function getProgress(runId: number): number {
  return progressCache.value[runId] || 0
}

async function pauseRun(runId: number) {
  try {
    await request.post(`/workflows/runs/${runId}/pause`, {}, '/api')
    ElMessage.success(t('workflow.paused'))
    loadRuns()
  } catch (error: any) {
    ElMessage.error(t('workflow.pauseFailed', { reason: error.message || error }))
  }
}

async function resumeRun(runId: number) {
  try {
    await request.post(`/workflows/runs/${runId}/resume`, {}, '/api')
    ElMessage.success(t('workflow.resumedFromBreakpoint'))
    loadRuns()
  } catch (error: any) {
    ElMessage.error(t('workflow.resumeFailed', { reason: error.message || error }))
  }
}

async function resumeRunFromDialog(run: WorkflowRun) {
  try {
    // Close the dialog
    visible.value = false

    // Notify parent component to resume execution
    emit('resume-run', run)
    
    ElMessage.success(t('workflow.resumingExecution'))
  } catch (error: any) {
    ElMessage.error(t('workflow.resumeFailed', { reason: error.message || error }))
  }
}

async function cancelRun(runId: number) {
  try {
    await ElMessageBox.confirm(t('workflow.confirmCancelRun'), t('workflow.confirmCancelTitle'), {
      type: 'warning'
    })

    await request.post(`/workflows/runs/${runId}/cancel`, {}, '/api')
    ElMessage.success(t('workflow.cancelled'))
    loadRuns()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(t('workflow.cancelFailed', { reason: error.message || error }))
    }
  }
}

async function viewNodeStatus(runId: number) {
  nodeStatusVisible.value = true
  loadingNodeStatus.value = true

  try {
    const status = await request.get<RunStatusResponse>(`/workflows/runs/${runId}/status`, {}, '/api')
    nodeStatuses.value = status.nodes || []
  } catch (error: any) {
    ElMessage.error(t('workflow.loadNodeStatusFailed', { reason: error.message || error }))
  } finally {
    loadingNodeStatus.value = false
  }
}

async function deleteRun(runId: number) {
  try {
    await ElMessageBox.confirm(t('workflow.confirmDeleteRun'), t('common.confirmDelete'), {
      type: 'warning',
      confirmButtonText: t('workflow.confirmDeleteBtn'),
      cancelButtonText: t('common.cancel')
    })

    await deleteRunApi(runId)
    ElMessage.success(t('workflow.runDeleted'))
    loadRuns()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(t('workflow.deleteFailed', { reason: error.message || error }))
    }
  }
}

function getStatusType(status: string): string {
  const typeMap: Record<string, string> = {
    running: 'primary',
    paused: 'warning',
    succeeded: 'success',
    failed: 'danger',
    cancelled: 'info',
    idle: 'info',
    pending: 'info',
    success: 'success',
    error: 'danger'
  }
  return typeMap[status] || 'info'
}

function getStatusLabel(status: string): string {
  const labelMap: Record<string, string> = {
    running: t('workflow.statusRunning'),
    paused: t('workflow.statusPaused'),
    succeeded: t('workflow.statusCompleted'),
    failed: t('workflow.statusFailed'),
    cancelled: t('workflow.statusCancelled'),
    idle: t('workflow.statusIdle'),
    pending: t('workflow.statusPending'),
    success: t('workflow.statusSuccess'),
    error: t('workflow.statusError'),
    skipped: t('workflow.statusSkipped')
  }
  return labelMap[status] || status
}

function formatTime(time?: string | number): string {
  if (!time) return '-'
  
  // If it's a number (Unix timestamp), multiply by 1000 to convert to milliseconds
  // But if the number is very small (< 100000000), it's likely invalid data
  if (typeof time === 'number') {
    console.warn('[formatTime] Received numeric timestamp:', time)
    if (time < 100000000) {
      console.error('[formatTime] Timestamp is abnormally small, likely invalid data')
      return t('workflow.dataAbnormal')
    }
    time = time * 1000 // Convert to milliseconds
  }
  
  const date = new Date(time)
  
  // Check if the date is valid
  if (isNaN(date.getTime())) {
    console.error('[formatTime] Invalid date:', time)
    return t('workflow.invalidDate')
  }

  // Check if the date is within a reasonable range (2020-2030)
  const year = date.getFullYear()
  if (year < 2020 || year > 2030) {
    console.error('[formatTime] Date out of reasonable range:', date.toISOString(), 'original value:', time)
    return t('workflow.dateAbnormal')
  }
  
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}
</script>

<style scoped>
.runs-dialog-content {
  min-height: 400px;
}

.filters {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
}
</style>
