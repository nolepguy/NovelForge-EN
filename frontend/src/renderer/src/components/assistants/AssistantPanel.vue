<template>
  <div class="assistant-panel" :style="assistantPanelStyle">
    <div class="panel-header">
      <div class="header-title-row">
        <div class="title-area">
          <span class="main-title">{{ t('assistant.title') }}</span>
          <span class="session-subtitle">{{ currentSession.title }}</span>
        </div>
        <div class="spacer"></div>
        <el-tooltip :content="t('assistant.newConversation')" placement="bottom">
          <el-button :icon="Plus" size="small" circle @click="createNewSession" />
        </el-tooltip>
        <el-tooltip :content="t('assistant.historyConversations')" placement="bottom">
          <el-button :icon="Clock" size="small" circle @click="historyDrawerVisible = true" />
        </el-tooltip>
      </div>
      <div class="header-controls-row">
        <el-tag v-if="currentCardTitle" size="small" type="info" class="card-tag" effect="plain">{{
          currentCardTitle
        }}</el-tag>
        <div class="spacer"></div>
        <el-button size="small" @click="$emit('refresh-context')">{{
          t('assistant.refreshContext')
        }}</el-button>
        <el-popover placement="bottom" width="480" trigger="hover">
          <template #reference>
            <el-tag type="info" class="ctx-tag" size="small">{{ t('common.preview') }}</el-tag>
          </template>
          <pre class="ctx-preview">{{ resolvedContext || '' }}</pre>
        </el-popover>
      </div>
    </div>

    <div class="chat-area reasoning-container">
      <AgentMessageList
        ref="messageListRef"
        :messages="messages"
        :streaming="isStreaming"
        :empty-description="t('assistant.emptyDescription')"
        :jump-project-id="projectStore.currentProject?.id || null"
        :show-assistant-actions="true"
        :assistant-actions-latest-only="false"
        :show-user-actions="true"
        @jump-to-card="(payload) => emit('jump-to-card', payload)"
        @copy-assistant="(payload) => handleCopyAssistantAt(payload.index)"
        @regenerate-assistant="(payload) => handleRegenerateAt(payload.index)"
        @delete-assistant="(payload) => handleDeleteAssistantAt(payload.index)"
        @copy-user="(payload) => handleCopyUserAt(payload.index)"
        @delete-user="(payload) => handleDeleteUserAt(payload.index)"
      />
      <div v-if="isStreaming" class="streaming-tip">{{ t('assistant.generating') }}</div>
    </div>

    <div class="composer">
      <div class="inject-toolbar">
        <!-- Referenced cards display area (split into two containers: tags area + more button area) -->
        <div class="chips">
          <!-- Tags display area (scrollable overflow) -->
          <div class="chips-tags">
            <el-tag
              v-for="(r, idx) in visibleRefs"
              :key="getRefKey(r)"
              closable
              size="small"
              effect="plain"
              class="chip-tag"
              @close="removeInjectedRef(idx)"
              @click="onChipClick(r)"
            >
              {{ getRefLabel(r) }}
            </el-tag>
          </div>

          <!-- More button area (always shown, unaffected by width) -->
          <div v-if="assistantStore.injectedRefs.length > 0" class="chips-more">
            <el-popover placement="bottom-start" :width="380" trigger="click">
              <template #reference>
                <el-button
                  size="small"
                  text
                  class="more-refs-btn"
                  :title="
                    t('assistant.refsCountTitle', { count: assistantStore.injectedRefs.length })
                  "
                >
                  <span class="more-refs-dots">...</span>
                  <span class="more-refs-count">({{ assistantStore.injectedRefs.length }})</span>
                </el-button>
              </template>

              <!-- Popover content -->
              <div class="more-refs-popover">
                <div class="popover-header">
                  <span>{{ t('assistant.referencedCards') }}</span>
                  <span class="popover-count"
                    >{{ assistantStore.injectedRefs.length }}
                    {{ t('assistant.refCountUnit') }}</span
                  >
                </div>
                <div class="more-refs-list">
                  <div
                    v-for="(r, idx) in assistantStore.injectedRefs"
                    :key="getRefKey(r)"
                    class="more-ref-item"
                  >
                    <span class="ref-info" @click="onChipClick(r)">
                      <el-icon><Document /></el-icon>
                      {{ getRefLabel(r) }}
                    </span>
                    <el-button
                      :icon="Close"
                      size="small"
                      text
                      :title="t('assistant.removeReference')"
                      @click="removeInjectedRef(idx)"
                    />
                  </div>
                </div>
              </div>
            </el-popover>
          </div>
        </div>

        <el-button size="small" :icon="Plus" class="add-ref-btn" @click="openInjectSelector">{{
          t('assistant.addReference')
        }}</el-button>
      </div>

      <div class="composer-subbar">
        <el-select
          v-model="overrideLlmId"
          :placeholder="t('assistant.selectModel')"
          size="small"
          style="width: 200px"
        >
          <el-option
            v-for="m in llmOptions"
            :key="m.id"
            :label="m.display_name || m.model_name"
            :value="m.id"
          />
        </el-select>
      </div>

      <AgentComposer
        v-model="draft"
        :rows="4"
        :placeholder="t('assistant.inputPlaceholder')"
        :disabled="isStreaming"
        input-class="composer-input"
        @keydown="handleComposerEnter"
      >
        <template #actions>
          <div class="composer-actions">
            <el-tooltip :content="t('assistant.thinkingTooltip')" placement="top">
              <el-switch
                v-model="useThinkingMode"
                size="small"
                active-text="Thinking"
                class="composer-toggle"
              />
            </el-tooltip>
            <el-tooltip :content="t('assistant.autosaveTooltip')" placement="top">
              <el-switch
                v-model="useAutosaveMode"
                size="small"
                active-text="Autosave"
                class="composer-toggle"
                style="margin-right: auto"
              />
            </el-tooltip>
            <el-button
              :type="sendButtonType"
              :icon="sendButtonIcon"
              circle
              :disabled="!isStreaming && !canSend"
              :title="sendButtonTitle"
              @click="handlePrimaryAction"
            />
          </div>
        </template>
      </AgentComposer>
    </div>

    <!-- Selector dialog -->
    <el-dialog
      v-model="selectorVisible"
      :title="t('assistant.addReferenceCardTitle')"
      width="760px"
    >
      <div style="display: flex; gap: 12px; align-items: center; margin-bottom: 10px">
        <el-select
          v-model="selectorSourcePid"
          :placeholder="t('assistant.sourceProject')"
          style="width: 260px"
          @change="onSelectorProjectChange($event as any)"
        >
          <el-option
            v-for="p in assistantStore.projects"
            :key="p.id"
            :label="p.name"
            :value="p.id"
          />
        </el-select>
        <el-input
          v-model="selectorSearch"
          :placeholder="t('assistant.searchTitle')"
          clearable
          style="flex: 1"
        />
      </div>
      <el-tree
        :data="selectorTreeData"
        :props="{ label: 'label', children: 'children' }"
        node-key="key"
        show-checkbox
        highlight-current
        :default-expand-all="false"
        :check-strictly="false"
        style="
          max-height: 360px;
          overflow: auto;
          border: 1px solid var(--el-border-color-light);
          padding: 8px;
          border-radius: 6px;
        "
        @check="onTreeCheck"
      />
      <template #footer>
        <el-button @click="selectorVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button
          type="primary"
          :disabled="!selectorSelectedIds.length || !selectorSourcePid"
          @click="confirmAddInjectedRefs"
          >{{ t('common.add') }}</el-button
        >
      </template>
    </el-dialog>

    <!-- History conversation drawer -->
    <el-drawer
      v-model="historyDrawerVisible"
      :title="t('assistant.historyConversations')"
      direction="rtl"
      size="320px"
    >
      <div class="history-drawer-content">
        <div class="history-actions">
          <el-button type="primary" :icon="Plus" style="width: 100%" @click="createNewSession">
            {{ t('assistant.newConversation') }}
          </el-button>
        </div>

        <el-divider />

        <div v-if="!historySessions.length" class="empty-history">
          <el-empty :description="t('assistant.noHistory')" :image-size="80" />
        </div>

        <div v-else class="history-list">
          <div
            v-for="session in historySessions"
            :key="session.id"
            :class="['history-item', { 'is-current': session.id === currentSession.id }]"
            @click="loadSession(session.id)"
          >
            <div class="history-item-header">
              <el-icon class="history-icon"><ChatDotRound /></el-icon>
              <span class="history-title">{{ session.title }}</span>
            </div>
            <div class="history-item-footer">
              <span class="history-time">{{ formatSessionTime(session.updatedAt) }}</span>
              <el-button
                :icon="Delete"
                size="small"
                text
                type="danger"
                @click.stop="handleDeleteSession(session.id)"
              />
            </div>
          </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { generateContinuationStreaming, renderPromptWithKnowledge } from '@renderer/api/ai'
