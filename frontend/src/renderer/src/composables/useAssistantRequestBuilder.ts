import type { Ref } from 'vue'

import type { AssistantPanelMessage } from '@renderer/types/assistantPanel'
import type { AssistantRef } from '@renderer/api/ai'

interface AssistantContextLite {
  active_card: {
    title: string
    card_id: number
    card_type: string
  } | null
}

interface AssistantStoreLite {
  projectStructure: any
  formatRecentOperations: () => string
  getContextForAssistant: () => AssistantContextLite
  injectedRefs: AssistantRef[]
}

interface AssistantPreferenceRefs {
  contextSummaryEnabled: Ref<boolean>
  contextSummaryThreshold: Ref<number | null>
  reactModeEnabled: Ref<boolean>
  assistantTemperature: Ref<number | null>
  assistantMaxTokens: Ref<number | null>
  assistantTimeout: Ref<number | null>
}

interface UseAssistantRequestBuilderOptions {
  messages: Ref<AssistantPanelMessage[]>
  assistantStore: AssistantStoreLite
  resolvedContext: Ref<string>
  effectiveSchema: Ref<any>
  preferences: AssistantPreferenceRefs
}

function pruneEmpty(val: any): any {
  if (val == null) return val
  if (typeof val === 'string') return val.trim() === '' ? undefined : val
  if (typeof val !== 'object') return val
  if (Array.isArray(val)) {
    return val.map(pruneEmpty).filter(item => item !== undefined)
  }
  const out: Record<string, any> = {}
  for (const [key, value] of Object.entries(val)) {
    const pruned = pruneEmpty(value)
    if (pruned === undefined) continue
    if (typeof pruned === 'object' && !Array.isArray(pruned) && Object.keys(pruned).length === 0) continue
    if (Array.isArray(pruned) && pruned.length === 0) continue
    out[key] = pruned
  }
  return out
}

function clipText(text: string, maxLen = 4000): string {
  if (!text) return ''
  return text.length > maxLen ? `${text.slice(0, maxLen)}\n/* ... */` : text
}

function serializeInjectedRef(ref: AssistantRef): string | null {
  if (ref.refType === 'card') {
    try {
      const cleaned = pruneEmpty(ref.content)
      const text = JSON.stringify(cleaned ?? {}, null, 2)
      return `### [Full Card Reference]${ref.projectName} / ${ref.cardTitle}\n\`\`\`json\n${clipText(text)}\n\`\`\``
    } catch {
      return null
    }
  }

  if (ref.refType === 'chapter_excerpt') {
    const header = `${ref.projectName} / ${ref.cardTitle} (${ref.fieldPath} lines ${ref.startLine}-${ref.endLine})`
    const body = ref.numberedText?.trim() || ref.text?.trim() || '(empty excerpt)'
    return `### [Text Excerpt]${header}\n\`\`\`text\n${clipText(body)}\n\`\`\`\n- snapshot_hash: ${ref.snapshotHash}\n- To modify this text, prefer replace_card_text_by_lines over replace_field_text`
  }

  const lines: string[] = []
  lines.push(`### [Review Result Card] Target: ${ref.targetTitle} (review_card_id=${ref.reviewCardId})`)
  lines.push(`- Review Type: ${ref.reviewType}`)
  if (ref.reviewProfile) lines.push(`- Review Profile: ${ref.reviewProfile}`)
  lines.push(`- Quality Gate: ${ref.qualityGate}`)
  if (ref.contentSnapshot) lines.push(`- content_snapshot: ${clipText(ref.contentSnapshot, 800)}`)
  lines.push('```text')
  lines.push(clipText(ref.resultText || '(empty review result)'))
  lines.push('```')
  return lines.join('\n')
}

export function useAssistantRequestBuilder(options: UseAssistantRequestBuilderOptions) {
  function buildConversationText() {
    return options.messages.value
      .map(message => {
        const prefix = message.role === 'user' ? 'User:' : 'Assistant:'
        let text = `${prefix} ${message.content}`
        if (message.tools && message.tools.length > 0) {
          text += '\n\n[Tool Call Log]'
          for (const tool of message.tools) {
            text += `\n- Tool: ${tool.tool_name}`
            if (tool.result) {
              text += `\n  Result: ${JSON.stringify(tool.result, null, 2)}`
            }
          }
        }
        return text
      })
      .join('\n\n')
  }

  function buildAssistantChatRequest() {
    const parts: string[] = []
    const projectStructure = options.assistantStore.projectStructure

    if (projectStructure) {
      parts.push(`# Project: ${projectStructure.project_name}`)
      parts.push(`Project ID: ${projectStructure.project_id} | Total Cards: ${projectStructure.total_cards}`)
      parts.push('')

      const stats = Object.entries(projectStructure.stats)
        .map(([type, count]) => `- ${type}: ${count} cards`)
        .join('\n')
      parts.push(`## 📊 Project Statistics\n${stats}`)
      parts.push('')

      parts.push(`## 🌲 Card Structure Tree\nROOT\n${projectStructure.tree_text}`)
      parts.push('')

      parts.push('## 🏷️ Available Card Types')
      parts.push(projectStructure.available_card_types.join(' | '))
      parts.push('')
    }

    const opsText = options.assistantStore.formatRecentOperations()
    if (opsText) {
      parts.push(`## 📝 Recent Operations\n${opsText}`)
      parts.push('')
    }

    const context = options.assistantStore.getContextForAssistant()
    if (context.active_card) {
      parts.push('## ⭐ Current Card')
      parts.push(`"${context.active_card.title}" (ID: ${context.active_card.card_id}, Type: ${context.active_card.card_type})`)

      if (options.effectiveSchema.value) {
        try {
          const schemaText = JSON.stringify(options.effectiveSchema.value, null, 2)
          parts.push('\n### Card Structure (JSON Schema)')
          parts.push('```json')
          parts.push(schemaText)
          parts.push('```')
        } catch {
          // ignore schema serialization error
        }
      }

      parts.push('')
    }

    if (options.assistantStore.injectedRefs.length) {
      const blocks: string[] = []
      for (const ref of options.assistantStore.injectedRefs) {
        const block = serializeInjectedRef(ref)
        if (block) blocks.push(block)
      }
      parts.push(`## 📎 Referenced Content\n${blocks.join('\n\n')}`)
      parts.push('')
    }

    if (options.resolvedContext.value) {
      parts.push(`## 🔗 Context References\n${options.resolvedContext.value}`)
      parts.push('')
    }

    parts.push('## 💬 Conversation History')
    parts.push(buildConversationText())

    const lastUserMessage = options.messages.value.filter(message => message.role === 'user').pop()
    const userPrompt = lastUserMessage?.content?.trim() || ''

    return {
      user_prompt: userPrompt,
      context_info: parts.join('\n'),
      context_summarization_enabled: options.preferences.contextSummaryEnabled.value || undefined,
      context_summarization_threshold: options.preferences.contextSummaryThreshold.value || undefined,
      react_mode_enabled: options.preferences.reactModeEnabled.value || undefined,
      temperature: options.preferences.assistantTemperature.value || undefined,
      max_tokens: options.preferences.assistantMaxTokens.value || undefined,
      timeout: options.preferences.assistantTimeout.value || undefined,
    }
  }

  return {
    buildConversationText,
    buildAssistantChatRequest,
  }
}
