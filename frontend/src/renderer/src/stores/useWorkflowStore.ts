import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { 
    getRun, 
    runCodeWorkflowStream, 
    getNodeTypes,
    type WorkflowStreamCallbacks,
    type WorkflowNodeType 
} from '@/api/workflows'

import i18n from '@renderer/i18n'

// Simple run info interface for status bar display
export interface RunInfo {
    id: number
    workflow_id: number
    workflow_name?: string
    status: string
    created_at?: string
    error?: string // error message extracted from error_json
    current_node?: string // currently executing node
    progress?: number // execution progress (0-100)
}

// SSE connection management
interface SSEConnection {
    runId: number
    workflowId: number
    workflowName: string
    eventSource: EventSource
    callbacks: WorkflowStreamCallbacks
}

/**
 * Unified workflow store
 * Manages:
 * 1. Metadata such as node types, card types
 * 2. Workflow run state and SSE connections
 */
export const useWorkflowStore = defineStore('workflow', () => {
    // ==================== Metadata management ====================
    const nodeTypes = ref<WorkflowNodeType[]>([])
    const cardTypes = ref<any[]>([])
    const isLoadingNodeTypes = ref(false)

    // Getters
    const categories = computed(() => {
        const cats = new Set(nodeTypes.value.map(n => n.category))
        return Array.from(cats)
    })

    const getNodesByCategory = (category: string) => {
        return nodeTypes.value.filter(n => n.category === category)
    }

    const getNodeType = (type: string) => {
        return nodeTypes.value.find(n => n.type === type)
    }

    // Actions
    async function fetchNodeTypes() {
        if (isLoadingNodeTypes.value) return

        try {
            isLoadingNodeTypes.value = true
            const res = await getNodeTypes()
            nodeTypes.value = res.node_types
        } catch (error) {
            console.error('Failed to fetch node types:', error)
        } finally {
            isLoadingNodeTypes.value = false
        }
    }

    async function fetchCardTypes() {
        if (cardTypes.value.length > 0) return // cache
        try {
            const { getCardTypes } = await import('../api/cards')
            cardTypes.value = await getCardTypes()
        } catch (error) {
            console.error('Failed to fetch card types:', error)
        }
    }

    // ==================== Run state management ====================
    const runs = ref<Map<number, RunInfo>>(new Map())
    const pollingTimer = ref<any>(null)
    const sseConnections = ref<Map<number, SSEConnection>>(new Map()) // manages all SSE connections

    // Getters
    const activeRuns = computed(() => {
        return Array.from(runs.value.values()).filter(r =>
            ['pending', 'running', 'paused'].includes(r.status)
        ).sort((a, b) => b.id - a.id)
    })

    const completedRuns = computed(() => {
        return Array.from(runs.value.values()).filter(r =>
            ['succeeded', 'failed', 'cancelled', 'timeout'].includes(r.status)
        ).sort((a, b) => b.id - a.id)
    })

    const totalRunCount = computed(() => runs.value.size)
    const activeRunCount = computed(() => activeRuns.value.length)

    // Actions
    function addRun(id: number, workflowName?: string) {
        if (runs.value.has(id)) return

        // Initialize placeholder
        runs.value.set(id, {
            id,
            workflow_id: 0,
            status: 'running',
            workflow_name: workflowName || i18n.global.t('app.workflow.loadingName'),
            progress: 0
        })

        // Fetch details immediately once
        fetchRunDetails(id)

        // Ensure polling is started
        startPolling()
    }

    function updateRunProgress(id: number, progress: number, currentNode?: string) {
        const run = runs.value.get(id)
        if (run) {
            runs.value.set(id, {
                ...run,
                progress,
                current_node: currentNode
            })
        }
    }

    function updateRunStatus(id: number, status: string, error?: string) {
        const run = runs.value.get(id)
        if (run) {
            runs.value.set(id, {
                ...run,
                status,
                error
            })
        }
    }

    async function fetchRunDetails(id: number) {
        try {
            const run = await getRun(id)
            if (run) {
                const existingRun = runs.value.get(id)
                
                // Extract error message from error_json
                let errorMessage: string | undefined
                if (run.error_json) {
                    errorMessage = typeof run.error_json === 'object' 
                        ? JSON.stringify(run.error_json) 
                        : String(run.error_json)
                }
                
                runs.value.set(id, {
                    id: run.id,
                    workflow_id: run.workflow_id,
                    workflow_name: run.workflow?.name || i18n.global.t('app.workflow.unnamed'),
                    status: run.status,
                    created_at: run.created_at || undefined,
                    error: errorMessage,
                    current_node: existingRun?.current_node, // preserve current node info
                    progress: existingRun?.progress // preserve progress info
                })
            }
        } catch (e) {
            console.error(`Failed to fetch run ${id}`, e)
        }
    }

    function startPolling() {
        if (pollingTimer.value) return

        // Run a check immediately once
        checkActiveRuns()

        pollingTimer.value = setInterval(() => {
            checkActiveRuns()
        }, 2000) // poll every 2 seconds
    }

    function stopPolling() {
        if (pollingTimer.value) {
            clearInterval(pollingTimer.value)
            pollingTimer.value = null
        }
    }

    /**
     * Listen for workflows triggered by the backend (notified via response headers)
     */
    function setupWorkflowListener() {
        const handleWorkflowStarted = (event: CustomEvent) => {
            const runIds = event.detail as number[]
            
            // Add all newly started runs to the state
            runIds.forEach(runId => {
                if (!runs.value.has(runId)) {
                    addRun(runId, i18n.global.t('app.workflow.triggerWorkflow'))
                }
            })
        }
        
        window.addEventListener('workflow-started', handleWorkflowStarted as EventListener)
        
        // Return cleanup function
        return () => {
            window.removeEventListener('workflow-started', handleWorkflowStarted as EventListener)
        }
    }

    async function checkActiveRuns() {
        if (activeRuns.value.length === 0) {
            stopPolling()
            return
        }

        // Update the status of all active runs
        for (const run of activeRuns.value) {
            await fetchRunDetails(run.id)
        }
    }

    // Clean up completed runs (optional, to avoid excessive memory usage)
    function clearCompleted() {
        const completedIds = completedRuns.value.map(r => r.id)
        completedIds.forEach(id => {
            runs.value.delete(id)
            // Also clean up the corresponding SSE connection
            const conn = sseConnections.value.get(id)
            if (conn) {
                conn.eventSource.close()
                sseConnections.value.delete(id)
            }
        })
    }

    /**
     * Start workflow execution (global SSE connection management)
     * @param workflowId workflow ID
     * @param workflowName workflow name
     * @param callbacks callbacks (for updating the UI)
     * @param resume whether to resume execution
     * @param runId the run ID when resuming execution
     */
    async function startWorkflowExecution(
        workflowId: number,
        workflowName: string,
        callbacks: WorkflowStreamCallbacks,
        resume: boolean = false,
        runId?: number
    ) {
        let currentRunId: number | null = runId || null
        let totalNodes = 0
        let completedNodes = 0

        // If resuming execution, ensure the run record exists and status is correct
        if (resume && runId) {
            const existingRun = runs.value.get(runId)
            if (existingRun) {
                // Update status to running
                updateRunStatus(runId, 'running')
                console.log('[WorkflowStore] Resuming execution, updated status to running:', runId)
            } else {
                // If it doesn't exist, add it to the status bar
                addRun(runId, workflowName)
                console.log('[WorkflowStore] Resuming execution, added run record:', runId)
            }
        }

        // Wrap callbacks to automatically update the status bar
        const wrappedCallbacks: WorkflowStreamCallbacks = {
            onRunStarted: (actualRunId: number) => {
                currentRunId = actualRunId
                // Add to status bar (new execution only)
                if (!resume) {
                    addRun(actualRunId, workflowName)
                }
                // Call original callback
                if (callbacks.onRunStarted) {
                    callbacks.onRunStarted(actualRunId)
                }
            },

            onStart: (event) => {
                totalNodes++
                // Update status bar: current node
                if (currentRunId) {
                    const progress = totalNodes > 0 ? (completedNodes / totalNodes) * 100 : 0
                    updateRunProgress(currentRunId, progress, event.statement?.variable)
                }
                // Call original callback
                if (callbacks.onStart) {
                    callbacks.onStart(event)
                }
            },

            onProgress: (event) => {
                // Update status bar: progress
                if (currentRunId) {
                    const nodeProgress = event.percent || 0
                    const overallProgress = totalNodes > 0 
                        ? ((completedNodes + nodeProgress / 100) / totalNodes) * 100 
                        : nodeProgress
                    updateRunProgress(currentRunId, overallProgress, event.statement?.variable)
                }
                // Call original callback
                if (callbacks.onProgress) {
                    callbacks.onProgress(event)
                }
            },

            onComplete: (event) => {
                completedNodes++
                // Update status bar: a node is completed
                if (currentRunId) {
                    const progress = totalNodes > 0 ? (completedNodes / totalNodes) * 100 : 100
                    updateRunProgress(currentRunId, progress, event.statement?.variable)
                }
                // Call original callback
                if (callbacks.onComplete) {
                    callbacks.onComplete(event)
                }
            },

            onError: (event) => {
                // Update status
                if (currentRunId) {
                    updateRunStatus(currentRunId, 'failed', event.error)
                }
                // Call original callback
                if (callbacks.onError) {
                    callbacks.onError(event)
                }
            },

            onEnd: () => {
                // Workflow ended, final status update
                if (currentRunId) {
                    updateRunProgress(currentRunId, 100, undefined)
                    // Update status to succeeded (if not failed)
                    const run = runs.value.get(currentRunId)
                    if (run && run.status !== 'failed') {
                        updateRunStatus(currentRunId, 'succeeded')
                    }
                    // Clean up SSE connection
                    const conn = sseConnections.value.get(currentRunId)
                    if (conn) {
                        conn.eventSource.close()
                        sseConnections.value.delete(currentRunId)
                    }
                }
                // Call original callback
                if (callbacks.onEnd) {
                    callbacks.onEnd()
                }
            }
        }

        try {
            // If resuming execution, clean up the old SSE connection first
            if (resume && runId) {
                const oldConn = sseConnections.value.get(runId)
                if (oldConn) {
                    console.log('[WorkflowStore] Cleaning up old SSE connection:', runId)
                    oldConn.eventSource.close()
                    sseConnections.value.delete(runId)
                }
            }
            
            // Start SSE connection
            const { runId: actualRunId, eventSource } = await runCodeWorkflowStream(
                workflowId,
                wrappedCallbacks,
                resume,
                runId
            )

            // Save connection info
            if (currentRunId) {
                console.log('[WorkflowStore] Saving SSE connection:', currentRunId)
                sseConnections.value.set(currentRunId, {
                    runId: currentRunId,
                    workflowId,
                    workflowName,
                    eventSource,
                    callbacks: wrappedCallbacks
                })
            }

            return { runId: actualRunId, eventSource }
        } catch (error) {
            console.error('[WorkflowStore] Failed to start workflow:', error)
            throw error
        }
    }

    /**
     * Pause workflow execution
     */
    function pauseWorkflowExecution(runId: number) {
        console.log('[WorkflowStore] Pausing workflow execution:', runId)
        const conn = sseConnections.value.get(runId)
        if (conn) {
            console.log('[WorkflowStore] Closing SSE connection:', runId)
            conn.eventSource.close()
            sseConnections.value.delete(runId)
            updateRunStatus(runId, 'paused')
        } else {
            console.warn('[WorkflowStore] SSE connection not found:', runId)
        }
    }

    /**
     * Get SSE connection
     */
    function getSSEConnection(runId: number) {
        return sseConnections.value.get(runId)
    }

    return {
        // Metadata
        nodeTypes,
        cardTypes,
        isLoadingNodeTypes,
        categories,
        getNodesByCategory,
        getNodeType,
        fetchNodeTypes,
        fetchCardTypes,
        
        // Run state
        runs,
        activeRuns,
        completedRuns,
        activeRunCount,
        totalRunCount,
        addRun,
        updateRunProgress,
        updateRunStatus,
        clearCompleted,
        startWorkflowExecution,
        pauseWorkflowExecution,
        getSSEConnection,
        
        // Workflow listener
        setupWorkflowListener
    }
})