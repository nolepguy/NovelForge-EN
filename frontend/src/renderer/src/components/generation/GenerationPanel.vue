<template>
  <div
    v-show="props.visible"
    ref="panelRef"
    class="generation-panel-float"
    :class="{ minimized: isMinimized }"
    :style="panelStyle"
  >
    <!-- Top title bar -->
    <div class="panel-header" @mousedown="handleDragStart">
      <div class="header-title">
        <el-icon class="title-icon"><MagicStick /></el-icon>
        <span>{{ t('generation.title') }}</span>
      </div>
      <div class="header-actions">
        <el-button
          :icon="isMinimized ? ArrowUp : ArrowDown"
          circle
          size="small"
          text
          @click.stop="toggleMinimize"
        />
        <el-button :icon="Close" circle size="small" text @click.stop="handleClose" />
      </div>
    </div>

    <!-- Message list (hidden when minimized) -->
    <div v-show="!isMinimized" ref="messagesContainer" class="messages-container">
      <div v-for="(msg, index) in messages" :key="index" class="message-item">
        <!-- Thinking message -->
        <div v-if="msg.type === 'thinking'" class="message-thinking">
          <el-icon class="message-icon"><ChatDotRound /></el-icon>
          <span class="message-text">{{ msg.content }}</span>
        </div>

        <!-- Instruction execution message -->
        <div v-else-if="msg.type === 'action'" class="message-action">
          <el-icon class="message-icon success"><Check /></el-icon>
          <span class="message-text">{{ msg.content }}</span>
        </div>

        <!-- User message -->
        <div v-else-if="msg.type === 'user'" class="message-user">
          <el-icon class="message-icon"><User /></el-icon>
          <span class="message-text">{{ msg.content }}</span>
        </div>

        <!-- Warning message -->
        <div v-else-if="msg.type === 'warning'" class="message-warning">
          <el-icon class="message-icon"><Warning /></el-icon>
          <span class="message-text">{{ msg.content }}</span>
        </div>

        <!-- Error message -->
        <div v-else-if="msg.type === 'error'" class="message-error">
          <el-icon class="message-icon"><CircleClose /></el-icon>
          <span class="message-text">{{ msg.content }}</span>
        </div>

        <!-- System message -->
        <div v-else-if="msg.type === 'system'" class="message-system">
          <el-icon class="message-icon"><InfoFilled /></el-icon>
          <span class="message-text">{{ msg.content }}</span>
        </div>
      </div>

      <!-- Generating indicator -->
      <div v-if="isGenerating && !isPaused" class="generating-indicator">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>{{ t('generation.generating') }}</span>
      </div>
    </div>

    <!-- Bottom control area (hidden when minimized) -->
    <div v-show="!isMinimized" class="panel-footer">
      <!-- Progress info -->
      <div v-if="completedFields > 0" class="progress-info">
        <el-icon><Check /></el-icon>
        <span>{{ t('generation.fieldsGenerated', { count: completedFields }) }}</span>
      </div>

      <!-- User input box -->
      <div class="input-area">
        <div class="custom-input-wrapper">
          <el-input
            v-model="userInput"
            :placeholder="
              isFinished
                ? t('generation.feedbackContinuePlaceholder')
                : isPaused
                  ? t('generation.feedbackResumePlaceholder')
                  : t('generation.guidancePlaceholder')
            "
            size="default"
            @keyup.enter="handleSendMessage"
          >
            <template #suffix>
              <el-button
                v-if="userInput.trim()"
                :icon="Promotion"
                link
                type="primary"
                @click="handleSendMessage"
              />
            </template>
          </el-input>
        </div>
      </div>

      <!-- Control buttons -->
      <div class="control-buttons">
        <!-- Generating / Paused -->
        <template v-if="!isFinished">
          <el-button v-if="isGenerating && !isPaused" :icon="VideoPause" round @click="handlePause">
            {{ t('generation.pause') }}
          </el-button>

          <el-button v-if="isPaused" :icon="VideoPlay" type="primary" round @click="handleContinue">
            {{ t('generation.continueGeneration') }}
          </el-button>

          <el-button :icon="CircleClose" text bg round type="danger" @click="handleStop">
            {{ t('generation.abort') }}
          </el-button>
        </template>

        <!-- After completion -->
        <template v-else>
          <el-button :icon="Check" type="primary" round @click="handleClose">
            {{ t('common.finish') }}
          </el-button>

          <el-button :icon="RefreshLeft" text bg round @click="handleRestart">
            {{ t('generation.restart') }}
          </el-button>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import {
  MagicStick,
  Close,
  ChatDotRound,
  Check,
  User,
  Warning,
  CircleClose,
  InfoFilled,
  Loading,
  VideoPause,
  VideoPlay,
  RefreshLeft,
  CircleCloseFilled,
  Promotion,
  ArrowUp,
  ArrowDown
} from '@element-plus/icons-vue'
import type { GenerationMessage } from '@renderer/types/instruction'
import { useI18n } from 'vue-i18n'

