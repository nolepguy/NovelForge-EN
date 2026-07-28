<template>
  <div class="workflow-container">
    <!-- Top toolbar -->
    <div class="workflow-toolbar">
      <div class="toolbar-left">
        <el-select
          v-model="currentWorkflowId"
          :placeholder="t('workflow.selectWorkflow')"
          filterable
          clearable
          @change="onWorkflowChange"
          style="width: 300px"
        >
          <el-option
            v-for="wf in workflowList"
            :key="wf.id"
            :label="wf.name"
            :value="wf.id"
          >
            <span style="float: left">{{ wf.name }}</span>
            <span style="float: right; color: #8492a6; font-size: 13px">
              {{ formatDate(wf.updated_at) }}
            </span>
          </el-option>
        </el-select>

        <el-button @click="createNewWorkflow">
          <el-icon><Plus /></el-icon>
          <span>{{ t('workflow.createNew') }}</span>
        </el-button>
        
        <el-button 
          @click="deleteWorkflow" 
          :disabled="!currentWorkflowId"
          type="danger"
          plain
        >
          <el-icon><Delete /></el-icon>
          <span>{{ t('common.delete') }}</span>
        </el-button>
      </div>

      <div class="toolbar-right">
        <div class="toolbar-switch-item">
          <span class="switch-label">{{ t('workflow.persistRuns') }}</span>
          <el-switch
            v-model="keepRunHistory"
            @change="onKeepRunHistoryChange"
            :disabled="!currentWorkflowId"
            size="small"
          />
        </div>
        
        <el-divider direction="vertical" />
        
        <el-button 
          @click="showRunsDialog = true"
          plain
        >
          <el-icon><Clock /></el-icon>
          <span>{{ t('workflow.runHistory') }}</span>
        </el-button>
        
        <el-button 
          @click="validateWorkflowCode" 
          :disabled="!currentWorkflowId"
          plain
        >
          <el-icon><CircleCheck /></el-icon>
          <span>{{ t('workflow.validateCode') }}</span>
        </el-button>
        
        <el-divider direction="vertical" />
        
        <el-button @click="saveWorkflow">
          <el-icon><Document /></el-icon>
          <span>{{ t('common.save') }}</span>
        </el-button>
        
        <el-divider direction="vertical" />
        
        <el-button
          v-if="canStart"
          @click="runWorkflow"
          type="primary"
        >
          <el-icon><VideoPlay /></el-icon>
          <span>{{ t('workflow.run') }}</span>
        </el-button>
        <el-button
          v-if="canPause"
          @click="pauseCurrentRun"
          type="warning"
        >
          <el-icon><VideoPause /></el-icon>
          <span>{{ t('workflow.pause') }}</span>
        </el-button>
        <el-button
          v-if="canResume"
          @click="resumeCurrentRun"
          type="success"
        >
          <el-icon><VideoPlay /></el-icon>
          <span>{{ t('workflow.resume') }}</span>
        </el-button>
      </div>
    </div>

    <!-- Main content area -->
    <div class="workflow-content">
      <!-- Node library -->
      <div class="library-section" :style="{ width: libraryWidth + 'px' }">
        <node-library @add-node="onAddNode" />
      </div>

      <!-- Resize handle - Node library -->
      <div class="resize-handle" @mousedown="startResizing('library')"></div>

      <!-- Node block editor -->
      <div class="editor-section">
        <div class="section-header">
          <span class="section-title">{{ t('workflow.workflowNodes') }}</span>
          <span class="section-subtitle" v-if="currentWorkflowName">
            {{ currentWorkflowName }}
          </span>
          <div class="view-mode-toggle" style="margin-left: auto">
             <el-radio-group v-model="viewMode" size="small">
                <el-radio-button label="visual">
                   <el-icon><List /></el-icon> {{ t('workflow.visual') }}
                </el-radio-button>
                <el-radio-button label="code">
                   <el-icon><Document /></el-icon> {{ t('workflow.code') }}
                </el-radio-button>
             </el-radio-group>
          </div>
        </div>
        <div style="flex: 1; overflow: hidden; position: relative">
            <node-block-editor
              v-if="viewMode === 'visual'"
              v-model="code"
              :is-running="isRunning"
              :workflow-id="currentWorkflowId"
              :revision="currentWorkflowRevision"
              @revision-changed="handleVisualRevisionChanged"
            />
            <code-editor
              v-else
              v-model="code"
            />
        </div>
      </div>

      <!-- Resize handle - Notebook -->
      <div class="resize-handle" @mousedown="startResizing('notebook')"></div>

      <!-- Notebook execution view -->
      <div class="notebook-section" :style="{ width: notebookWidth + 'px' }">
        <workflow-notebook
          :cells="notebookCells"
          :is-running="isRunning"
          @cell-output="onCellOutput"
          @clear-output="clearOutput"
        />
      </div>
    </div>

    <!-- Run history dialog -->
    <workflow-runs-dialog 
      v-model="showRunsDialog" 
      :workflow-id="currentWorkflowId"
      @resume-run="onResumeRun"
    />

    <workflow-agent-dialog
      :workflow-id="currentWorkflowId"
      :revision="currentWorkflowRevision"
      @applied="handleWorkflowAgentApplied"
    />

    <!-- Validation result dialog -->
    <el-dialog
      v-model="showValidationDialog"
      :title="t('workflow.validationResult')"
      width="680px"
    >
      <div v-if="validationResult">
        <el-alert
          :type="validationResult.is_valid ? 'success' : 'error'"
          :title="validationResult.is_valid ? t('workflow.validationPassed') : t('workflow.validationFailed')"
          :closable="false"
          style="margin-bottom: 16px"
        >
          <template v-if="!validationResult.is_valid">
            {{ t('workflow.foundErrors', { count: validationResult.errors.length }) }}
            <span v-if="validationResult.warnings.length > 0">
              {{ t('workflow.andWarnings', { count: validationResult.warnings.length }) }}
            </span>
          </template>
        </el-alert>

        <!-- Error list -->
        <div v-if="validationResult.errors.length > 0" style="margin-bottom: 16px">
          <h4 style="margin-bottom: 8px; color: #f56c6c">{{ t('workflow.errors') }}</h4>
          <el-scrollbar max-height="300px">
            <div
              v-for="(error, index) in validationResult.errors"
              :key="'error-' + index"
              class="validation-item error-item"
            >
              <div class="validation-header">
                <el-tag type="danger" size="small">{{ error.error_type }}</el-tag>
                <span class="validation-location">{{ t('workflow.line', { line: error.line }) }}</span>
                <span v-if="error.variable" class="validation-variable">{{ error.variable }}</span>
              </div>
              <div class="validation-message">{{ error.message }}</div>
              <div v-if="error.suggestion" class="validation-suggestion">
                💡 {{ error.suggestion }}
              </div>
            </div>
          </el-scrollbar>
        </div>

        <!-- Warning list -->
        <div v-if="validationResult.warnings.length > 0">
          <h4 style="margin-bottom: 8px; color: #e6a23c">{{ t('workflow.warnings') }}</h4>
          <el-scrollbar max-height="200px">
            <div
              v-for="(warning, index) in validationResult.warnings"
              :key="'warning-' + index"
              class="validation-item warning-item"
            >
              <div class="validation-header">
                <el-tag type="warning" size="small">{{ warning.error_type }}</el-tag>
                <span class="validation-location">{{ t('workflow.line', { line: warning.line }) }}</span>
                <span v-if="warning.variable" class="validation-variable">{{ warning.variable }}</span>
              </div>
              <div class="validation-message">{{ warning.message }}</div>
              <div v-if="warning.suggestion" class="validation-suggestion">
                💡 {{ warning.suggestion }}
              </div>
            </div>
          </el-scrollbar>
        </div>
      </div>

      <template #footer>
        <el-button @click="showValidationDialog = false">{{ t('common.close') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { Plus, Refresh, Document, Delete, VideoPlay, VideoPause, Close, List, Clock, CircleCheck, ArrowDown } from '@element-plus/icons-vue'
import NodeBlockEditor from './editor/NodeBlockEditor.vue'
import CodeEditor from './editor/CodeEditor.vue'
import WorkflowNotebook from './notebook/WorkflowNotebook.vue'
import NodeLibrary from './panels/NodeLibrary.vue'
import WorkflowRunsDialog from './dialogs/WorkflowRunsDialog.vue'
import WorkflowAgentDialog from './WorkflowAgentDialog.vue'
import { useWorkflowExecution } from '@/composables/useWorkflowExecution'
import { useWorkflowProgress } from '@/composables/useWorkflowProgress'
import { applyWorkflowPatch } from '@/api/workflowAgent'
import {
  listWorkflows,
  saveCodeWorkflow,
  getCodeWorkflow,
  updateWorkflow,
  deleteWorkflow as deleteWorkflowApi,
  validateWorkflow
} from '@/api/workflows'
import request from '@/api/request'

const { t } = useI18n()

// Manage execution state via a state machine
const {
  execution,
  isRunning,
  isPaused,
  isIdle,
  canPause,
  canResume,
  canStart,
  start: startExecution,
  updateRunId,
  pause: pauseExecution,
  resume: resumeExecution,
  complete: completeExecution,
  fail: failExecution,
  reset: resetExecution
} = useWorkflowExecution()

// Progress management
const { startWorkflow, pauseWorkflow } = useWorkflowProgress()

const code = ref(``)
const showRunsDialog = ref(false)
const showValidationDialog = ref(false)
const validationResult = ref(null)

const viewMode = ref('visual') // 'visual' | 'code'
const notebookCells = reactive([])
let currentWorkflowId = ref(null) // Current workflow ID
let currentWorkflowName = ref(t('workflow.unnamedWorkflow')) // Current workflow name
const currentWorkflowRevision = ref('')
const keepRunHistory = ref(false) // Whether to persist run history
const workflowList = ref([]) // Workflow list

// Resize panel widths
const libraryWidth = ref(280)
const notebookWidth = ref(500)
const minLibraryWidth = 200
const maxLibraryWidth = 500
const minNotebookWidth = 300
const maxNotebookWidth = 800
let resizingPanel = ref(null)
let startX = 0
let startWidth = 0

function startResizing(panel) {
  resizingPanel.value = panel
  startX = window.event.clientX
  startWidth = panel === 'library' ? libraryWidth.value : notebookWidth.value
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
  window.addEventListener('mousemove', handleResizing)
  window.addEventListener('mouseup', stopResizing)
}

function handleResizing(e) {
  if (!resizingPanel.value) return
  
  if (resizingPanel.value === 'library') {
    let newWidth = startWidth + (e.clientX - startX)
    newWidth = Math.max(minLibraryWidth, Math.min(maxLibraryWidth, newWidth))
    libraryWidth.value = newWidth
  } else if (resizingPanel.value === 'notebook') {
    let newWidth = startWidth - (e.clientX - startX)
    newWidth = Math.max(minNotebookWidth, Math.min(maxNotebookWidth, newWidth))
    notebookWidth.value = newWidth
  }
}

function stopResizing() {
  resizingPanel.value = null
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
  window.removeEventListener('mousemove', handleResizing)
  window.removeEventListener('mouseup', stopResizing)
}

// Load the workflow list
const loadWorkflowList = async () => {
  try {
    const workflows = await listWorkflows()
    // All workflows are code-style workflows (dsl_version === 2)
    workflowList.value = workflows.filter(wf => {
      return wf.dsl_version === 2
    })
  } catch (error) {
    console.error('[Workflow] Failed to load workflow list:', error)
    ElMessage.error(t('workflow.loadListFailed'))
  }
}

// Refresh the workflow list
const refreshWorkflowList = async () => {
  await loadWorkflowList()
  ElMessage.success(t('workflow.listRefreshed'))
}

// Switch workflow
const onWorkflowChange = async (workflowId) => {
  if (!workflowId) {
    // Clear selection
    currentWorkflowId.value = null
    currentWorkflowName.value = t('workflow.unnamedWorkflow')
    code.value = `# Example workflow
#@node(description="Select project")
project = Logic.SelectProject(project_id=1)
#</node>

#@node(description="Load novel directory")
novel = Novel.Load(root_path="E:\\\\Novels\\\\book")
#</node>

#@node(description="Batch create volume cards")
cards = Card.BatchUpsert(
    items=novel.volume_list,
    card_type="volume",
    title_template="{item}"
)
#</node>`
    notebookCells.length = 0
    return
  }

  try {
    const workflow = await getCodeWorkflow(workflowId)
    currentWorkflowId.value = workflow.id
    currentWorkflowName.value = workflow.name
    code.value = workflow.code || ''
    currentWorkflowRevision.value = workflow.revision || ''
    keepRunHistory.value = workflow.keep_run_history || false // Load persistence setting
    notebookCells.length = 0 // Clear output
  } catch (error) {
    console.error('[Workflow] Failed to load workflow:', error)
    ElMessage.error(t('workflow.loadFailed'))
  }
}

// Create a new workflow
const createNewWorkflow = async () => {
  try {
    const { value: name } = await ElMessageBox.prompt(t('workflow.inputNamePrompt'), t('workflow.createNewWorkflow'), {
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
      inputValue: t('workflow.newWorkflow'),
      inputPattern: /\S+/,
      inputErrorMessage: t('workflow.nameEmpty'),
      inputValidator: (value) => {
        if (!value || !value.trim()) {
          return t('workflow.nameEmpty')
        }
        // Check for duplicate names
        const exists = workflowList.value.some(wf => wf.name === value.trim())
        if (exists) {
          return t('workflow.nameExists')
        }
        return true
      }
    })

    // Create a new workflow using the marker DSL template
    const initialCode = `# New workflow
#@node(description="Select project")
project = Logic.SelectProject(project_id=1)
#</node>`
    const workflow = await saveCodeWorkflow(name, initialCode)
    currentWorkflowId.value = workflow.id
    currentWorkflowName.value = workflow.name
    code.value = initialCode  // Update code
    currentWorkflowRevision.value = ''

    // Refresh list
    await loadWorkflowList()

    ElMessage.success(t('workflow.created', { name: workflow.name }))
  } catch (error) {
    if (error !== 'cancel') {
      console.error('[Workflow] Failed to create workflow:', error)
      ElMessage.error(t('workflow.createFailed'))
    }
  }
}

// Delete the workflow
const deleteWorkflow = async () => {
  if (!currentWorkflowId.value) {
    ElMessage.warning(t('workflow.selectToDelete'))
    return
  }

  try {
    await ElMessageBox.confirm(
      t('workflow.confirmDelete', { name: currentWorkflowName.value }),
      t('workflow.deleteWorkflow'),
      {
        confirmButtonText: t('workflow.confirmDeleteBtn'),
        cancelButtonText: t('common.cancel'),
        type: 'warning'
      }
    )

    // Delete the workflow
    await deleteWorkflowApi(currentWorkflowId.value)

    // Clear current selection
    currentWorkflowId.value = null
    currentWorkflowName.value = t('workflow.unnamedWorkflow')
    currentWorkflowRevision.value = ''
    code.value = `# Example workflow
#@node(description="Select project")
project = Logic.SelectProject(project_id=1)
#</node>

#@node(description="Load novel directory")
novel = Novel.Load(root_path="E:\\\\Novels\\\\book")
#</node>

#@node(description="Batch create volume cards")
cards = Card.BatchUpsert(
    items=novel.volume_list,
    card_type="volume",
    title_template="{item}"
)
#</node>`
    notebookCells.length = 0

    // Refresh list
    await loadWorkflowList()

    ElMessage.success(t('workflow.deleted'))
  } catch (error) {
    if (error !== 'cancel') {
      console.error('[Workflow] Failed to delete workflow:', error)
      ElMessage.error(t('workflow.deleteWorkflowFailed'))
    }
  }
}

// Format date
const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now - date

  // Less than 1 minute
  if (diff < 60000) return t('workflow.justNow')
  // Less than 1 hour
  if (diff < 3600000) return t('workflow.minutesAgo', { n: Math.floor(diff / 60000) })
  // Less than 1 day
  if (diff < 86400000) return t('workflow.hoursAgo', { n: Math.floor(diff / 3600000) })
  // Less than 7 days
  if (diff < 604800000) return t('workflow.daysAgo', { n: Math.floor(diff / 86400000) })

  // More than 7 days: show the date
  return date.toLocaleDateString('zh-CN')
}

// Persistence toggle change
const onKeepRunHistoryChange = async (value) => {
  if (!currentWorkflowId.value) return
  
  try {
    await updateWorkflow(currentWorkflowId.value, {
      keep_run_history: value
    })
    ElMessage.success(value ? t('workflow.persistenceEnabled') : t('workflow.persistenceDisabled'))
  } catch (error) {
    console.error('[Workflow] Failed to update persistence setting:', error)
    ElMessage.error(t('workflow.updatePersistenceFailed'))
    // Restore original value
    keepRunHistory.value = !value
  }
}

// Run the workflow
const runWorkflow = async () => {
  if (!canStart.value) return

  notebookCells.length = 0 // Clear previous output

  try {
    // 1. Re-save the workflow on each run (ensure the code is up to date)
    if (currentWorkflowId.value) {
      // Update existing workflow
      await updateWorkflow(currentWorkflowId.value, {
        definition_code: code.value
      })
      currentWorkflowRevision.value = ''
    } else {
      // Create a new workflow
      const workflow = await saveCodeWorkflow(currentWorkflowName.value, code.value)
      currentWorkflowId.value = workflow.id
    }

    // 2. Run the workflow
    // Use the global SSE connection manager (auto-updates the status bar)
    await startWorkflow(
      currentWorkflowId.value,
      currentWorkflowName.value,
      {
        onRunStarted: (actualRunId) => {
          // Update runId in the state machine (without changing state)
          updateRunId(actualRunId)
        },
        onStart: (event) => {
          notebookCells.push({
            id: event.statement?.variable || 'unknown',
            type: 'execution',
            content: event.statement?.code || '',
            description: event.statement?.description || '',
            status: 'running',
            outputs: []
          })
        },
        onProgress: (event) => {
          const cellIndex = notebookCells.findIndex(c => c.id === event.statement?.variable)
          if (cellIndex !== -1) {
            // Use splice to force a reactive update
            const updatedCell = {
              ...notebookCells[cellIndex],
              status: 'progress',
              progress: event.percent,
              message: event.message
            }
            notebookCells.splice(cellIndex, 1, updatedCell)
          }
        },
        onComplete: (event) => {
          const cellIndex = notebookCells.findIndex(c => c.id === event.statement?.variable)
          if (cellIndex !== -1) {
            notebookCells[cellIndex] = {
              ...notebookCells[cellIndex],
              status: 'completed',
              outputs: [event.result],
              resumed: event.resumed || false  // Mark whether this is a resumed node
            }
          } else {
            // If the cell doesn't exist (resumed node), create one
            notebookCells.push({
              id: event.statement?.variable || 'unknown',
              type: 'execution',
              content: event.statement?.code || '',
              status: 'completed',
              outputs: [event.result],
              resumed: true  // Mark as a resumed node
            })
          }
        },
        onError: (event) => {
          const cell = notebookCells.find(c => c.id === event.statement?.variable)
          if (cell) {
            cell.status = 'error'
            cell.error = event.error
          } else {
            // No matching cell (e.g. parse failure); create an error cell
            notebookCells.push({
              id: 'error-' + Date.now(),
              type: 'execution',
              content: event.statement?.code || t('workflow.codeParseFailed'),
              status: 'error',
              error: event.error || t('workflow.unknownError'),
              outputs: []
            })
          }
          // Mark as failed
          failExecution(event.error || t('workflow.runFailed'))
          ElMessage.error(event.error || t('workflow.runFailed'))
        },
        onEnd: () => {
          // If not in a failed state, mark as completed
          if (execution.state === 'running') {
            completeExecution()
          }
        }
      },
      false // resume=false, start from scratch
    )

    // Initial state transition (using a temporary runId of 0)
    // The real runId will be updated in the onRunStarted callback
    startExecution(currentWorkflowId.value, 0)
  } catch (error) {
    console.error('[Workflow] Workflow execution failed:', error)
    failExecution(error.message || t('workflow.runFailed'))
    ElMessage.error(error.message || t('workflow.runFailed'))
  }
}

// Clear output
const clearOutput = () => {
  notebookCells.length = 0
  // Reset the state machine
  if (!isIdle.value) {
    resetExecution()
  }
}

// Pause the current run
const pauseCurrentRun = async () => {
  if (!canPause.value) return
  
  if (execution.runId === null || execution.runId === undefined) {
    console.error('[Workflow] Cannot pause: missing runId')
    return
  }
  
  try {
    console.log('[Workflow] Starting to pause workflow:', execution.runId)

    // 1. First close the SSE connection via the store (stop receiving events)
    pauseWorkflow(execution.runId)

    // 2. Call the pause API to update the database state (the backend will stop execution)
    await request.post(`/workflows/runs/${execution.runId}/pause`, {}, '/api')

    // 3. Transition the state machine to the paused state
    pauseExecution()

    console.log('[Workflow] Workflow paused')
    ElMessage.success(t('workflow.paused'))
  } catch (error) {
    console.error('[Workflow] Pause failed:', error)
    ElMessage.error(t('workflow.pauseFailed', { reason: error.message || error }))
  }
}

// Resume the current run
const resumeCurrentRun = async () => {
  if (!canResume.value) return
  
  if (execution.runId === null || execution.runId === undefined || execution.workflowId === null || execution.workflowId === undefined) {
    console.error('[Workflow] Cannot resume: missing runId or workflowId')
    return
  }
  
  try {
    // Clear previous output (avoid duplicate display)
    notebookCells.length = 0

    // Resume execution: pass resume=true and run_id
    await startWorkflow(
      execution.workflowId,
      currentWorkflowName.value,
      {
        onStart: (event) => {
          notebookCells.push({
            id: event.statement?.variable || 'unknown',
            type: 'execution',
            content: event.statement?.code || '',
            status: 'running',
            outputs: []
          })
        },
        onProgress: (event) => {
          const cellIndex = notebookCells.findIndex(c => c.id === event.statement?.variable)
          if (cellIndex !== -1) {
            const updatedCell = {
              ...notebookCells[cellIndex],
              status: 'progress',
              progress: event.percent,
              message: event.message
            }
            notebookCells.splice(cellIndex, 1, updatedCell)
          }
        },
        onComplete: (event) => {
          const cellIndex = notebookCells.findIndex(c => c.id === event.statement?.variable)
          if (cellIndex !== -1) {
            notebookCells[cellIndex] = {
              ...notebookCells[cellIndex],
              status: 'completed',
              outputs: [event.result],
              resumed: event.resumed || false
            }
          } else {
            // If the cell doesn't exist (resumed node), create one
            notebookCells.push({
              id: event.statement?.variable || 'unknown',
              type: 'execution',
              content: event.statement?.code || '',
              description: event.statement?.description || '',
              status: 'completed',
              outputs: [event.result],
              resumed: true
            })
          }
        },
        onError: (event) => {
          const cell = notebookCells.find(c => c.id === event.statement?.variable)
          if (cell) {
            cell.status = 'error'
            cell.error = event.error
          } else {
            notebookCells.push({
              id: 'error-' + Date.now(),
              type: 'execution',
              content: event.statement?.code || t('workflow.codeParseFailed'),
              description: event.statement?.description || '',
              status: 'error',
              error: event.error || t('workflow.unknownError'),
              outputs: []
            })
          }
          // Mark as failed
          failExecution(event.error || t('workflow.runFailed'))
          ElMessage.error(event.error || t('workflow.runFailed'))
        },
        onEnd: () => {
          // If not in a failed state, mark as completed
          if (execution.state === 'running') {
            completeExecution()
          }
        }
      },
      true, // resume=true
      execution.runId // Pass run_id
    )

    // Transition the state machine to the running state
    resumeExecution()

    ElMessage.success(t('workflow.resumed'))
  } catch (error) {
    console.error('[Workflow] Resume execution failed:', error)
    failExecution(error.message || t('workflow.resumeFailedPlain'))
    ElMessage.error(error.message || t('workflow.resumeFailedPlain'))
  }
}

// Cancel the current run
const cancelCurrentRun = async () => {
  if (!currentRunId.value) return
  
  try {
    await ElMessageBox.confirm(t('workflow.confirmCancelRun'), t('workflow.confirmCancelTitle'), {
      type: 'warning'
    })
    
    await request.post(`/workflows/runs/${currentRunId.value}/cancel`, {}, '/api')
    ElMessage.success(t('workflow.cancelled'))
    
    isRunning.value = false
    isPaused.value = false
    currentRunId.value = null
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(t('workflow.cancelFailed', { reason: error.message || error }))
    }
  }
}