import { listLLMConfigs, type LLMConfigRead } from '@renderer/api/setting'
import {
  Plus,
  Promotion,
  ChatDotRound,
  Delete,
  Clock,
  Document,
  Close,
  VideoPause
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import AgentMessageList from '@/components/shared/AgentMessageList.vue'
import AgentComposer from '@/components/shared/AgentComposer.vue'
import { useAssistantStore } from '@renderer/stores/useAssistantStore'
import { useProjectStore } from '@renderer/stores/useProjectStore'
import { useCardStore } from '@renderer/stores/useCardStore'
import { useEditorStore } from '@renderer/stores/useEditorStore'
import { useAssistantPreferences } from '@renderer/composables/useAssistantPreferences'
import { useAssistantSessionHistory } from '@renderer/composables/useAssistantSessionHistory'
import { useAssistantInjectionSelector } from '@renderer/composables/useAssistantInjectionSelector'
import { useAssistantRequestBuilder } from '@renderer/composables/useAssistantRequestBuilder'
import {
  applyAssistantStreamChunk,
  resetAssistantMessageForRegenerate
} from '@renderer/composables/useAssistantStreamMessageOps'
import { useEnterToSend } from '@renderer/composables/useEnterToSend'
import { useMessageListScroll } from '@renderer/composables/useMessageListScroll'
import { notifyTaskDone } from '@renderer/utils/taskDoneNotifier'
import type { AssistantChatSession, AssistantPanelMessage } from '@renderer/types/assistantPanel'
import type { AssistantRef } from '@renderer/api/ai'

const props = defineProps<{
  resolvedContext: string
  llmConfigId?: number | null
  promptName?: string | null
  temperature?: number | null
  max_tokens?: number | null
  timeout?: number | null
  effectiveSchema?: any
  generationPromptName?: string | null
  currentCardTitle?: string | null
  currentCardContent?: any
}>()
const emit = defineEmits<{
  finalize: [string]
  'refresh-context': []
  'reset-selection': []
  'jump-to-card': [{ projectId: number; cardId: number }]
}>()
const { t } = useI18n()
const messages = ref<AssistantPanelMessage[]>([])
const draft = ref('')
const isStreaming = ref(false)
let streamCtl: { cancel: () => void } | null = null
let streamCanceled = false
const { messageListRef, scrollToBottom } = useMessageListScroll()

// ---- Multi-card data references (cross-project, using Pinia) ----
const assistantStore = useAssistantStore()
const projectStore = useProjectStore()
const editorStore = useEditorStore()

// Reasoning process collapse state: key is the bucket id (e.g. plain-0-0 / pre-0-0 / g-0-1-0), value is whether expanded
// Collapsed by default (false), expands on user click
const reasoningBucketsOpen = ref<Record<string, boolean>>({})

function isReasoningBucketOpen(key: string): boolean {
  return Boolean(reasoningBucketsOpen.value[key])
}

// ===== Session management =====
const currentSession = ref<AssistantChatSession>({
  id: `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
  projectId: 0,
  title: t('assistant.newSession'),
  createdAt: Date.now(),
  updatedAt: Date.now(),
  messages: []
})

const historySessions = ref<AssistantChatSession[]>([])
const historyDrawerVisible = ref(false)
const projectIdRef = computed(() => projectStore.currentProject?.id || null)

const sessionHistory = useAssistantSessionHistory({
  projectId: projectIdRef,
  messages,
  currentSession,
  historySessions,
  historyDrawerVisible,
  onScrollToBottom: () => scrollToBottom()
})

const {
  saveCurrentSession,
  createNewSession,
  loadSession,
  handleDeleteSession,
  formatSessionTime
} = sessionHistory

const lastRun = ref<{ prev: string; tail: string; targetIdx: number } | null>(null)
const canRegenerate = computed(
  () =>
    !isStreaming.value &&
    !!lastRun.value &&
    messages.value[lastRun.value.targetIdx]?.role === 'assistant'
)

// Model selection (overrides card config, persisted per project)
const llmOptions = ref<LLMConfigRead[]>([])
const overrideLlmId = ref<number | null>(null)
const effectiveLlmId = computed(() => overrideLlmId.value || props.llmConfigId || null)
const MODEL_KEY_PREFIX = 'nf:assistant:model:'
function modelKeyForProject(pid: number): string {
  return `${MODEL_KEY_PREFIX}${pid}`
}

function restoreProjectAssistantState(pid: number | null): void {
  if (!pid) {
    overrideLlmId.value = null
    return
  }

  const saved = Number(localStorage.getItem(modelKeyForProject(pid)) || '')
  if (saved && Number.isFinite(saved)) {
    overrideLlmId.value = saved
  } else if (llmOptions.value.length > 0) {
    overrideLlmId.value = llmOptions.value[0].id
  } else {
    overrideLlmId.value = null
  }

  const thinkingSaved = localStorage.getItem(thinkingModeKeyForProject(pid))
  if (thinkingSaved !== null) {
    useThinkingMode.value = thinkingSaved === 'true'
  }

  const autosaveSaved = localStorage.getItem(autosaveModeKeyForProject(pid))
  if (autosaveSaved !== null) {
    useAutosaveMode.value = autosaveSaved === 'true'
  }
}

// Thinking mode toggle (persisted per project)
const useThinkingMode = ref(false)
const THINKING_MODE_KEY_PREFIX = 'nf:assistant:thinking:'
function thinkingModeKeyForProject(pid: number): string {
  return `${THINKING_MODE_KEY_PREFIX}${pid}`
}

// Autosave mode toggle (persisted per project)
const useAutosaveMode = ref(false)
const AUTOSAVE_MODE_KEY_PREFIX = 'nf:assistant:autosave:'
function autosaveModeKeyForProject(pid: number): string {
  return `${AUTOSAVE_MODE_KEY_PREFIX}${pid}`
}

// Card ids touched (field-filled) during the current assistant run, awaiting confirm & save
const autosaveTouchedCardIds = ref<Set<number>>(new Set())

// Referenced cards display control
const MAX_VISIBLE_REFS = 5 // Show at most 5 references (about two rows, 2-3 per row)

const visibleRefs = computed(() => {
  return assistantStore.injectedRefs.slice(0, MAX_VISIBLE_REFS)
})

watch(overrideLlmId, (val) => {
  try {
    const pid = projectStore.currentProject?.id
    if (pid && val) localStorage.setItem(modelKeyForProject(pid), String(val))
  } catch {
    // ignore localStorage write errors
  }
})

watch(useThinkingMode, (val) => {
  try {
    const pid = projectStore.currentProject?.id
    if (pid) localStorage.setItem(thinkingModeKeyForProject(pid), String(val))
  } catch {
    // ignore localStorage write errors
  }
})

watch(useAutosaveMode, (val) => {
  try {
    const pid = projectStore.currentProject?.id
    if (pid) localStorage.setItem(autosaveModeKeyForProject(pid), String(val))
  } catch {
    // ignore localStorage write errors
  }
})

const injectedCardPrompt = ref<string>('')
async function loadInjectedCardPrompt() {
  try {
    const name = props.generationPromptName || ''
    if (!name) {
      injectedCardPrompt.value = ''
      return
    }
    const resp = await renderPromptWithKnowledge(name)
    injectedCardPrompt.value = resp?.text || ''
  } catch {
    injectedCardPrompt.value = ''
  }
}

watch(
  () => props.generationPromptName,
  async () => {
    await loadInjectedCardPrompt()
  },
  { immediate: true }
)

const canSend = computed(() => {
  const hasDraft = !!draft.value.trim()
  const hasRefs = assistantStore.injectedRefs.length > 0
  return !!effectiveLlmId.value && (hasDraft || hasRefs)
})
const sendButtonType = computed(() => (isStreaming.value ? 'danger' : 'primary'))
const sendButtonTitle = computed(() =>
  isStreaming.value ? t('assistant.abortGeneration') : t('assistant.send')
)
const sendButtonIcon = computed(() => (isStreaming.value ? VideoPause : Promotion))

const assistantPrefs = useAssistantPreferences()
const assistantPanelStyle = computed(() => ({
  '--nf-assistant-font-size': `${assistantPrefs.assistantFontSize.value}px`,
  '--nf-assistant-line-height': '1.65'
}))

function notifyAssistantDone(): void {
  notifyTaskDone({
    title: t('assistant.notifyTitle'),
    body: t('assistant.notifyBody'),
    soundEnabled: assistantPrefs.taskDoneSoundEnabled.value,
    desktopNotificationEnabled: assistantPrefs.taskDoneDesktopNotificationEnabled.value
  })
}

// Autosave: automatically confirm & save cards the assistant field-filled during this run.
// Mirrors the manual "Confirm & Save" button by clearing needs_confirmation, which triggers
// each card's onSave workflow via the backend PUT /cards/{id} handler.
async function nfAutosaveConfirmTouchedCards(): Promise<void> {
  if (!useAutosaveMode.value) return
  const ids = Array.from(autosaveTouchedCardIds.value)
  if (!ids.length) return

  const pid = projectStore.currentProject?.id
  const cardStore = useCardStore()
  // Ensure the store reflects the latest DB state (including needs_confirmation flags set by tools)
  if (pid) {
    try {
      await cardStore.fetchCards(pid)
    } catch (e) {
      console.error('[Assistant.autosave] fetchCards failed:', e)
    }
  }

  // Only confirm cards that are still flagged needs_confirmation, to avoid marking
  // untouched cards as user-modified via the backend's "scenario 2" path.
  const toConfirm = ids.filter((id) => {
    const c = cardStore.cards.find((c) => c.id === id)
    return !!c && c.needs_confirmation === true
  })

  let count = 0
  for (const id of toConfirm) {
    try {
      await cardStore.modifyCard(id, { needs_confirmation: false })
      count++
    } catch (e) {
      console.error(`[Assistant.autosave] confirm failed for card ${id}:`, e)
    }
  }

  if (count > 0) {
    ElMessage.success(t('assistant.autosaveConfirmed', { count }))
  }
  autosaveTouchedCardIds.value = new Set()
}
const injectionSelector = useAssistantInjectionSelector({
  assistantStore,
  currentProjectId: computed(() => projectStore.currentProject?.id || null)
})

const {
  selectorVisible,
  selectorSourcePid,
  selectorSearch,
  selectorSelectedIds,
  selectorTreeData,
  openInjectSelector,
  onSelectorProjectChange,
  onTreeCheck,
  confirmAddInjectedRefs
} = injectionSelector

function removeInjectedRef(idx: number) {
  assistantStore.removeInjectedRefAt(idx)
}

function getRefKey(ref: AssistantRef): string {
  if (ref.refType === 'card') return `card:${ref.projectId}:${ref.cardId}`
  if (ref.refType === 'chapter_excerpt') {
    return `chapter_excerpt:${ref.projectId}:${ref.cardId}:${ref.startLine}:${ref.endLine}:${ref.snapshotHash}`
  }
  return `review_result:${ref.projectId}:${ref.reviewCardId}`
}

function getRefLabel(ref: AssistantRef): string {
  if (ref.refType === 'card') return `${ref.projectName} / ${ref.cardTitle}`
  if (ref.refType === 'chapter_excerpt') {
    return `${ref.projectName} / ${ref.cardTitle} [${ref.startLine}-${ref.endLine} ${t('assistant.lineRangeUnit')}]`
  }
  return `${t('assistant.reviewResultLabel')} / ${ref.targetTitle}`
}

const { buildConversationText, buildAssistantChatRequest } = useAssistantRequestBuilder({
  messages,
  assistantStore,
  resolvedContext: computed(() => props.resolvedContext || ''),
  effectiveSchema: computed(() => props.effectiveSchema),
  preferences: {
    contextSummaryEnabled: assistantPrefs.contextSummaryEnabled,
    contextSummaryThreshold: assistantPrefs.contextSummaryThreshold,
    reactModeEnabled: assistantPrefs.reactModeEnabled,
    assistantTemperature: assistantPrefs.assistantTemperature,
    assistantMaxTokens: assistantPrefs.assistantMaxTokens,
    assistantTimeout: assistantPrefs.assistantTimeout
  }
})

async function startStreaming(targetIdx: number) {
  isStreaming.value = true
  streamCanceled = false
  autosaveTouchedCardIds.value = new Set()

  const hasChapterExcerptRefs = assistantStore.injectedRefs.some(
    (ref) => ref.refType === 'chapter_excerpt'
  )
  if (hasChapterExcerptRefs) {
    try {
      const persisted = await editorStore.persistActiveChapterDraft()
      if (!persisted) {
        isStreaming.value = false
        return
      }
    } catch (error) {
      console.error('Failed to persist active chapter draft before assistant run:', error)
      ElMessage.error(t('assistant.persistChapterFailed'))
      isStreaming.value = false
      return
    }
  }

  const chatRequest = buildAssistantChatRequest()
  const promptName = props.promptName?.trim() || 'Inspiration Dialogue'
  const requestTemperature = assistantPrefs.assistantTemperature.value

  streamCtl = generateContinuationStreaming(
    {
      ...chatRequest,
      llm_config_id: overrideLlmId.value || undefined,
      prompt_name: promptName,
      temperature: requestTemperature || undefined,
      project_id: projectStore.currentProject?.id as number,
      stream: true,
      thinking_enabled: useThinkingMode.value
    } as any,
    (chunk) => {
      applyAssistantStreamChunk({
        messages,
        targetIdx,
        chunk,
        reasoningBucketsOpen,
        isReasoningBucketOpen,
        scrollToBottom,
        schedule: (callback) => nextTick(callback),
        onToolsExecuted: (tools) => handleToolsExecuted(targetIdx, tools)
      })
    },
    () => {
      const wasCanceled = streamCanceled
      streamCanceled = false
      isStreaming.value = false
      streamCtl = null

      if (
        messages.value[targetIdx]?.toolsInProgress &&
        !messages.value[targetIdx].toolsInProgress.includes('❌')
      ) {
        nextTick(() => {
          if (messages.value[targetIdx]) {
            messages.value[targetIdx].toolsInProgress = undefined
          }
        })
      }

      if (messages.value.length > 0) {
        saveCurrentSession()
      }
      if (!wasCanceled) {
        nfFlushAssistantTextPatchBatches(targetIdx)
        nfMaybeDispatchTextPatchBatchFromMessage(targetIdx)
        notifyAssistantDone()
        nfAutosaveConfirmTouchedCards()
      }
    },
    (err) => {
      streamCanceled = false
      if (messages.value[targetIdx]) {
        messages.value[targetIdx].toolsInProgress = undefined
      }
      ElMessage.error(err?.message || t('assistant.generationFailed'))
      isStreaming.value = false
      streamCtl = null
    }
  ) as any
}

function handleSend() {
  if (!canSend.value || isStreaming.value) return
  lastRun.value = null
  const userText = draft.value.trim()
  if (!userText) return
  messages.value.push({ role: 'user', content: userText })
  try {
    const pid = projectStore.currentProject?.id
    if (pid) assistantStore.appendHistory(pid, { role: 'user', content: userText })
  } catch {}
  draft.value = ''
  scrollToBottom()

  // The inspiration assistant does not need prev/tail, build the request directly inside startStreaming
  const assistantIdx = messages.value.push({ role: 'assistant', content: '' }) - 1
  scrollToBottom()
  lastRun.value = { prev: '', tail: '', targetIdx: assistantIdx }
  startStreaming(assistantIdx)
}

function handleCancel() {
  if (streamCtl) streamCanceled = true
  try {
    streamCtl?.cancel()
  } catch {}
  isStreaming.value = false

  // Clear tool call progress indicators from all messages
  messages.value.forEach((msg) => {
    if (msg.toolsInProgress) {
      msg.toolsInProgress = undefined
    }
  })
}

function handlePrimaryAction() {
  if (isStreaming.value) {
    handleCancel()
    return
  }
  handleSend()
}

function handleCopyAssistantAt(index: number) {
  const target = messages.value[index]
  if (!target || target.role !== 'assistant') return
  const text = (target.content || '').trim()
  if (!text) return

  navigator.clipboard
    .writeText(text)
    .then(() => {
      ElMessage.success(t('common.copySuccess'))
    })
    .catch(() => {
      ElMessage.error(t('common.copyFailed'))
    })
}

function handleCopyUserAt(index: number) {
  const target = messages.value[index]
  if (!target || target.role !== 'user') return
  const text = (target.content || '').trim()
  if (!text) return

  navigator.clipboard
    .writeText(text)
    .then(() => {
      ElMessage.success(t('common.copySuccess'))
    })
    .catch(() => {
      ElMessage.error(t('common.copyFailed'))
    })
}

function handleRegenerateAt(index: number) {
  if (isStreaming.value) return
  if (index < 0 || index >= messages.value.length) return
  if (messages.value[index]?.role !== 'assistant') return

  messages.value = messages.value.slice(0, index + 1)
  const target = messages.value[index]
  resetAssistantMessageForRegenerate(target)

  lastRun.value = { prev: '', tail: '', targetIdx: index }
  scrollToBottom()
  startStreaming(index)
}

function handleDeleteAssistantAt(index: number) {
  if (isStreaming.value) return
  if (index < 0 || index >= messages.value.length) return
  if (messages.value[index]?.role !== 'assistant') return

  deleteMessageAt(index)
  ElMessage.success(t('assistant.replyDeleted'))
}

function handleDeleteUserAt(index: number) {
  if (isStreaming.value) return
  if (index < 0 || index >= messages.value.length) return
  if (messages.value[index]?.role !== 'user') return

  deleteMessageAt(index)
  ElMessage.success(t('assistant.messageDeleted'))
}

function deleteMessageAt(index: number) {
  if (index < 0 || index >= messages.value.length) return

  messages.value.splice(index, 1)

  if (lastRun.value) {
    if (lastRun.value.targetIdx === index) {
      lastRun.value = null
    } else if (lastRun.value.targetIdx > index) {
      lastRun.value = {
        ...lastRun.value,
        targetIdx: lastRun.value.targetIdx - 1
      }
    }
  }

  saveCurrentSession()
}

function handleRegenerate() {
  if (!canRegenerate.value || !lastRun.value) return
  messages.value[lastRun.value.targetIdx].content = ''
  scrollToBottom()
  startStreaming(lastRun.value.targetIdx)
}
function regenerateFromCurrent() {
  if (isStreaming.value) return
  const lastIndex = messages.value.length - 1
  const lastIsAssistant = lastIndex >= 0 && messages.value[lastIndex].role === 'assistant'
  let targetIdx: number
  if (lastIsAssistant) {
    resetAssistantMessageForRegenerate(messages.value[lastIndex])
    targetIdx = lastIndex
  } else {
    targetIdx = messages.value.push({ role: 'assistant', content: '' }) - 1
  }
  lastRun.value = { prev: '', tail: '', targetIdx }
  startStreaming(targetIdx)
}
function handleRegenerateWithHistory() {
  // Prefer to remove the last assistant message from history
  try {
    const pid = projectStore.currentProject?.id
    if (pid) {
      const hist = assistantStore.getHistory(pid)
      for (let i = hist.length - 1; i >= 0; i--) {
        if (hist[i].role === 'assistant') {
          hist.splice(i, 1)
          break
        }
      }
      assistantStore.setHistory(pid, hist)
    }
  } catch {}
  if (lastRun.value && canRegenerate.value) {
    handleRegenerate()
  } else {
    regenerateFromCurrent()
  }
}
function handleFinalize() {
  const summary = (() => {
    const last = [...messages.value].reverse().find((m) => m.role === 'assistant')
    return (last?.content || '').trim() || buildConversationText()
  })()
  emit('finalize', summary)
}
function onChipClick(refItem: AssistantRef) {
  if (refItem.refType === 'review_result') {
    emit('jump-to-card', { projectId: refItem.projectId, cardId: refItem.targetId })
    return
  }
  emit('jump-to-card', { projectId: refItem.projectId, cardId: refItem.cardId })
}

const handleComposerEnter = useEnterToSend({
  canSend,
  onSend: handleSend,
  streaming: isStreaming
})

onMounted(async () => {
  try {
    llmOptions.value = await listLLMConfigs()
  } catch {}
  restoreProjectAssistantState(projectStore.currentProject?.id || null)
})

watch(projectIdRef, (pid) => {
  restoreProjectAssistantState(pid)
})

// ✅ Handle tool execution results: append tool results to the specified assistant message
/* NF_ASSISTANT_BATCH_PATCH_BEGIN */
function nfIsAssistantTextPatchBatch(result: any): boolean {
  return (
    !!result &&
    (result.kind === 'assistant_text_patch_batch' ||
      result.status === 'text_patch_batch_proposed') &&
    Array.isArray(result.patches)
  )
}

function nfNormalizeAssistantPatchBatch(result: any) {
  const patches = Array.isArray(result?.patches) ? result.patches : []
  return {
    ...result,
    kind: 'assistant_text_patch_batch',
    status: result?.status || 'text_patch_batch_proposed',
    patches: patches.map((patch: any, index: number) => ({
      ...patch,
      id: patch?.id ?? index + 1,
      index: patch?.index ?? index + 1,
      old_text: patch?.old_text ?? patch?.original_text ?? '',
      original_text: patch?.original_text ?? patch?.old_text ?? '',
      new_text: patch?.new_text ?? patch?.revised_text ?? patch?.replacement_text ?? '',
      instruction: patch?.instruction ?? patch?.reason ?? patch?.explanation ?? '',
      status: patch?.status || 'pending'
    }))
  }
}

function nfDispatchAssistantTextPatchBatch(result: any): number {
  const batch = nfNormalizeAssistantPatchBatch(result)
  if (!batch.patches.length) return 0
  window.dispatchEvent(new CustomEvent('nf-assistant-text-patch-batch', { detail: batch }))
  return batch.patches.length
}

function nfStoreAssistantTextPatchBatches(msg: AssistantPanelMessage, results: any[]): void {
  const messageAny = msg as any
  if (!Array.isArray(messageAny._nfPendingPatchBatches)) {
    messageAny._nfPendingPatchBatches = []
  }
  messageAny._nfPendingPatchBatches.push(...results.map(nfNormalizeAssistantPatchBatch))
}

function nfFlushAssistantTextPatchBatches(targetIdx: number): boolean {
  const msg = messages.value[targetIdx]
  if (!msg || msg.role !== 'assistant') return false

  const messageAny = msg as any
  const batches = Array.isArray(messageAny._nfPendingPatchBatches)
    ? messageAny._nfPendingPatchBatches
    : []
  if (!batches.length) return false

  const grouped = new Map<string, any>()
  for (const batch of batches) {
    const key = `${batch.card_id ?? ''}::${batch.field_path ?? 'content'}`
    const current = grouped.get(key)
    if (current) {
      current.patches.push(...batch.patches)
      current.failed_patches = [...(current.failed_patches || []), ...(batch.failed_patches || [])]
    } else {
      grouped.set(key, {
        ...batch,
        patches: [...batch.patches],
        failed_patches: [...(batch.failed_patches || [])]
      })
    }
  }

  let total = 0
  grouped.forEach((batch) => {
    batch.patches = batch.patches.map((patch: any, index: number) => ({
      ...patch,
      id: patch.id ?? index + 1,
      index: index + 1
    }))
    batch.count = batch.patches.length
    batch.failed_count = Array.isArray(batch.failed_patches) ? batch.failed_patches.length : 0
    total += nfDispatchAssistantTextPatchBatch(batch)
  })

  messageAny._nfPendingPatchBatches = []
  messageAny._nfPatchBatchDispatched = total > 0
  if (total > 0) {
    ElMessage.success(t('assistant.suggestionsSent', { count: total }))
  }
  return total > 0
}

function nfCleanPatchText(raw: unknown): string {
  return String(raw ?? '')
    .trim()
    .replace(/^```[a-zA-Z0-9_-]*\s*/, '')
    .replace(/```$/, '')
    .replace(/^["“”'‘’]+|["“”'‘’]+$/g, '')
    .trim()
}

function nfEscapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function nfExtractLabeledValue(block: string, labels: string[], allLabels: string[]): string {
  const labelPattern = labels.map(nfEscapeRegExp).join('|')
  const stopPattern = allLabels.map(nfEscapeRegExp).join('|')
  const re = new RegExp(
    `(?:^|\\n)\\s*(?:${labelPattern})\\s*[：:]?\\s*([\\s\\S]*?)(?=\\n\\s*(?:${stopPattern})\\s*[：:]|$)`,
    'i'
  )
  const match = block.match(re)
  return nfCleanPatchText(match?.[1] || '')
}

function nfSplitSuggestionBlocks(text: string): string[] {
  const lines = text.replace(/\r\n/g, '\n').split('\n')
  const blocks: string[] = []
  let current: string[] = []
  const startRe = /^\s*(?:Suggestion\s*#?\s*\d+|Item\s*\d+|#\s*\d+|\d+[.\)])/

  for (const line of lines) {
    if (startRe.test(line) && current.join('\n').trim()) {
      blocks.push(current.join('\n'))
      current = [line]
    } else {
      current.push(line)
    }
  }
  if (current.join('\n').trim()) {
    blocks.push(current.join('\n'))
  }
  return blocks.length ? blocks : [text]
}

function nfCurrentTextPatchTarget(): { card_id?: number; field_path: string } {
  const refs = assistantStore.injectedRefs as any[]
  const excerpt = refs.find((ref) => ref?.refType === 'chapter_excerpt')
  if (excerpt) {
    return {
      card_id: Number(excerpt.cardId) || undefined,
      field_path: excerpt.fieldPath || 'content'
    }
  }
  const card = refs.find((ref) => ref?.refType === 'card')
  if (card) {
    return { card_id: Number(card.cardId) || undefined, field_path: 'content' }
  }
  return { field_path: 'content' }
}

function nfParseAssistantTextPatchBatch(text: string): any | null {
  const normalized = text.replace(/\r\n/g, '\n').trim()
  if (!normalized) return null

  const allLabels = [
    'original text',
    'original sentence',
    'original excerpt',
    'old text',
    'old_text',
    'original_text',
    'new text',
    'modified',
    'replace with',
    'suggested replacement',
    'new_text',
    'revised_text',
    'replacement_text',
    'reason',
    'explanation',
    'cause',
    'reason',
    'instruction',
    'explanation'
  ]
  const blocks = nfSplitSuggestionBlocks(normalized)
  const target = nfCurrentTextPatchTarget()
  const patches = blocks
    .map((block, index) => {
      const oldText = nfExtractLabeledValue(
        block,
        ['original text', 'original sentence', 'original excerpt', 'old text', 'old_text', 'original_text'],
        allLabels
      )
      const newText = nfExtractLabeledValue(
        block,
        ['new text', 'modified', 'replace with', 'suggested replacement', 'new_text', 'revised_text', 'replacement_text'],
        allLabels
      )
      const instruction = nfExtractLabeledValue(
        block,
        ['reason', 'explanation', 'cause', 'reason', 'instruction', 'explanation'],
        allLabels
      )
      if (!oldText || !newText) return null
      return {
        id: index + 1,
        index: index + 1,
        card_id: target.card_id,
        field_path: target.field_path,
        old_text: oldText,
        original_text: oldText,
        new_text: newText,
        instruction,
        status: 'pending'
      }
    })
    .filter(Boolean)

  if (!patches.length) return null
  return {
    success: true,
    kind: 'assistant_text_patch_batch',
    status: 'text_patch_batch_proposed',
    card_id: target.card_id,
    field_path: target.field_path,
    count: patches.length,
    patches,
    preview_only: true,
    needs_user_accept: true,
    source: 'assistant_text_parse'
  }
}

function nfLooksLikeTextPatchSuggestions(text: string): boolean {
  return (
    /(?:original text|original sentence|original excerpt|old text|old_text|original_text)/i.test(text) &&
    /(?:new text|modified|replace with|suggested replacement|new_text|revised_text|replacement_text)/i.test(text)
  )
}

function nfMaybeDispatchTextPatchBatchFromMessage(targetIdx: number): boolean {
  const msg = messages.value[targetIdx]
  if (!msg || msg.role !== 'assistant') return false

  const messageAny = msg as any
  if (messageAny._nfPatchBatchDispatched) return true

  const parsed = nfParseAssistantTextPatchBatch(msg.content || '')
  if (parsed) {
    const count = nfDispatchAssistantTextPatchBatch(parsed)
    messageAny._nfPatchBatchDispatched = count > 0
    if (count > 0) {
      ElMessage.success(t('assistant.suggestionsParsed', { count: count }))
      return true
    }
  } else if (nfLooksLikeTextPatchSuggestions(msg.content || '')) {
    ElMessage.warning(t('assistant.suggestionParseWarning'))
  }
  return false
}
/* NF_ASSISTANT_BATCH_PATCH_END */

function handleToolsExecuted(targetIdx: number, tools: Array<{ tool_name: string; result: any }>) {
  console.log('🔧 Tools executed:', targetIdx, tools)

  const msg = messages.value[targetIdx]
  if (!msg || msg.role !== 'assistant') return

  const nfPatchBatchTools = tools
    .map((t) => t?.result)
    .filter((result) => nfIsAssistantTextPatchBatch(result))
  if (nfPatchBatchTools.length) {
    nfStoreAssistantTextPatchBatches(msg, nfPatchBatchTools)
  }
  // Refresh the left card tree (if any card was created or modified)
  const needsRefresh = tools.some((t) => {
    const toolName = t.tool_name
    const result = t.result

    // These tools require a card list refresh after being called
    const refreshTools = [
      'create_card',
      'modify_card_field',
      'batch_create_cards',
      'replace_field_text',
      'replace_card_text_by_lines'
    ]

    if (refreshTools.includes(toolName)) {
      console.log(`🔄 Detected ${toolName} call, preparing to refresh card list`)
      return true
    }

    // Or a result with a card_id field
    if (result?.card_id) {
      console.log(`🔄 Detected card_id: ${result.card_id}, preparing to refresh card list`)
      return true
    }

    return false
  })

  if (needsRefresh && projectStore.currentProject?.id) {
    const cardStore = useCardStore()
    console.log('🔄 Starting card list refresh...')
    // Refresh the entire card list
    cardStore
      .fetchCards(projectStore.currentProject.id)
      .then(() => {
        console.log('✅ Card list refresh complete')
      })
      .catch((err) => {
        console.error('❌ Card list refresh failed:', err)
      })
  }

  // Show notification
  const successTools = tools.filter((t) => t.result?.success)
  if (successTools.length > 0) {
    ElMessage.success(t('assistant.toolsExecuted', { count: successTools.length }))
  }

  const failedTools = tools.filter((t) => t.result?.success === false || t.result?.error)
  if (failedTools.length > 0) {
    const first = failedTools[0]
    const message =
      first.result?.message ||
      first.result?.error ||
      t('assistant.toolCallFailed', { name: first.tool_name || t('assistant.toolGeneric') })
    ElMessage.error(String(message))
  }

  // Collect cards flagged needs_confirmation by the assistant (for autosave on run end)
  for (const tl of tools) {
    const result = tl?.result
    if (!result) continue
    if (result.needs_confirmation === true) {
      const direct = Number(result.card_id)
      if (Number.isFinite(direct)) autosaveTouchedCardIds.value.add(direct)
      const arrays: Array<unknown> = [result.cards, result.created_cards, result.card_ids]
      for (const arr of arrays) {
        if (!Array.isArray(arr)) continue
        for (const item of arr) {
          const id =
            typeof item === 'number'
              ? item
              : Number((item as { card_id?: unknown; id?: unknown })?.card_id ?? (item as { id?: unknown })?.id)
          if (Number.isFinite(id)) autosaveTouchedCardIds.value.add(id)
        }
      }
    }
  }
}

// Auto-save on message changes (debounced, to avoid saving too frequently)
// Optimization: only watch array length and the last message, to avoid deep watching performance issues
let saveDebounceTimer: any = null
watch(
  [() => messages.value.length, () => messages.value[messages.value.length - 1]?.content],
  () => {
    if (messages.value.length > 0) {
      // Clear the previous timer
      if (saveDebounceTimer) clearTimeout(saveDebounceTimer)
      // Save after 300ms
      saveDebounceTimer = setTimeout(() => {
        saveCurrentSession()
      }, 300)
    }
  }
)

onBeforeUnmount(() => {
  if (saveDebounceTimer) {
    clearTimeout(saveDebounceTimer)
    saveDebounceTimer = null
  }
})
</script>

<style scoped>
.assistant-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  font-size: 13px;
  --nf-assistant-font-size: 16px;
  --nf-assistant-line-height: 1.65;
  font-family:
    'Segoe UI', 'Helvetica Neue', Arial, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei',
    sans-serif;
}
.panel-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
  border-bottom: 1px solid var(--el-border-color-light);
  background: var(--el-bg-color);
}
.header-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.title-area {
  flex: 1;
  display: flex;
  align-items: baseline;
  gap: 8px;
  overflow: hidden;
}
.main-title {
  font-weight: 600;
  color: var(--el-text-color-primary);
  font-size: 15px;
  flex-shrink: 0;
}
.session-subtitle {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.header-controls-row {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: nowrap;
  overflow-x: auto;
}
.panel-header .card-tag {
  flex-shrink: 0;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
}
.panel-header .spacer {
  flex: 1;
  min-width: 4px;
}
.ctx-tag {
  cursor: pointer;
  flex-shrink: 0;
  font-size: 12px;
}
.header-controls-row .el-button {
  flex-shrink: 0;
  padding: 3px 6px;
  font-size: 12px;
}
.ctx-preview {
  max-height: 40vh;
  overflow: auto;
  white-space: pre-wrap;
  background: var(--el-bg-color);
  color: var(--el-text-color-primary);
  padding: 8px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
}
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow: hidden;
  padding: 6px 8px;
}
.streaming-tip {
  color: var(--el-text-color-secondary);
  padding-left: 4px;
  font-size: var(--nf-assistant-font-size);
  line-height: var(--nf-assistant-line-height);
}
.composer {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px;
  border-top: 1px solid var(--el-border-color-light);
}

/* Referenced cards toolbar - fixed height, more compact */
.inject-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  padding-bottom: 6px;
  min-height: 28px;
  max-height: 64px; /* Slightly taller to fit two rows + spacing */
}

.inject-toolbar .chips {
  display: flex;
  align-items: flex-start; /* top-aligned */
  gap: 6px;
  flex: 1;
  overflow: hidden;
  max-height: 58px; /* Limit to at most two rows (24px×2 + 6px spacing + 4px allowance) */
}

/* Tags display area (wraps, neatly arranged) */
.chips-tags {
  display: flex;
  align-items: flex-start; /* top-aligned */
  gap: 6px; /* uniform spacing */
  row-gap: 6px; /* row spacing */
  flex-wrap: wrap;
  flex: 1;
  overflow: hidden;
  line-height: 1.2;
  align-content: flex-start; /* multi-row starts from top */
  min-height: 24px; /* at least one row height */
}

/* More button area (always shown) */
.chips-more {
  flex-shrink: 0; /* do not shrink */
  display: flex;
  align-items: flex-start; /* top-aligned with tags */
  padding-top: 2px; /* fine-tune alignment */
}

.chip-tag {
  cursor: pointer;
  font-size: 12px !important;
  height: 24px !important;
  line-height: 22px !important;
  padding: 0 8px !important;
  margin: 0; /* remove top/bottom margins, use gap for uniform spacing */
  flex-shrink: 0; /* prevent tags from being compressed */
  white-space: nowrap; /* prevent text inside tags from wrapping */
}

/* Input box styles */
.composer-input {
  flex: 1;
  min-height: 90px;
}

::deep(.composer-input .el-textarea__inner) {
  min-height: 90px !important;
  font-size: var(--nf-assistant-font-size);
  line-height: var(--nf-assistant-line-height);
}

::deep(.composer-input .el-textarea__inner::placeholder) {
  font-size: var(--nf-assistant-font-size);
}

.more-refs-btn {
  font-size: 12px;
  font-weight: 600;
  color: var(--el-color-primary);
  padding: 0 10px !important;
  height: 24px !important;
  line-height: 22px !important;
  border: 1px dashed var(--el-color-primary);
  border-radius: 4px;
  flex-shrink: 0;
  margin: 0; /* align with tags */
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

.more-refs-btn:hover {
  background: var(--el-color-primary-light-9);
  border-color: var(--el-color-primary);
}

.more-refs-dots {
  font-weight: 700;
  letter-spacing: 1px;
}

.more-refs-count {
  font-size: 11px;
  font-weight: 500;
  opacity: 0.85;
}

/* Add reference button */
.add-ref-btn {
  flex-shrink: 0;
  align-self: flex-start; /* top-aligned */
  margin-top: 2px; /* fine-tune alignment */
}

/* More references popover */
.more-refs-popover {
  padding: 0;
}

.popover-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  font-weight: 600;
  font-size: 13px;
  color: var(--el-text-color-primary);
}

.popover-count {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-weight: normal;
}

.more-refs-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 320px;
  overflow-y: auto;
  padding: 8px;
}

.more-ref-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
  transition: all 0.2s;
}

.more-ref-item:hover {
  background: var(--el-fill-color);
}

.more-ref-item .ref-info {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  color: var(--el-text-color-regular);
  flex: 1;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.more-ref-item .ref-info:hover {
  color: var(--el-color-primary);
}

.composer-subbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 2px 0;
}

.composer-actions {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
  flex-wrap: nowrap;
  align-items: center;
  padding: 4px 0 0 0;
  width: 100%;
}

.composer-actions .composer-toggle {
  flex-shrink: 0;
}

.composer-actions .composer-toggle :deep(.el-switch__label) {
  font-size: 12px;
}

::deep(.composer .el-button) {
  padding: 6px 8px;
  font-size: 12px;
}
::deep(.inject-toolbar .el-button) {
  padding: 4px 8px !important;
  font-size: 12px;
  height: 24px;
}

.chat-area :deep(.msg-bubble),
.chat-area :deep(.bubble-markdown),
.chat-area :deep(.bubble-markdown p),
.chat-area :deep(.bubble-markdown li),
.chat-area :deep(.bubble-markdown blockquote),
.chat-area :deep(.bubble-markdown span),
.chat-area :deep(.bubble-markdown strong),
.chat-area :deep(.bubble-markdown em),
.chat-area :deep(.thinking-content),
.chat-area :deep(.thinking-content .bubble-markdown),
.chat-area :deep(.tool-result),
.chat-area :deep(.tools-progress-text) {
  font-size: var(--nf-assistant-font-size);
  line-height: var(--nf-assistant-line-height);
}

.chat-area :deep(.thinking-title) {
  font-size: max(14px, calc(var(--nf-assistant-font-size) - 1px));
}

/* History conversation drawer styles */
.history-drawer-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 0;
}

.history-actions {
  padding: 0 0 8px 0;
}

.empty-history {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 0;
}

.history-item {
  padding: 12px;
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
  border: 1px solid var(--el-border-color-light);
  cursor: pointer;
  transition: all 0.2s;
}

.history-item:hover {
  background: var(--el-fill-color-light);
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.history-item.is-current {
  background: var(--el-color-primary-light-9);
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 1px var(--el-color-primary-light-7);
}

.history-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.history-icon {
  color: var(--el-color-primary);
  font-size: 16px;
  flex-shrink: 0;
}

.history-title {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-item-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.history-time {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

:deep(.el-thinking .trigger) {
  color: var(--el-text-color-primary);
  background: var(--el-fill-color-light);
}

/* i18n: english-length css fixes */

.assistant-panel :deep(.el-button) {
  white-space: nowrap;
}
.header-controls-row .el-button {
  white-space: nowrap;
}
.composer-input :deep(.el-textarea__inner) {
  word-break: break-word;
  overflow-wrap: anywhere;
}
</style>