// ==================== Props & Emits ====================

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  close: []
  pause: []
  continue: [userMessage: string]
  stop: []
  restart: []
  finish: [] // newly added finish event
}>()

// ==================== State management ====================

const { t } = useI18n()

const isGenerating = ref(false)
const isPaused = ref(false)
const isFinishedState = ref(false) // explicit finished state
const messages = ref<GenerationMessage[]>([])
const completedFields = ref(0)
const userInput = ref('')
const messagesContainer = ref<HTMLElement>()
const panelRef = ref<HTMLElement>()

// Floating window state
const isMinimized = ref(false)
const position = ref({ x: 0, y: 0 })
const isDragging = ref(false)
const dragOffset = ref({ x: 0, y: 0 })

// Computed: whether it is in the finished state
const isFinished = computed(() => isFinishedState.value)

// Compute the panel style
const panelStyle = computed(() => {
  if (isMinimized.value) {
    return {
      left: `${position.value.x}px`,
      top: `${position.value.y}px`,
      height: 'auto'
    }
  }
  return {
    left: `${position.value.x}px`,
    top: `${position.value.y}px`
    // height is controlled by CSS max-height
  }
})

// ==================== Floating window control methods ====================

/**
 * Initialize the default position (bottom-right, with some margin)
 */
function initPosition() {
  const width = 360 // estimated width
  const height = 500 // estimated height
  const padding = 30

  position.value = {
    x: window.innerWidth - width - padding,
    y: window.innerHeight - height - padding
  }
}

function toggleMinimize() {
  isMinimized.value = !isMinimized.value
}

/**
 * Start dragging
 */
function handleDragStart(e: MouseEvent) {
  isDragging.value = true
  dragOffset.value = {
    x: e.clientX - position.value.x,
    y: e.clientY - position.value.y
  }

  document.addEventListener('mousemove', handleDragMove)
  document.addEventListener('mouseup', handleDragEnd)
  e.preventDefault()
}

/**
 * Dragging
 */
function handleDragMove(e: MouseEvent) {
  if (!isDragging.value) return

  // Compute the new position
  let newX = e.clientX - dragOffset.value.x
  let newY = e.clientY - dragOffset.value.y

  // Simple boundary check (prevent dragging too far off screen)
  const maxX = window.innerWidth - 50
  const maxY = window.innerHeight - 50

  if (newX < -300) newX = -300
  if (newX > maxX) newX = maxX
  if (newY < 0) newY = 0
  if (newY > maxY) newY = maxY

  position.value = { x: newX, y: newY }
}

/**
 * End dragging
 */
function handleDragEnd() {
  isDragging.value = false
  document.removeEventListener('mousemove', handleDragMove)
  document.removeEventListener('mouseup', handleDragEnd)
}

// ==================== Lifecycle ====================

onMounted(() => {
  // Initial position
  initPosition()
  window.addEventListener('resize', handleWindowResize)
})

onUnmounted(() => {
  document.removeEventListener('mousemove', handleDragMove)
  document.removeEventListener('mouseup', handleDragEnd)
  window.removeEventListener('resize', handleWindowResize)
})

function handleWindowResize() {
  // Simple adaptation: reset if it goes off screen
  if (position.value.x > window.innerWidth - 100 || position.value.y > window.innerHeight - 100) {
    initPosition()
  }
}

// ==================== Business logic methods ====================

/**
 * Add a message
 */
function addMessage(type: GenerationMessage['type'], content: string) {
  if (type === 'thinking' && messages.value.length > 0) {
    const lastMessage = messages.value[messages.value.length - 1]
    if (lastMessage.type === 'thinking') {
      lastMessage.content += content
      lastMessage.timestamp = Date.now()
      nextTick(scrollToBottom)
      return
    }
  }

  messages.value.push({
    type,
    content,
    timestamp: Date.now()
  })
  nextTick(scrollToBottom)
}

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