// Save the workflow
const saveWorkflow = async () => {
  try {
    if (currentWorkflowId.value) {
      // Update existing workflow
      await updateWorkflow(currentWorkflowId.value, {
        definition_code: code.value
      })
      try {
        const workflowData = await getCodeWorkflow(currentWorkflowId.value)
        currentWorkflowRevision.value = workflowData.revision || ''
      } catch {
        // ignore
      }
      ElMessage.success(t('workflow.updated'))
    } else {
      // Create a new workflow: first ask for the name
      const { value: name } = await ElMessageBox.prompt(t('workflow.inputNamePrompt'), t('workflow.saveWorkflow'), {
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
        inputValue: currentWorkflowName.value,
        inputPattern: /\S+/,
        inputErrorMessage: t('workflow.nameEmpty')
      })

      // Save the code-style workflow
      const workflow = await saveCodeWorkflow(name, code.value)
      currentWorkflowId.value = workflow.id
      currentWorkflowName.value = workflow.name
      currentWorkflowRevision.value = ''
      ElMessage.success(t('workflow.saved', { name: workflow.name }))
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('[Workflow] Failed to save workflow:', error)
      ElMessage.error(error.message || t('workflow.saveFailed'))
    }
  }
}

// Validate the workflow
const validateWorkflowCode = async () => {
  if (!currentWorkflowId.value) {
    ElMessage.warning(t('workflow.selectOrSaveFirst'))
    return
  }

  try {
    const runPatchDryRun = async () => {
      return applyWorkflowPatch(currentWorkflowId.value, {
        base_revision: currentWorkflowRevision.value || '',
        patch_ops: [
          {
            op: 'replace_code',
            new_code: code.value || '',
            reason: 'ui_validate',
          },
        ],
        dry_run: true,
      })
    }

    let patchResult
    try {
      patchResult = await runPatchDryRun()
    } catch (error) {
      // If the revision is stale, refresh and retry once
      const status = error?.response?.status
      const detail = error?.response?.data?.detail
      if (status === 409 && detail?.code === 'revision_mismatch') {
        const workflowData = await getCodeWorkflow(currentWorkflowId.value)
        currentWorkflowRevision.value = workflowData.revision || currentWorkflowRevision.value
        patchResult = await runPatchDryRun()
      } else {
        throw error
      }
    }

    validationResult.value = patchResult?.validation || {
      is_valid: false,
      errors: [
        {
          line: 0,
          variable: '',
          error_type: 'unknown',
          message: patchResult?.error || t('workflow.validationFailed'),
          suggestion: null,
        },
      ],
      warnings: [],
    }
    showValidationDialog.value = true

    if (validationResult.value.is_valid) {
      ElMessage.success(t('workflow.validationPassed'))
    } else {
      ElMessage.error(t('workflow.foundErrors', { count: validationResult.value.errors.length }))
    }
  } catch (error) {
    console.error('Failed to validate workflow:', error)
    ElMessage.error(t('workflow.validateFailed'))
  }
}

