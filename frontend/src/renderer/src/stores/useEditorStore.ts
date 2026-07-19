import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'

export interface ChapterSelectionRange {
  text: string
  from: number
  to: number
  startLine?: number
  endLine?: number
  numberedText?: string
  snapshotHash?: string
}

// Backward compatibility: objects without an explicit mode are still treated as text replacement.
export type ChapterReplaceTextOp = {
  mode?: 'text'
  from: string
  to: string
}

export interface ChapterReplaceLineRangeOp {
  mode: 'line_range'
  cardId: number
  fieldPath: string
  startLine: number
  endLine: number
  newText: string
  snapshotHash?: string
}

export type ChapterReplaceOp = ChapterReplaceTextOp | ChapterReplaceLineRangeOp

export interface ChapterExtractRunOptions {
  llm_config_id?: number
  temperature?: number
  max_tokens?: number
  timeout?: number
}

export const useEditorStore = defineStore('editor', () => {
  // Currently active editor
  const activeEditor = ref<{ type: string; id: string; data?: any } | null>(null)

  // Sidebar widths
  const leftSidebarWidth = ref(250)
  const rightSidebarWidth = ref(300)

  // Sidebar width limits
  const minLeftWidth = 180
  const maxLeftWidth = 400
  const minRightWidth = 220
  const maxRightWidth = 500
  
  // Navigation tree expansion state
  const expandedKeys = ref<string[]>(['content-root'])

  // Context menu state
  const contextMenu = reactive({
    visible: false,
    x: 0,
    y: 0,
    items: [] as { label: string; action: () => void }[],
    nodeData: null as any | null
  })
  
  // AI config dialog state
  const aiConfigDialog = reactive({
    visible: false,
    task: '',
    input: {} as any
  })
  
  // Drag-resize state
  const resizing = ref<'left' | 'right' | null>(null)
  let startX = 0
  let startWidth = 0

  // Editor cross-component revision interface (registered by NovelEditor)
  const applyChapterReplacements = ref<null | ((pairs: ChapterReplaceOp[]) => Promise<void> | void)>(null)
  const persistActiveChapterDraftRef = ref<null | (() => Promise<boolean>)>(null)

  // Callback to cross-component trigger "extract dynamic info"
  const triggerExtractDynamicInfoRef = ref<null | ((opts: ChapterExtractRunOptions) => Promise<void>)>(null)
  // Callback to cross-component trigger "extract relations into graph"
  const triggerExtractRelationsRef = ref<null | ((opts: ChapterExtractRunOptions) => Promise<void>)>(null)
  // Callback to cross-component trigger "extract item state"
  const triggerExtractItemStateRef = ref<null | ((opts: ChapterExtractRunOptions) => Promise<void>)>(null)
  // Callback to cross-component trigger "extract concept mastery"
  const triggerExtractConceptStateRef = ref<null | ((opts: ChapterExtractRunOptions) => Promise<void>)>(null)
  const triggerExtractSceneStateRef = ref<null | ((opts: ChapterExtractRunOptions) => Promise<void>)>(null)
  const triggerExtractOrganizationStateRef = ref<null | ((opts: ChapterExtractRunOptions) => Promise<void>)>(null)

  // Writing context sharing: volume/chapter number/title (for other panels to use)
  const currentVolumeNumber = ref<number | null>(null)
  const currentChapterNumber = ref<number | null>(null)
  const currentChapterTitle = ref<string>('')

  // Actions
  function setActiveEditor(editor: { type: string; id: string; data?: any } | null) {
    activeEditor.value = editor
  }

  function setLeftSidebarWidth(width: number) {
    leftSidebarWidth.value = Math.max(minLeftWidth, Math.min(maxLeftWidth, width))
  }

  function setRightSidebarWidth(width: number) {
    rightSidebarWidth.value = Math.max(minRightWidth, Math.min(maxRightWidth, width))
  }

  function addExpandedKey(key: string) {
    if (!expandedKeys.value.includes(key)) {
      expandedKeys.value.push(key)
    }
  }

  function removeExpandedKey(key: string) {
    const index = expandedKeys.value.indexOf(key)
    if (index !== -1) {
      expandedKeys.value.splice(index, 1)
    }
  }

  function setExpandedKeys(keys: string[]) {
    expandedKeys.value = keys
  }

  function showContextMenu(x: number, y: number, items: { label: string; action: () => void }[], nodeData?: any) {
    contextMenu.x = x
    contextMenu.y = y
    contextMenu.items = items
    contextMenu.nodeData = nodeData || null
    contextMenu.visible = true
  }

  function hideContextMenu() {
    contextMenu.visible = false
  }

  function showAIConfigDialog(task: string, input: any) {
    aiConfigDialog.task = task
    aiConfigDialog.input = input
    aiConfigDialog.visible = true
  }

  function hideAIConfigDialog() {
    aiConfigDialog.visible = false
  }

  function startResizing(side: 'left' | 'right') {
    resizing.value = side
    startX = window.event instanceof MouseEvent ? window.event.clientX : 0
    startWidth = side === 'left' ? leftSidebarWidth.value : rightSidebarWidth.value
    document.body.style.cursor = 'col-resize'
    window.addEventListener('mousemove', handleResizing)
    window.addEventListener('mouseup', stopResizing)
  }

  function handleResizing(e: MouseEvent) {
    if (!resizing.value) return
    if (resizing.value === 'left') {
      let newWidth = startWidth + (e.clientX - startX)
      setLeftSidebarWidth(newWidth)
    } else if (resizing.value === 'right') {
      let newWidth = startWidth - (e.clientX - startX)
      setRightSidebarWidth(newWidth)
    }
  }

  function stopResizing() {
    resizing.value = null
    document.body.style.cursor = ''
    window.removeEventListener('mousemove', handleResizing)
    window.removeEventListener('mouseup', stopResizing)
  }

  function setApplyChapterReplacements(fn: ((pairs: ChapterReplaceOp[]) => Promise<void> | void) | null) {
    applyChapterReplacements.value = fn
  }

  async function applyReplacements(pairs: ChapterReplaceOp[]) {
    if (applyChapterReplacements.value) {
      await applyChapterReplacements.value(pairs)
    }
  }

  function setPersistActiveChapterDraft(fn: (() => Promise<boolean>) | null) {
    persistActiveChapterDraftRef.value = fn
  }

  async function persistActiveChapterDraft(): Promise<boolean> {
    if (!persistActiveChapterDraftRef.value) return false
    return await persistActiveChapterDraftRef.value()
  }

  function setTriggerExtractDynamicInfo(fn: null | ((opts: ChapterExtractRunOptions) => Promise<void>)) {
    triggerExtractDynamicInfoRef.value = fn
  }

  async function triggerExtractDynamicInfo(opts: ChapterExtractRunOptions) {
    if (triggerExtractDynamicInfoRef.value) {
      await triggerExtractDynamicInfoRef.value(opts)
    }
  }

  function setTriggerExtractRelations(fn: null | ((opts: ChapterExtractRunOptions) => Promise<void>)) {
    triggerExtractRelationsRef.value = fn
  }

  async function triggerExtractRelations(opts: ChapterExtractRunOptions) {
    if (triggerExtractRelationsRef.value) {
      await triggerExtractRelationsRef.value(opts)
    }
  }

  function setTriggerExtractItemState(fn: null | ((opts: ChapterExtractRunOptions) => Promise<void>)) {
    triggerExtractItemStateRef.value = fn
  }

  async function triggerExtractItemState(opts: ChapterExtractRunOptions) {
    if (triggerExtractItemStateRef.value) {
      await triggerExtractItemStateRef.value(opts)
    }
  }

  function setTriggerExtractConceptState(fn: null | ((opts: ChapterExtractRunOptions) => Promise<void>)) {
    triggerExtractConceptStateRef.value = fn
  }

  async function triggerExtractConceptState(opts: ChapterExtractRunOptions) {
    if (triggerExtractConceptStateRef.value) {
      await triggerExtractConceptStateRef.value(opts)
    }
  }

  function setTriggerExtractSceneState(fn: null | ((opts: ChapterExtractRunOptions) => Promise<void>)) {
    triggerExtractSceneStateRef.value = fn
  }

  async function triggerExtractSceneState(opts: ChapterExtractRunOptions) {
    if (triggerExtractSceneStateRef.value) {
      await triggerExtractSceneStateRef.value(opts)
    }
  }

  function setTriggerExtractOrganizationState(fn: null | ((opts: ChapterExtractRunOptions) => Promise<void>)) {
    triggerExtractOrganizationStateRef.value = fn
  }

  async function triggerExtractOrganizationState(opts: ChapterExtractRunOptions) {
    if (triggerExtractOrganizationStateRef.value) {
      await triggerExtractOrganizationStateRef.value(opts)
    }
  }

  function setCurrentContextInfo(payload: { volume?: number | null; chapter?: number | null; title?: string }) {
    if (payload.volume !== undefined) currentVolumeNumber.value = payload.volume ?? null
    if (payload.chapter !== undefined) currentChapterNumber.value = payload.chapter ?? null
    if (payload.title !== undefined) currentChapterTitle.value = payload.title ?? ''
  }

  function reset() {
    activeEditor.value = null
    leftSidebarWidth.value = 250
    rightSidebarWidth.value = 300
    expandedKeys.value = ['content-root']
    contextMenu.visible = false
    aiConfigDialog.visible = false
    resizing.value = null
    applyChapterReplacements.value = null
    persistActiveChapterDraftRef.value = null
    triggerExtractDynamicInfoRef.value = null
    triggerExtractRelationsRef.value = null
    triggerExtractItemStateRef.value = null
    triggerExtractConceptStateRef.value = null
    triggerExtractSceneStateRef.value = null
    triggerExtractOrganizationStateRef.value = null
    currentVolumeNumber.value = null
    currentChapterNumber.value = null
    currentChapterTitle.value = ''
  }

  return {
    // State
    activeEditor,
    leftSidebarWidth,
    rightSidebarWidth,
    minLeftWidth,
    maxLeftWidth,
    minRightWidth,
    maxRightWidth,
    expandedKeys,
    contextMenu,
    aiConfigDialog,
    resizing,
    applyChapterReplacements,
    persistActiveChapterDraftRef,
    currentVolumeNumber,
    currentChapterNumber,
    currentChapterTitle,
    
    // Actions
    setActiveEditor,
    setLeftSidebarWidth,
    setRightSidebarWidth,
    addExpandedKey,
    removeExpandedKey,
    setExpandedKeys,
    showContextMenu,
    hideContextMenu,
    showAIConfigDialog,
    hideAIConfigDialog,
    startResizing,
    handleResizing,
    stopResizing,
    setApplyChapterReplacements,
    applyReplacements,
    setPersistActiveChapterDraft,
    persistActiveChapterDraft,
    setTriggerExtractDynamicInfo,
    triggerExtractDynamicInfo,
    setTriggerExtractRelations,
    triggerExtractRelations,
    setTriggerExtractItemState,
    triggerExtractItemState,
    setTriggerExtractConceptState,
    triggerExtractConceptState,
    setTriggerExtractSceneState,
    triggerExtractSceneState,
    setTriggerExtractOrganizationState,
    triggerExtractOrganizationState,
    setCurrentContextInfo,
    reset
  }
})
