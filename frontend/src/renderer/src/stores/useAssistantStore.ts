import { defineStore } from 'pinia'
import { ref, shallowRef } from 'vue'
import i18n from '@renderer/i18n'
import { getProjects, type ProjectRead } from '@renderer/api/projects'
import { getCardsForProject, type CardRead } from '@renderer/api/cards'
import type {
  AssistantRef,
  AssistantCardRef,
  AssistantRefSource,
  ChapterExcerptRef,
  ReviewResultRef,
} from '@renderer/api/ai'

export type InjectRef = AssistantRef
export type AssistantMessage = { role: 'user' | 'assistant'; content: string; ts?: number }

function getInjectedRefKey(ref: InjectRef): string {
  if (ref.refType === 'card') return `card:${ref.projectId}:${ref.cardId}`
  if (ref.refType === 'chapter_excerpt') {
    return `chapter_excerpt:${ref.projectId}:${ref.cardId}:${ref.fieldPath}:${ref.startLine}:${ref.endLine}:${ref.snapshotHash}`
  }
  return `review_result:${ref.projectId}:${ref.reviewCardId}`
}

function normalizeInjectedRef(ref: Partial<InjectRef> & Record<string, any>, source: AssistantRefSource): InjectRef | null {
  if (!ref) return null
  const refType = (ref.refType || 'card') as InjectRef['refType']

  if (refType === 'card') {
    if (!ref.projectId || !ref.cardId) return null
    return {
      refType: 'card',
      projectId: Number(ref.projectId),
      projectName: String(ref.projectName || ''),
      cardId: Number(ref.cardId),
      cardTitle: String(ref.cardTitle || ''),
      content: ref.content ?? {},
      source,
    }
  }

  if (refType === 'chapter_excerpt') {
    if (!ref.projectId || !ref.cardId || !ref.startLine || !ref.endLine || !ref.snapshotHash) return null
    return {
      refType: 'chapter_excerpt',
      projectId: Number(ref.projectId),
      projectName: String(ref.projectName || ''),
      cardId: Number(ref.cardId),
      cardTitle: String(ref.cardTitle || ''),
      fieldPath: String(ref.fieldPath || 'content'),
      startLine: Number(ref.startLine),
      endLine: Number(ref.endLine),
      text: String(ref.text || ''),
      numberedText: String(ref.numberedText || ''),
      snapshotHash: String(ref.snapshotHash),
      source,
    }
  }

  if (!ref.projectId || !ref.reviewCardId || !ref.targetId) return null
  return {
    refType: 'review_result',
    projectId: Number(ref.projectId),
    reviewCardId: Number(ref.reviewCardId),
    targetId: Number(ref.targetId),
    targetTitle: String(ref.targetTitle || ''),
    reviewType: String(ref.reviewType || 'card'),
    reviewProfile: ref.reviewProfile ?? null,
    qualityGate: String(ref.qualityGate || 'revise'),
    resultText: String(ref.resultText || ''),
    contentSnapshot: ref.contentSnapshot ?? null,
    source,
  }
}

// Card context info interface
export interface CardContextInfo {
  card_id: number
  title: string
  card_type: string
  parent_id: number | null
  project_id: number
  first_seen: number  // timestamp
  last_seen: number   // timestamp
  access_count: number
}

// User operation record interface
export interface UserOperation {
  timestamp: number
  type: 'create' | 'edit' | 'delete' | 'move'  // add 'move' type
  cardId: number
  cardTitle: string
  cardType: string
  detail?: string  // operation detail (e.g. hierarchy change, move position)
}

// Project structured context interface
export interface ProjectStructureContext {
  project_id: number
  project_name: string
  total_cards: number
  stats: Record<string, number>  // card type -> count
  tree_text: string              // tree text
  available_card_types: string[] // available card types
  last_updated: number           // last updated timestamp
  version: number                // data version (for cache invalidation)
}