// Handle code changes
const onCodeChange = (newCode) => {
  code.value = newCode
}

// Handle node selection
// const onNodeSelected = (node) => {
//   selectedNode.value = node
// }

// Handle node updates (from the property panel)
const onNodeUpdate = (updatedNode) => {
  // Regenerate the code
  // Need to find the corresponding node and replace its code
  const lines = code.value.split('\n')

  // Simple implementation: find the line containing the variable name and replace it
  // A better implementation should maintain a node list inside NodeBlockEditor
  let updated = false
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].includes(`${updatedNode.variable} =`)) {
      lines[i] = updatedNode.code
      updated = true
      break
    }
  }

  if (updated) {
    code.value = lines.join('\n')
    ElMessage.success(t('workflow.nodeUpdated'))
  } else {
    ElMessage.error(t('workflow.updateFailedNodeNotFound'))
  }
}

// Add a node (from the node library)
const onAddNode = (nodeType) => {
  // Generate a unique variable name
  const baseName = generateVariableName(nodeType)
  const variableName = generateUniqueVariableName(baseName)

  // Generate the node code with the comment marker DSL
  const nodeCode = `#@node()
${variableName} = ${nodeType}()
#</node>`

  // Append to the end of the code
  const newCode = code.value.trim()
  if (newCode) {
    code.value = newCode + '\n\n' + nodeCode  // Separate with double newline
  } else {
    code.value = nodeCode
  }

  ElMessage.success(t('workflow.nodeAdded'))
}

