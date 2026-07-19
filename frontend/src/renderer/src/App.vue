<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, computed, defineAsyncComponent } from 'vue'
import { storeToRefs } from 'pinia'
import { ElConfigProvider } from 'element-plus'
import enLocale from 'element-plus/es/locale/lang/en'
import zhLocale from 'element-plus/es/locale/lang/zh-cn'
import Dashboard from './views/Dashboard.vue'
import Editor from './views/Editor.vue'
import Header from './components/common/Header.vue'
import SettingsDialog from './components/common/SettingsDialog.vue'
import { useAppStore } from './stores/useAppStore'
import { useProjectStore } from './stores/useProjectStore'
import { useUpdateStore } from './stores/useUpdateStore'
import { useWorkflowStore } from './stores/useWorkflowStore'
import type { components } from '@renderer/types/generated'
import { schemaService } from './api/schema'

const IdeasHome = defineAsyncComponent(() => import('./views/IdeasHome.vue'))
const CodeWorkflowEditor = defineAsyncComponent(() => import('./views/workflow/CodeWorkflowEditor.vue'))
const WorkflowStatusBar = defineAsyncComponent(() => import('./components/workflow/WorkflowStatusBar.vue'))

type Project = components['schemas']['ProjectRead']

const appStore = useAppStore()
const projectStore = useProjectStore()
const updateStore = useUpdateStore()
const workflowStore = useWorkflowStore()

const { currentView, settingsDialogVisible, locale } = storeToRefs(appStore)
const { currentProject } = storeToRefs(projectStore)

const elLocale = computed(() => (locale.value === 'zh-CN' ? zhLocale : enLocale))

function handleProjectSelected(project: Project) {
  projectStore.setCurrentProject(project)
  appStore.goToEditor()
}

function handleBackToDashboard() {
  projectStore.reset()
  appStore.goToDashboard()
}

function handleOpenSettings() {
  appStore.openSettings()
}

function handleCloseSettings() {
  appStore.closeSettings()
}

const isNoHeader = computed(() => {
  const h = window.location.hash || ''
  return h.startsWith('#/ideas-home')
})

async function syncViewFromHash() {
  const hash = window.location.hash || ''
  if (hash.startsWith('#/ideas-home')) {
    appStore.goToIdeas()
    try { await projectStore.loadFreeProject() } catch {}
  }
  if (hash.startsWith('#/workflows')) {
    appStore.goToWorkflows()
  }
  if (hash.startsWith('#/code-workflows')) {
    appStore.goToCodeWorkflows()
  }
}

// Initialize theme and load global resources
onMounted(async () => {
  appStore.initTheme()
  schemaService.loadSchemas() // Load all schemas on app startup
  syncViewFromHash()
  window.addEventListener('hashchange', syncViewFromHash)
  
  // Set up workflow listener (listens for X-Workflows-Started in response headers)
  const cleanupWorkflowListener = workflowStore.setupWorkflowListener()
  
  // Clean up on component unmount
  onBeforeUnmount(() => {
    cleanupWorkflowListener()
  })
  
  // Auto-check for updates (if enabled)
  if (updateStore.autoCheckEnabled) {
    try {
      await updateStore.autoCheck()
    } catch (error) {
      // Fail silently so as not to disturb the user
      console.warn('Auto update check failed:', error)
    }
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('hashchange', syncViewFromHash)
})
</script>

<template>
  <el-config-provider :locale="elLocale">
    <div class="app-layout">
      <Header v-if="!isNoHeader" />
      <main class="main-content">
        <Dashboard v-if="currentView === 'dashboard'" @project-selected="handleProjectSelected" />
        <Editor
          v-else-if="currentView === 'editor' && currentProject"
          :initial-project="currentProject"
          @back-to-dashboard="handleBackToDashboard"
        />
        <IdeasHome v-else-if="currentView === 'ideas'" />
        <CodeWorkflowEditor v-else-if="currentView === 'workflows'" />
      </main>

      <SettingsDialog 
        v-model="settingsDialogVisible"
        @close="handleCloseSettings"
      />
      <WorkflowStatusBar />
    </div>
  </el-config-provider>
</template>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  background-color: var(--el-bg-color-page);
}

.main-content {
  flex-grow: 1;
  overflow: auto; /* Allow content to scroll if needed */
}
</style>