// To avoid sharing local cache between dev/build, the conversation history key is prefixed with the environment
// dev -> 'development', build -> 'production'
const ENV_PREFIX = (import.meta as any)?.env?.MODE || 'production'
const HISTORY_KEY_PREFIX = `nf:${ENV_PREFIX}:assistant:history:`
const STRUCTURE_KEY_PREFIX = `nf:${ENV_PREFIX}:assistant:structure:`
const OPERATIONS_KEY_PREFIX = `nf:${ENV_PREFIX}:assistant:operations:`

function projectHistoryKey(projectId: number) { return `${HISTORY_KEY_PREFIX}${projectId}` }
function projectStructureKey(projectId: number) { return `${STRUCTURE_KEY_PREFIX}${projectId}` }
function projectOperationsKey(projectId: number) { return `${OPERATIONS_KEY_PREFIX}${projectId}` }

export const useAssistantStore = defineStore('assistant', () => {
  const projects = ref<ProjectRead[]>([])
  // Use shallowRef to avoid deep reactive wrapping of card content, improving performance
  const cardsByProject = shallowRef<Record<number, CardRead[]>>({})
  const injectedRefs = shallowRef<InjectRef[]>([])
  
  const activeCardContext = ref<CardContextInfo | null>(null)
  const cardRegistry = ref<Map<number, CardContextInfo>>(new Map())
  const projectCardTypes = ref<string[]>([])
  
  // Project structured context
  const projectStructure = ref<ProjectStructureContext | null>(null)

  // User operation history (max 3 entries)
  const recentOperations = ref<UserOperation[]>([])

  async function loadProjects() {
    projects.value = await getProjects()
  }

  async function loadCardsForProject(pid: number) {
    const list = await getCardsForProject(pid)
    // Create a new object to trigger the shallowRef update
    cardsByProject.value = { ...cardsByProject.value, [pid]: list }
    return list
  }

  function addInjectedRefs(pid: number, pname: string, ids: number[]) {
    const list = cardsByProject.value[pid] || []
    const map = new Map<number, CardRead>()
    list.forEach(c => map.set(c.id, c))
    
    // Create a new array to trigger the shallowRef update
    const newRefs = [...injectedRefs.value]

    for (const id of ids) {
      const c = map.get(id)
      if (!c) continue
      const nextRef: AssistantCardRef = {
        refType: 'card',
        projectId: pid,
        projectName: pname,
        cardId: id,
        cardTitle: c.title,
        content: (c as any).content,
        source: 'manual',
      }
      const key = getInjectedRefKey(nextRef)
      const existingIdx = newRefs.findIndex(r => getInjectedRefKey(r) === key)
      if (existingIdx >= 0) {
        // Upgrade to manual (if previously auto) and refresh the title/content
        const prev = newRefs[existingIdx]
        newRefs[existingIdx] = { ...prev, ...nextRef, source: 'manual' } as InjectRef
        continue
      }
      newRefs.push(nextRef)
    }
    
    injectedRefs.value = newRefs
  }

  function addInjectedRefDirect(ref: InjectRef | (Partial<InjectRef> & Record<string, any>), source: AssistantRefSource = 'manual') {
    const normalizedRef = normalizeInjectedRef(ref as any, source)
    if (!normalizedRef) return
    
    // Create a new array to trigger the shallowRef update
    const newRefs = [...injectedRefs.value]
    const key = getInjectedRefKey(normalizedRef)
    const idx = newRefs.findIndex(r => getInjectedRefKey(r) === key)
    const prev = idx >= 0 ? newRefs[idx] : null

    // Rule: manual is never overridden by auto; manual overrides auto; same source updates the content
    if (idx >= 0) {
      if (prev?.source === 'manual' && source === 'auto') {
        // Keep manual, do not downgrade, only update display info/content
        newRefs[idx] = { ...prev, ...normalizedRef, source: 'manual' } as InjectRef
      } else {
        newRefs[idx] = { ...prev, ...normalizedRef, source } as InjectRef
      }
    } else {
      newRefs.push(normalizedRef)
    }
    
    injectedRefs.value = newRefs
  }

  function clearAutoRefs() {
    injectedRefs.value = injectedRefs.value.filter(r => r.source !== 'auto')
  }

  function addAutoRef(ref: InjectRef) {
    // Only clears other auto refs; if the same card was marked manual, it will not be overridden
    clearAutoRefs()
    addInjectedRefDirect(ref, 'auto')
  }

  function addChapterExcerptRef(ref: ChapterExcerptRef, source: AssistantRefSource = 'manual') {
    addInjectedRefDirect(ref, source)
  }

  function addReviewResultRef(ref: ReviewResultRef, source: AssistantRefSource = 'manual') {
    addInjectedRefDirect(ref, source)
  }

  function removeInjectedRefAt(index: number) {
    // Create a new array to trigger the shallowRef update
    injectedRefs.value = injectedRefs.value.filter((_, i) => i !== index)
  }
  function clearInjectedRefs() { injectedRefs.value = [] }

  // --- Conversation history (persisted to localStorage per project) ---
  function getHistory(projectId: number): AssistantMessage[] {
    try {
      const raw = localStorage.getItem(projectHistoryKey(projectId))
      if (!raw) return []
      const arr = JSON.parse(raw)
      if (!Array.isArray(arr)) return []
      return arr as AssistantMessage[]
    } catch { return [] }
  }

  function setHistory(projectId: number, history: AssistantMessage[]) {
    try {
      localStorage.setItem(projectHistoryKey(projectId), JSON.stringify(history || []))
    } catch {}
  }

  function appendHistory(projectId: number, msg: AssistantMessage) {
    const hist = getHistory(projectId)
    hist.push({ ...msg, ts: msg.ts ?? Date.now() })
    setHistory(projectId, hist)
  }

  function clearHistory(projectId: number) {
    try { localStorage.removeItem(projectHistoryKey(projectId)) } catch {}
  }
  
  // Card context management methods
  function updateActiveCard(card: CardRead | null, projectId: number) {
    if (!card) {
      activeCardContext.value = null
      console.log('📋 [AssistantStore] Cleared active card')
      return
    }

    const now = Date.now()
    const info: CardContextInfo = {
      card_id: card.id,
      title: card.title,
      card_type: (card as any).card_type?.name || 'Unknown',  // fix: use card_type.name
      parent_id: (card as any).parent_id || null,
      project_id: projectId,
      first_seen: now,
      last_seen: now,
      access_count: 1
    }

    console.log('📋 [AssistantStore] Updated active card:', info)

    // Update the active card
    activeCardContext.value = info

    // Register into the card registry (update access info if it already exists)
    registerCard(info)
  }

  function registerCard(info: CardContextInfo) {
    const existing = cardRegistry.value.get(info.card_id)
    if (existing) {
      // Update the existing card info
      cardRegistry.value.set(info.card_id, {
        ...existing,
        title: info.title,  // update the title (may have changed)
        card_type: info.card_type,
        last_seen: Date.now(),
        access_count: existing.access_count + 1
      })
    } else {
      // New card
      cardRegistry.value.set(info.card_id, info)
    }
  }
  
  function updateProjectCardTypes(types: string[]) {
    projectCardTypes.value = types
  }
  
  function getContextForAssistant(): {
    active_card: CardContextInfo | null
    recent_cards: CardContextInfo[]
    card_types: string[]
  } {
    // Get recently accessed cards (max 10, sorted by last_seen)
    const recent = Array.from(cardRegistry.value.values())
      .sort((a, b) => b.last_seen - a.last_seen)
      .slice(0, 10)
    
    return {
      active_card: activeCardContext.value,
      recent_cards: recent,
      card_types: projectCardTypes.value
    }
  }
  
  function clearCardContext() {
    activeCardContext.value = null
    cardRegistry.value.clear()
    projectCardTypes.value = []
  }
  
  //  ========== Project structured context management ==========

  /**
   * Load the project structure cache from localStorage
   */
  function loadProjectStructureFromCache(projectId: number): ProjectStructureContext | null {
    try {
      const raw = localStorage.getItem(projectStructureKey(projectId))
      if (!raw) return null
      const data = JSON.parse(raw)
      return data as ProjectStructureContext
    } catch {
      return null
    }
  }
  
  /**
   * Save project structure to localStorage
   */
  function saveProjectStructureToCache(structure: ProjectStructureContext) {
    try {
      localStorage.setItem(projectStructureKey(structure.project_id), JSON.stringify(structure))
    } catch (e) {
      console.warn('Failed to save project structure cache', e)
    }
  }

  /**
   * Build the card tree text (recursive)
   */
  function buildCardTreeText(cards: CardRead[], parentId: number | null = null, depth: number = 0, currentCardId?: number): string {
    const indent = depth === 0 ? '' : '│  '.repeat(depth - 1) + '├─ '
    const children = cards.filter(c => (c as any).parent_id === parentId)
      .sort((a, b) => ((a as any).display_order || 0) - ((b as any).display_order || 0))
    
    const lines: string[] = []
    
    for (let i = 0; i < children.length; i++) {
      const card = children[i]
      const typeName = (card as any).card_type?.name || 'Unknown'
      const updatedAt = (card as any).updated_at
      const updatedDate = updatedAt ? new Date(updatedAt).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }) : ''
      const isCurrent = currentCardId && card.id === currentCardId
      const marker = isCurrent ? ' ⭐ Current' : ''
      
      lines.push(`${indent}[${typeName}] ${card.title} {id:${card.id} | Updated:${updatedDate}${marker}}`)

      // Recursively process child cards
      const childText = buildCardTreeText(cards, card.id, depth + 1, currentCardId)
      if (childText) {
        lines.push(childText)
      }
    }
    
    return lines.join('\n')
  }
  
  /**
   * Build the project structured context from card data
   * @param projectId project ID
   * @param projectName project name
   * @param cards all card data (from useCardStore)
   * @param cardTypes all card types (from useCardStore)
   * @param currentCardId the currently active card ID (optional)
   */
  function buildProjectStructure(
    projectId: number,
    projectName: string,
    cards: CardRead[],
    cardTypes: any[],
    currentCardId?: number
  ): ProjectStructureContext {
    // Count cards per type
    const stats: Record<string, number> = {}
    for (const card of cards) {
      const typeName = (card as any).card_type?.name || i18n.global.t('app.assistant.uncategorized')
      stats[typeName] = (stats[typeName] || 0) + 1
    }

    // Build the tree text
    const treeText = buildCardTreeText(cards, null, 0, currentCardId)

    // Available card types
    const availableTypes = cardTypes.map(ct => ct.name)
    
    return {
      project_id: projectId,
      project_name: projectName,
      total_cards: cards.length,
      stats,
      tree_text: treeText || 'ROOT\n(no cards yet)',
      available_card_types: availableTypes,
      last_updated: Date.now(),
      version: cards.length  // simply use card count as the version number
    }
  }

  /**
   * Update the project structure (auto build + cache)
   * @param projectId project ID
   * @param projectName project name
   * @param cards all card data
   * @param cardTypes all card types
   * @param currentCardId current card ID
   * @param forceRebuild whether to force a rebuild (ignore cache)
   */
  function updateProjectStructure(
    projectId: number,
    projectName: string,
    cards: CardRead[],
    cardTypes: any[],
    currentCardId?: number,
    forceRebuild: boolean = false
  ) {
    // Check whether the cache is valid
    if (!forceRebuild) {
      const cached = loadProjectStructureFromCache(projectId)
      if (cached && cached.version === cards.length) {
        // Cache is valid, use it directly (but update the current card marker)
        const updated = buildProjectStructure(projectId, projectName, cards, cardTypes, currentCardId)
        projectStructure.value = updated
        saveProjectStructureToCache(updated)
        console.log('📋 [AssistantStore] Using cached project structure (current card updated)')
        return
      }
    }

    // Rebuild
    const structure = buildProjectStructure(projectId, projectName, cards, cardTypes, currentCardId)
    projectStructure.value = structure
    saveProjectStructureToCache(structure)
    console.log('📋 [AssistantStore] Built project structure:', structure)
  }

  /**
   * Clear the project structure cache
   */
  function clearProjectStructure() {
    projectStructure.value = null
  }
  
  // ========== User operation history management ==========

  /**
   * Load operation history from localStorage
   */
  function loadOperationsFromCache(projectId: number): UserOperation[] {
    try {
      const raw = localStorage.getItem(projectOperationsKey(projectId))
      if (!raw) return []
      const arr = JSON.parse(raw)
      if (!Array.isArray(arr)) return []
      return arr as UserOperation[]
    } catch {
      return []
    }
  }
  
  /**
   * Save operation history to localStorage
   */
  function saveOperationsToCache(projectId: number, operations: UserOperation[]) {
    try {
      localStorage.setItem(projectOperationsKey(projectId), JSON.stringify(operations))
    } catch (e) {
      console.warn('Failed to save operation history', e)
    }
  }

  /**
   * Record a user operation
   */
  function recordOperation(projectId: number, op: Omit<UserOperation, 'timestamp'>) {
    const operation: UserOperation = {
      ...op,
      timestamp: Date.now()
    }

    // Add to memory
    recentOperations.value.unshift(operation)

    // Keep at most 3 entries
    if (recentOperations.value.length > 3) {
      recentOperations.value = recentOperations.value.slice(0, 3)
    }

    // Save to cache
    saveOperationsToCache(projectId, recentOperations.value)

    console.log('📝 [AssistantStore] Recorded operation:', operation)
  }

  /**
   * Load operation history
   */
  function loadOperations(projectId: number) {
    recentOperations.value = loadOperationsFromCache(projectId)
  }

  /**
   * Format operation history as text
   */
  function formatRecentOperations(): string {
    if (recentOperations.value.length === 0) return ''
    
    const lines = recentOperations.value.map((op, idx) => {
      const time = new Date(op.timestamp).toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      })
      const emoji = op.type === 'create' ? '➕' : 
                    op.type === 'edit' ? '✏️' : 
                    op.type === 'move' ? '📦' : 
                    '🗑️'
      const action = op.type === 'create' ? 'Create' :
                     op.type === 'edit' ? 'Edit' :
                     op.type === 'move' ? 'Move' :
                     'Delete'
      
      let line = `${idx + 1}. [${time}] ${emoji} ${action} "${op.cardTitle}" (${op.cardType} #${op.cardId})`

      // If there is detail info, add it to the next line
      if (op.detail) {
        line += `\n   Detail: ${op.detail}`
      }
      
      return line
    })
    
    return lines.join('\n')
  }
  
  /**
   * Clear operation history
   */
  function clearOperations(projectId: number) {
    recentOperations.value = []
    try {
      localStorage.removeItem(projectOperationsKey(projectId))
    } catch {}
  }

  return { 
    projects, cardsByProject, injectedRefs, 
    loadProjects, loadCardsForProject, 
    addInjectedRefs, addInjectedRefDirect, addAutoRef, addChapterExcerptRef, addReviewResultRef, clearAutoRefs, removeInjectedRefAt, clearInjectedRefs, 
    getHistory, setHistory, appendHistory, clearHistory,
    // Card context methods
    updateActiveCard, registerCard, updateProjectCardTypes, getContextForAssistant, clearCardContext,
    activeCardContext, cardRegistry, projectCardTypes,
    // Project structured context methods
    projectStructure,
    updateProjectStructure,
    clearProjectStructure,
    //  Operation history methods
    recentOperations,
    recordOperation,
    loadOperations,
    formatRecentOperations,
    clearOperations
  }
}) 