// Generate a base variable name from the node type
function generateVariableName(nodeType) {
  // Extract the node type name and convert it to a suitable variable name
  const parts = nodeType.split('.')
  if (parts.length >= 2) {
    const method = parts[1].toLowerCase()
    // Remove common verb prefixes
    const cleanMethod = method.replace(/^(get|set|create|update|delete|fetch|load)_?/, '')
    return cleanMethod || method
  }
  return nodeType.replace(/\./g, '_').toLowerCase()
}

// Generate a unique variable name
function generateUniqueVariableName(baseName) {
  let counter = 2
  let variableName = baseName

  // Check whether a variable with the same name already exists
  const allLines = code.value.split('\n')
  const usedVariables = new Set()

  allLines.forEach(line => {
    // Assignment form: variable = ...
    const assignMatch = line.match(/^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*/)
    if (assignMatch) {
      usedVariables.add(assignMatch[1])
    }
  })

  // If the base name already exists, append a numeric suffix
  while (usedVariables.has(variableName)) {
    variableName = `${baseName}${counter++}`
  }

  return variableName
}

// Cell output handler
const onCellOutput = (output) => {
  // Handle cell output
}

// Resume execution from a run record
const onResumeRun = async (run) => {
  // Clear previous output
  notebookCells.length = 0

  // Load the workflow code
  let workflowData
  try {
    workflowData = await getCodeWorkflow(run.workflow_id)
    code.value = workflowData.code || ''
    currentWorkflowName.value = workflowData.name
    currentWorkflowId.value = run.workflow_id
    currentWorkflowRevision.value = workflowData.revision || ''
  } catch (error) {
    console.error('[Workflow] Failed to load workflow:', error)
    ElMessage.error(t('workflow.loadFailed'))
    return
  }

  try {
    await startWorkflow(
      run.workflow_id,
      workflowData.name,  // Use workflowData.name
      {
        onStart: (event) => {
          notebookCells.push({
            id: event.statement?.variable || 'unknown',
            type: 'execution',
            content: event.statement?.code || '',
            description: event.statement?.description || '',
            status: 'running',
            outputs: []
          })
        },
        onProgress: (event) => {
          const cellIndex = notebookCells.findIndex(c => c.id === event.statement?.variable)
          if (cellIndex !== -1) {
            const updatedCell = {
              ...notebookCells[cellIndex],
              status: 'progress',
              progress: event.percent,
              message: event.message
            }
            notebookCells.splice(cellIndex, 1, updatedCell)
          }
        },
        onComplete: (event) => {
          const cellIndex = notebookCells.findIndex(c => c.id === event.statement?.variable)
          if (cellIndex !== -1) {
            notebookCells[cellIndex] = {
              ...notebookCells[cellIndex],
              status: 'completed',
              outputs: [event.result],
              resumed: event.resumed || false
            }
          } else {
            // If the cell doesn't exist (resumed node), create one
            notebookCells.push({
              id: event.statement?.variable || 'unknown',
              type: 'execution',
              content: event.statement?.code || '',
              description: event.statement?.description || '',
              status: 'completed',
              outputs: [event.result],
              resumed: true
            })
          }
        },
        onError: (event) => {
          const cell = notebookCells.find(c => c.id === event.statement?.variable)
          if (cell) {
            cell.status = 'error'
            cell.error = event.error
          } else {
            notebookCells.push({
              id: 'error-' + Date.now(),
              type: 'execution',
              content: event.statement?.code || t('workflow.codeParseFailed'),
              description: event.statement?.description || '',
              status: 'error',
              error: event.error || t('workflow.unknownError'),
              outputs: []
            })
          }
          // Mark as failed
          failExecution(event.error || t('workflow.runFailed'))
          ElMessage.error(event.error || t('workflow.runFailed'))
        },
        onEnd: () => {
          // If not in a failed state, mark as completed
          if (execution.state === 'running') {
            completeExecution()
          }
        }
      },
      true, // resume=true
      run.id // Pass run_id
    )

    // Transition the state machine to the running state
    startExecution(run.workflow_id, run.id)
  } catch (error) {
    console.error('[Workflow] Resume execution failed:', error)
    failExecution(error.message || t('workflow.resumeFailedPlain'))
    ElMessage.error(error.message || t('workflow.resumeFailedPlain'))
  }
}

