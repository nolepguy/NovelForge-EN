/**
 * Type definitions related to instruction stream generation
 * 
 * Kept in sync with the backend Pydantic models
 */

// ==================== Instruction format definitions ====================

/**
 * Instruction operation type
 */
export type InstructionOp = 'set' | 'append' | 'done'

/**
 * Base instruction interface
 */
export interface InstructionBase {
  op: InstructionOp
}

/**
 * Set field value instruction
 */
export interface SetInstruction extends InstructionBase {
  op: 'set'
  path: string  // JSON Pointer format, e.g. /name or /config/theme
  value: any    // The value to set
}

/**
 * Append element to array instruction
 */
export interface AppendInstruction extends InstructionBase {
  op: 'append'
  path: string  // JSON Pointer format array path
  value: any    // The element to append
}

/**
 * Generate completion flag instruction
 */
export interface DoneInstruction extends InstructionBase {
  op: 'done'
}

/**
 * Instruction union type
 */
export type Instruction = SetInstruction | AppendInstruction | DoneInstruction

// ==================== Generation config ====================

/**
 * Card generation config
 */
export interface GenerationConfig {
  mode?: 'instruction_stream'
  prompt_template?: string
  field_hints?: Record<string, string>
  field_order?: string[]
  custom?: Record<string, any>
}

// ==================== API request/response models ====================

/**
 * Conversation message
 */
export interface ConversationMessage {
  role: 'system' | 'user' | 'assistant'
  content: string
}

/**
 * Instruction stream generation request
 */
export interface InstructionGenerateRequest {
  llm_config_id: number
  user_prompt?: string
  response_model_schema: Record<string, any>
  current_data?: Record<string, any>
  conversation_context?: ConversationMessage[]
  generation_config?: GenerationConfig
  prompt_template?: string
  context_info?: string
  temperature?: number
  max_tokens?: number
  timeout?: number
  deps?: string
}

// ==================== SSE event types ====================

/**
 * Thinking event (AI's natural language output)
 */
export interface ThinkingEvent {
  type: 'thinking'
  text: string
}

/**
 * Instruction event (validated instruction)
 */
export interface InstructionEvent {
  type: 'instruction'
  instruction: Instruction
}

/**
 * Warning event (non-fatal error)
 */
export interface WarningEvent {
  type: 'warning'
  text: string
}

/**
 * Error event (fatal error)
 */
export interface ErrorEvent {
  type: 'error'
  text: string
}

/**
 * Done event
 */
export interface DoneEvent {
  type: 'done'
  success?: boolean
  message?: string
}

/**
 * Stream event union type
 */
export type StreamEvent = ThinkingEvent | InstructionEvent | WarningEvent | ErrorEvent | DoneEvent

// ==================== Generation panel message types ====================

/**
 * Generation panel message type
 */
export type GenerationMessageType = 'thinking' | 'action' | 'system' | 'user' | 'warning' | 'error'

/**
 * Generation panel message
 */
export interface GenerationMessage {
  type: GenerationMessageType
  content: string
  timestamp: number
}
