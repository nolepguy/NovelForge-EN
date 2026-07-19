import { API_BASE_URL } from './request'

import type {
  InstructionGenerateRequest,
  StreamEvent,
  Instruction
} from '@renderer/types/instruction'
import i18n from '@renderer/i18n'

/**
 * Generation parameters
 */
export interface GenerateParams extends InstructionGenerateRequest {
  // Inherits all request parameters
}

/**
 * Event callback function types
 */
export interface GenerateCallbacks {
  onThinking?: (text: string) => void
  onInstruction?: (instruction: Instruction) => void
  onWarning?: (text: string) => void
  onError?: (text: string) => void
  onDone?: (success: boolean, message?: string, finalData?: any) => void
}

/**
 * Generate using the instruction stream
 *
 * @param params Generation parameters
 * @param callbacks Event callbacks
 * @param signal Abort signal (optional)
 */
export async function generateWithInstructionStream(
  params: GenerateParams,
  callbacks: GenerateCallbacks,
  signal?: AbortSignal
): Promise<void> {
  const url = `${API_BASE_URL}/ai/generate/stream`

  try {
    // Send a POST request
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(params),
      signal
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`HTTP ${response.status}: ${errorText}`)
    }

    if (!response.body) {
      throw new Error(i18n.global.t('app.generation.emptyResponse'))
    }

    // Read the SSE stream
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()

      if (done) {
        break
      }

      // Decode the chunk
      buffer += decoder.decode(value, { stream: true })

      // Split by line
      const lines = buffer.split('\n')
      buffer = lines.pop() || '' // Keep incomplete lines

      for (const line of lines) {
        if (!line.trim()) {
          continue
        }

        // Parse the SSE format
        const event = parseSSELine(line)
        if (event) {
          handleEvent(event, callbacks)
        }
      }
    }

    // Process the remaining buffer
    if (buffer.trim()) {
      const event = parseSSELine(buffer)
      if (event) {
        handleEvent(event, callbacks)
      }
    }
  } catch (error: any) {
    if (error.name === 'AbortError') {
      console.log('Generation aborted')
      return
    }

    console.error('Generation failed:', error)
    callbacks.onError?.(error.message || i18n.global.t('app.generation.failed'))
  }
}

/**
 * Parse an SSE line
 * @param line A line in SSE format
 * @returns The parsed event object
 */
function parseSSELine(line: string): { event: string; data: any } | null {
  // SSE format: event: xxx\ndata: {...}
  // Or simplified format: data: {...}

  let eventType = 'message'
  let dataStr = ''

  const lines = line.split('\n')
  for (const l of lines) {
    if (l.startsWith('event:')) {
      eventType = l.slice(6).trim()
    } else if (l.startsWith('data:')) {
      dataStr = l.slice(5).trim()
    }
  }

  if (!dataStr) {
    return null
  }

  try {
    const data = JSON.parse(dataStr)
    return { event: eventType, data }
  } catch (e) {
    console.warn('Failed to parse SSE data:', dataStr)
    return null
  }
}

/**
 * Handle an event
 * @param event The event object
 * @param callbacks The callback functions
 */
function handleEvent(event: { event: string; data: any }, callbacks: GenerateCallbacks): void {
  const { data } = event
  const type = data.type || event.event

  switch (type) {
    case 'thinking':
      callbacks.onThinking?.(data.text)
      break

    case 'instruction':
      callbacks.onInstruction?.(data.instruction)
      break

    case 'warning':
      callbacks.onWarning?.(data.text)
      break

    case 'error':
      callbacks.onError?.(data.text)
      break

    case 'done':
      callbacks.onDone?.(data.success !== false, data.message, data.final_data)
      break

    default:
      console.warn('Unknown event type:', type, data)
  }
}