// Cleanup on component unmount
onUnmounted(() => {
  // The SSE connection is managed by the store; no manual cleanup needed on unmount
})

// Load the workflow list on mount
onMounted(() => {
  loadWorkflowList()
})

const handleWorkflowAgentApplied = (payload) => {
  code.value = payload.newCode || code.value
  if (payload.newRevision) {
    currentWorkflowRevision.value = payload.newRevision
  }
}

const handleVisualRevisionChanged = (revision) => {
  if (typeof revision === 'string' && revision.trim()) {
    currentWorkflowRevision.value = revision
  }
}
</script>

<style scoped>
.workflow-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--el-bg-color-page);
}

.workflow-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color);
  box-shadow: 0 1px 4px var(--el-box-shadow-light);
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.toolbar-switch-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 12px;
  height: 32px;
  border-radius: 4px;
  background: var(--el-fill-color-light);
}

.switch-label {
  font-size: 14px;
  color: var(--el-text-color-regular);
  white-space: nowrap;
}

.dropdown-switch-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  min-width: 180px;
}

.switch-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--el-text-color-regular);
}

.workflow-content {
  display: flex;
  flex: 1;
  overflow: hidden;
  gap: 0;
  background: var(--el-border-color-lighter);
  position: relative;
}

.library-section {
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color);
  overflow: hidden;
  flex-shrink: 0;
}