function handleClose() {
  emit('close')
}

function handlePause() {
  isPaused.value = true
  isGenerating.value = false // when paused, not considered generating
  addMessage('system', t('generation.paused'))
  emit('pause')
}

function handleContinue() {
  const message = userInput.value.trim()
  if (message) {
    addMessage('user', message)
  }
  userInput.value = ''

  isPaused.value = false
  isFinishedState.value = false
  isGenerating.value = true

  emit('continue', message || t('generation.pleaseContinue'))
}

function handleStop() {
  isGenerating.value = false
  isPaused.value = false
  isFinishedState.value = true // abort is also treated as a finished state
  addMessage('system', t('generation.aborted'))
  emit('stop')
}

function handleRestart() {
  reset()
  emit('restart')
}

function handleSendMessage() {
  if (!userInput.value.trim()) return

  if (isPaused.value || isFinishedState.value) {
    // When paused or (newly) finished, sending a message is treated as continuing generation
    handleContinue()
  } else if (isGenerating.value) {
    // Insert feedback during generation
    const msg = userInput.value.trim()
    addMessage('user', msg)
    userInput.value = ''
  }
}

function startGeneration() {
  reset()
  isGenerating.value = true
  addMessage('system', t('generation.starting'))
}

function finishGeneration(success: boolean, message?: string) {
  isGenerating.value = false
  isPaused.value = false
  isFinishedState.value = true // mark as finished

  if (success) {
    addMessage('system', message || t('generation.completed'))
  } else {
    addMessage('error', message || t('generation.generationFailed'))
  }
}

function incrementCompletedFields() {
  completedFields.value++
}

function reset() {
  messages.value = []
  isGenerating.value = false
  isPaused.value = false
  isFinishedState.value = false
  completedFields.value = 0
  userInput.value = ''
}

defineExpose({
  addMessage,
  startGeneration,
  finishGeneration,
  incrementCompletedFields,
  reset
})

watch(
  () => props.visible,
  (val) => {
    if (val) {
      // Check position each time it opens
      if (position.value.x === 0 && position.value.y === 0) {
        initPosition()
      }
    }
  }
)
</script>

<style scoped>
/* Floating window container - frosted glass style */
.generation-panel-float {
  position: fixed; /* global floating */
  width: 380px;
  max-height: 500px; /* fixed max height */
  display: flex;
  flex-direction: column;

  /* Frosted glass effect */
  background: rgba(255, 255, 255, 0.9); /* more opaque for contrast */
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);

  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 20px;
  box-shadow:
    0 16px 48px rgba(0, 0, 0, 0.12),
    0 8px 24px rgba(0, 0, 0, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.6);

  overflow: hidden;
  z-index: 9999; /* ensure on top layer */
  transition: opacity 0.2s;
}

/* Dark mode adaptation */
html.dark .generation-panel-float {
  /* Raise background brightness to distinguish from the dark editor background (usually #1e1e1e) */
  background: rgba(45, 45, 45, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.15); /* more visible border */
  box-shadow:
    0 20px 60px rgba(0, 0, 0, 0.6),
    0 8px 20px rgba(0, 0, 0, 0.4),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

.generation-panel-float.minimized {
  height: auto !important;
  max-height: 52px;
  overflow: hidden;
}

/* Top title bar */
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
  cursor: move; /* allow dragging */
  user-select: none;
  background: rgba(255, 255, 255, 0.5);
  flex-shrink: 0;
}

html.dark .panel-header {
  background: rgba(255, 255, 255, 0.05);
  border-bottom-color: rgba(255, 255, 255, 0.08);
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px; /* larger font size */
  font-weight: 800; /* bolder */
  /* Gradient text effect */
  background: linear-gradient(
    120deg,
    var(--el-text-color-primary) 0%,
    var(--el-color-primary) 100%
  );
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: var(--el-text-color-primary); /* fallback */

  letter-spacing: 0.5px;
  font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.title-icon {
  font-size: 20px;
  /* Add a bit of motion to the icon as well */
  filter: drop-shadow(0 2px 4px rgba(64, 158, 255, 0.3));
  color: var(--el-color-primary);
}

/* Message list */
.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 120px; /* minimum content height */
}

