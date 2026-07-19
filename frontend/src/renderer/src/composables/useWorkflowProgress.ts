/**
 * Workflow progress management Composable
 *
 * Unified management of workflow execution progress, shared by the execution view and status bar.
 * Note: SSE connection management has been moved into WorkflowStatusStore to ensure
 * the connection persists when switching views.
 */

import { useWorkflowStore } from '@/stores/useWorkflowStore'
import type { WorkflowStreamCallbacks } from '@/api/workflows'

export function useWorkflowProgress() {
  const workflowStore = useWorkflowStore()

  /**
   * Start workflow execution (global SSE connection management)
   */
  async function startWorkflow(
    workflowId: number,
    workflowName: string,
    callbacks: WorkflowStreamCallbacks,
    resume: boolean = false,
    runId?: number
  ) {
    return await workflowStore.startWorkflowExecution(
      workflowId,
      workflowName,
      callbacks,
      resume,
      runId
    )
  }

  /**
   * Pause workflow execution
   */
  function pauseWorkflow(runId: number) {
    workflowStore.pauseWorkflowExecution(runId)
  }

  /**
   * Get the SSE connection
   */
  function getConnection(runId: number) {
    return workflowStore.getSSEConnection(runId)
  }

  return {
    startWorkflow,
    pauseWorkflow,
    getConnection
  }
}