.resize-handle {
  width: 4px;
  background: var(--el-border-color-lighter);
  cursor: col-resize;
  flex-shrink: 0;
  position: relative;
  transition: background-color 0.2s;
}

.resize-handle:hover {
  background: var(--el-color-primary);
}

.resize-handle:active {
  background: var(--el-color-primary);
}

.editor-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color);
  overflow: hidden;
  min-width: 400px;
}

.property-section {
  width: 350px;
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color);
  overflow: hidden;
}

.notebook-section {
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color);
  overflow: hidden;
  flex-shrink: 0;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--el-fill-color-light);
  border-bottom: 1px solid var(--el-border-color);
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.section-subtitle {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-left: 8px;
}

/* Validation result styles */
.validation-item {
  padding: 12px;
  margin-bottom: 8px;
  border-radius: 4px;
  border-left: 3px solid;
}

.error-item {
  background-color: var(--el-color-danger-light-9);
  border-left-color: var(--el-color-danger);
}

.warning-item {
  background-color: var(--el-color-warning-light-9);
  border-left-color: var(--el-color-warning);
}

.validation-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.validation-location {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.validation-variable {
  font-size: 12px;
  font-family: 'Courier New', monospace;
  color: var(--el-text-color-regular);
  background-color: var(--el-fill-color);
  padding: 2px 6px;
  border-radius: 3px;
}

.validation-message {
  font-size: 14px;
  color: var(--el-text-color-primary);
  margin-bottom: 4px;
}

.validation-suggestion {
  font-size: 13px;
  color: var(--el-text-color-regular);
  font-style: italic;
}
.toolbar-left .el-button,
.toolbar-right .el-button {
  white-space: nowrap;
}

.section-title {
  white-space: nowrap;
}

.toolbar-right {
  flex-wrap: wrap;
}
</style>
