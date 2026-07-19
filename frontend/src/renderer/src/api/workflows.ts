import request, { API_BASE_URL } from './request'
import type { components } from '@/types/generated'

// ============================================================
// Type definitions - all use auto-generated types
// ============================================================
// All types are auto-generated from the OpenAPI schema
// After backend changes, run `npm run gen:types` to sync
// ============================================================

export type WorkflowRead = components['schemas']['WorkflowRead']
export type WorkflowUpdate = components['schemas']['WorkflowUpdate']
export type WorkflowRunRead = components['schemas']['WorkflowRunRead']
export type NodeExecutionStatus = components['schemas']['NodeExecutionStatus']

export function listWorkflows(): Promise<WorkflowRead[]> {
  return request.get('/workflows', undefined, '/api', { showLoading: false })
}

export function getWorkflow(id: number): Promise<WorkflowRead> {
  return request.get(`/workflows/${id}`, undefined, '/api', { showLoading: false })
}

export function createWorkflow(payload: Partial<WorkflowRead> & { name: string; definition_json?: any }): Promise<WorkflowRead> {
  return request.post('/workflows', payload, '/api', { showLoading: false })
}

export function updateWorkflow(id: number, payload: WorkflowUpdate): Promise<WorkflowRead> {
  return request.put(`/workflows/${id}`, payload, '/api', { showLoading: false })
}

export function deleteWorkflow(id: number): Promise<void> {
  return request.delete(`/workflows/${id}`, undefined, '/api', { showLoading: false })
}

export function deleteRun(runId: number): Promise<{ ok: boolean; message: string }> {
  return request.delete(`/workflows/runs/${runId}`, undefined, '/api')
}

export interface ValidationError {
  line: number
  variable: string
  error_type: string
  message: string
  suggestion?: string
}

export interface ValidationResult {
  is_valid: boolean
  errors: ValidationError[]
  warnings: ValidationError[]
}

export function validateWorkflow(id: number): Promise<ValidationResult> {
  return request.post(`/workflows/${id}/validate`, {}, '/api', { showLoading: false })
}


export interface WorkflowNodePort {
  name: string
  type: string
  description: string
  required?: boolean
}

export interface WorkflowNodeType {
  type: string
  category: string
  label: string
  description: string
  inputs: WorkflowNodePort[]
  outputs: WorkflowNodePort[]
  config_schema: any
}

export function getNodeTypes(): Promise<{ node_types: WorkflowNodeType[] }> {
  return request.get('/nodes/types', undefined, '/api', { showLoading: false })
}



// ============================================================
// API functions
// ============================================================

// Get run details
export function getRun(runId: number): Promise<WorkflowRunRead> {
  return request.get(`/workflows/runs/${runId}`, undefined, '/api', { showLoading: false })
}

// Get all run records
export function listAllRuns(params?: { limit?: number; offset?: number; status?: string }): Promise<WorkflowRunRead[]> {
  return request.get('/runs', params, '/api', { showLoading: false })
}

// Cancel run
export function cancelRun(runId: number): Promise<{ ok: boolean; message?: string }> {
  return request.post(`/workflows/runs/${runId}/cancel`, {}, '/api')
}

// ============================================================
// Code-style workflow API
// ============================================================

export interface WorkflowStatement {
  variable: string
  code: string
}

export interface ProgressEvent {
  type: 'progress'
  statement: WorkflowStatement
  percent: number
  message: string
  stage?: string
}

export interface CompleteEvent {
  type: 'complete'
  statement: WorkflowStatement
  result: any
}

export interface ErrorEvent {
  type: 'error'
  statement: WorkflowStatement
  error: string
}

export interface StartEvent {
  type: 'start'
  statement: WorkflowStatement
}

export type WorkflowStreamEvent = StartEvent | ProgressEvent | CompleteEvent | ErrorEvent

export interface WorkflowStreamCallbacks {
  onRunStarted?: (runId: number) => void
  onStart?: (event: StartEvent) => void
  onProgress?: (event: ProgressEvent) => void
  onComplete?: (event: CompleteEvent) => void
  onError?: (event: ErrorEvent) => void
  onEnd?: () => void
}