.message-item {
  animation: fadeSlideIn 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

@keyframes fadeSlideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Common message bubble styles */
.message-thinking,
.message-action,
.message-user,
.message-warning,
.message-error,
.message-system {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 12px;
  line-height: 1.6;
  font-size: 14px;
  position: relative;
}

.message-icon {
  margin-top: 3px;
  font-size: 16px;
  flex-shrink: 0;
}

.message-text {
  word-break: break-word;
  white-space: pre-wrap;
}

/* Thinking */
.message-thinking {
  background: rgba(240, 242, 245, 0.6);
  color: var(--el-text-color-regular);
  font-size: 13px;
}
html.dark .message-thinking {
  background: rgba(255, 255, 255, 0.05);
}
.message-thinking .message-icon {
  color: #909399;
}

/* Success / execution */
.message-action {
  background: rgba(225, 243, 216, 0.4);
  color: #67c23a;
}
html.dark .message-action {
  background: rgba(103, 194, 58, 0.15);
}

/* Error */
.message-error {
  background: rgba(254, 240, 240, 0.8);
  color: #f56c6c;
  border: 1px solid rgba(245, 108, 108, 0.2);
}
html.dark .message-error {
  background: rgba(245, 108, 108, 0.15);
  border-color: rgba(245, 108, 108, 0.3);
}

/* Warning */
.message-warning {
  background: rgba(253, 246, 236, 0.8);
  color: #e6a23c;
  border: 1px solid rgba(230, 162, 60, 0.2);
}
html.dark .message-warning {
  background: rgba(230, 162, 60, 0.15);
  border-color: rgba(230, 162, 60, 0.3);
}

/* User */
.message-user {
  align-self: flex-start; /* aligned left uniformly */
  background: rgba(236, 245, 255, 0.6);
  color: var(--el-text-color-primary);
  /* Use a pseudo-element for the left accent bar, with overflow: hidden to fit the rounded corners perfectly */
  position: relative;
  overflow: hidden;
  padding-left: 18px; /* add left padding to make room for the accent bar */
}

.message-user::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background-color: #409eff;
}

html.dark .message-user {
  background: rgba(64, 158, 255, 0.15);
}

/* System */
.message-system {
  background: transparent;
  justify-content: center;
  padding: 4px 0;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

/* Generating indicator */
.generating-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 8px;
  color: var(--el-color-primary);
  font-size: 13px;
}

/* Bottom control area */
.panel-footer {
  flex-shrink: 0; /* prevent the footer from being compressed */
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: rgba(255, 255, 255, 0.5);
  backdrop-filter: blur(10px);
  border-top: 1px solid rgba(0, 0, 0, 0.05);
}

html.dark .panel-footer {
  background: rgba(255, 255, 255, 0.03);
  border-top-color: rgba(255, 255, 255, 0.08);
}

.progress-info {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 12px;
  color: var(--el-color-success);
  font-weight: 500;
}

/* Input box beautification */
.custom-input-wrapper {
  transition: transform 0.2s;
}
.custom-input-wrapper:focus-within {
  transform: translateY(-2px);
}

:deep(.el-input__wrapper) {
  border-radius: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04) !important;
  border: 1px solid rgba(0, 0, 0, 0.05);
  padding-right: 8px;
  background-color: var(--el-fill-color-blank); /* explicitly set the background color */
}

/* Input box enhancement in dark mode */
html.dark :deep(.el-input__wrapper) {
  background-color: rgba(0, 0, 0, 0.3); /* dark translucent background */
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: none !important;
}

:deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.2) !important;
  border-color: var(--el-color-primary-light-5);
}

html.dark :deep(.el-input__wrapper.is-focus) {
  background-color: rgba(0, 0, 0, 0.5);
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 1px var(--el-color-primary) !important;
}

.control-buttons {
  display: flex;
  justify-content: center;
  gap: 12px;
}

.control-buttons .el-button {
  padding: 8px 20px;
  font-weight: 500;
  transition: all 0.2s;
}

.control-buttons .el-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

/* Scrollbar beautification */
.messages-container::-webkit-scrollbar {
  width: 4px;
}
.messages-container::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.1);
  border-radius: 2px;
}
html.dark .messages-container::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
}
/* i18n: english-length css fixes */

.control-buttons .el-button {
  white-space: nowrap;
}
.messages-container .message-text {
  word-break: break-word;
  overflow-wrap: anywhere;
}
</style>
