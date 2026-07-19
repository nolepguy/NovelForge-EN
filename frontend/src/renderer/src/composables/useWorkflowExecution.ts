/**
 * Workflow execution state machine
 * 
 * Manages state transitions for workflow execution, preventing illegal operations
 */

import { reactive, readonly, computed } from 'vue'
import i18n from '@renderer/i18n'

export enum WorkflowState {
  IDLE = 'idle',           // Idle state
  RUNNING = 'running',     // Running
  PAUSED = 'paused',       // Paused
  COMPLETED = 'completed', // Completed
  FAILED = 'failed'        // Failed
}

export interface WorkflowExecution {
  state: WorkflowState
  runId: number | null
  workflowId: number | null
  error: string | null
}

/**
 * Workflow execution state machine
 */
export function useWorkflowExecution() {
  // Internal state
  const execution = reactive<WorkflowExecution>({
    state: WorkflowState.IDLE,
    runId: null,
    workflowId: null,
    error: null
  })

  // State transition rules
  const validTransitions: Record<WorkflowState, WorkflowState[]> = {
    [WorkflowState.IDLE]: [WorkflowState.RUNNING],
    [WorkflowState.RUNNING]: [WorkflowState.PAUSED, WorkflowState.COMPLETED, WorkflowState.FAILED],
    [WorkflowState.PAUSED]: [WorkflowState.RUNNING, WorkflowState.FAILED],
    [WorkflowState.COMPLETED]: [WorkflowState.IDLE, WorkflowState.RUNNING],  // Allow starting a new execution directly from the completed state
    [WorkflowState.FAILED]: [WorkflowState.IDLE, WorkflowState.RUNNING]      // Allow starting a new execution directly from the failed state
  }

  // Computed properties
  const isRunning = computed(() => execution.state === WorkflowState.RUNNING)
  const isPaused = computed(() => execution.state === WorkflowState.PAUSED)
  const isIdle = computed(() => execution.state === WorkflowState.IDLE)
  const isCompleted = computed(() => execution.state === WorkflowState.COMPLETED)
  const isFailed = computed(() => execution.state === WorkflowState.FAILED)
  const canPause = computed(() => execution.state === WorkflowState.RUNNING)
  const canResume = computed(() => execution.state === WorkflowState.PAUSED)
  const canStart = computed(() => 
    execution.state === WorkflowState.IDLE || 
    execution.state === WorkflowState.COMPLETED || 
    execution.state === WorkflowState.FAILED
  )

  /**
   * State transition
   * @param newState The new state
   * @throws Error If the state transition is illegal
   */
  function transitionTo(newState: WorkflowState) {
    const currentState = execution.state
    const allowedStates = validTransitions[currentState]

    if (!allowedStates.includes(newState)) {
      throw new Error(
        i18n.global.t('app.workflow.illegalStateTransition', {
          from: currentState,
          to: newState,
          allowed: allowedStates.join(', ')
        })
      )
    }

    console.log(`[WorkflowExecution] State transition: ${currentState} -> ${newState}`)
    execution.state = newState
  }

  /**
   * Start execution
   * @param workflowId Workflow ID
   * @param runId Run ID
   */
  function start(workflowId: number, runId: number) {
    // If currently in the completed or failed state, reset first before starting (auto-clear previous results)
    if (execution.state === WorkflowState.COMPLETED || execution.state === WorkflowState.FAILED) {
      console.log(`[WorkflowExecution] Restarting from ${execution.state} state, auto-clearing results`)
    }
    
    transitionTo(WorkflowState.RUNNING)
    execution.workflowId = workflowId
    execution.runId = runId
    execution.error = null
  }

  /**
   * Update the run ID (without changing state)
   * @param runId The new run ID
   */
  function updateRunId(runId: number) {
    console.log(`[WorkflowExecution] Update runId: ${execution.runId} -> ${runId}`)
    execution.runId = runId
  }

  /**
   * Pause execution
   */
  function pause() {
    transitionTo(WorkflowState.PAUSED)
  }

  /**
   * Resume execution
   */
  function resume() {
    transitionTo(WorkflowState.RUNNING)
  }

  /**
   * Complete execution
   */
  function complete() {
    transitionTo(WorkflowState.COMPLETED)
  }

  /**
   * Execution failed
   * @param error Error message
   */
  function fail(error: string) {
    transitionTo(WorkflowState.FAILED)
    execution.error = error
  }

  /**
   * Reset state
   */
  function reset() {
    transitionTo(WorkflowState.IDLE)
    execution.runId = null
    execution.workflowId = null
    execution.error = null
  }

  return {
    // Read-only state
    execution: readonly(execution),
    
    // Computed properties
    isRunning,
    isPaused,
    isIdle,
    isCompleted,
    isFailed,
    canPause,
    canResume,
    canStart,
    
    // State transition methods
    start,
    updateRunId,
    pause,
    resume,
    complete,
    fail,
    reset
  }
}