/**
 * Execute a code-style workflow (streaming SSE push)
 * 
 * @param workflowId Workflow ID
 * @param callbacks Event callbacks
 * @param resume Whether to resume execution (default false)
 * @param runId The run ID when resuming (required when resume=true)
 * @returns An object containing runId and EventSource
 */
export async function runCodeWorkflowStream(
  workflowId: number,
  callbacks: WorkflowStreamCallbacks,
  resume: boolean = false,
  runId?: number
): Promise<{ runId: { value: number }; eventSource: EventSource }> {
  console.log('[API] Start executing workflow:', workflowId, 'resume:', resume, 'runId:', runId)
  
  // Build the URL
  let url = `${API_BASE_URL}/workflows/${workflowId}/execute-stream`
  if (resume && runId) {
    url += `?resume=true&run_id=${runId}`
  }
  
  console.log('[API] Connecting SSE:', url)

  // EventSource does not support AbortController; use close() directly to interrupt
  const eventSource = new EventSource(url)
  // Wrap runId in an object so it can be updated by external references
  const runIdRef = { value: runId || 0 }

  eventSource.onopen = () => {
    console.log('[API] SSE connection succeeded')
  }

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      console.log('[API] Received message:', data)
      
      // Handle different event types
      switch (data.type) {
        case 'run_started':
          // Save run_id
          runIdRef.value = data.run_id
          console.log('[API] Run started, run_id:', runIdRef.value)
          // Invoke the callback
          callbacks.onRunStarted?.(runIdRef.value)
          break
          
        case 'start':
          callbacks.onStart?.(data as StartEvent)
          break
          
        case 'progress':
          callbacks.onProgress?.(data as ProgressEvent)
          break
          
        case 'complete':
          callbacks.onComplete?.(data as CompleteEvent)
          break
          
        case 'error':
          callbacks.onError?.(data as ErrorEvent)
          break
          
        case 'paused':
          console.log('[API] Workflow paused')
          callbacks.onEnd?.()
          eventSource.close()
          break
          
        case 'end':
          callbacks.onEnd?.()
          eventSource.close()
          break
          
        default:
          console.warn('[API] Unknown event type:', data.type)
      }
    } catch (error) {
      console.error('[API] Failed to parse message:', error)
    }
  }

  eventSource.onerror = (error) => {
    console.error('[API] SSE error:', error)
    
    // Check readyState to determine whether it is a normal closure
    if (eventSource.readyState === EventSource.CLOSED) {
      console.log('[API] SSE connection closed (possibly paused or completed)')
      // Do not call onError to avoid false error reports
      return
    }
    
    // Close the connection immediately to prevent auto-reconnect
    eventSource.close()
    
    callbacks.onError?.({
      type: 'error',
      statement: { variable: 'unknown', code: 'unknown' },
      error: 'SSE connection error'
    })
    callbacks.onEnd?.()
  }

  return { runId: runIdRef, eventSource }
}

/**
 * Parse workflow code (validate syntax)
 * @param code Workflow code
 * @returns Parse result
 */
export async function parseWorkflowCode(code: string): Promise<{
  success: boolean
  statements?: WorkflowStatement[]
  errors?: string[]
}> {
  return request.post('/workflows/parse', { code }, '/api', { showLoading: false })
}

/**
 * Save a code-style workflow
 * @param name Workflow name
 * @param code Workflow code
 * @returns The saved workflow
 */
export async function saveCodeWorkflow(name: string, code: string): Promise<WorkflowRead> {
  return request.post('/workflows/code', { name, code }, '/api')
}

/**
 * Get a code-style workflow
 * @param id Workflow ID
 * @returns Workflow code
 */
export async function getCodeWorkflow(id: number): Promise<{ id: number; name: string; code: string; revision?: string; keep_run_history?: boolean }> {
  return request.get(`/workflows/${id}/code`, undefined, '/api', { showLoading: false })
}

// Get the list of project creation templates
export interface ProjectTemplate {
  workflow_id: number
  workflow_name: string
  template: string | null
  description?: string
}

export function getProjectTemplates(): Promise<{ templates: ProjectTemplate[] }> {
  return request.get('/workflows/project-templates', undefined, '/api', { showLoading: false })
}
