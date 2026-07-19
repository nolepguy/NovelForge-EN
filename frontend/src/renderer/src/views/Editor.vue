<template>
  <div class="editor-layout">
    <!-- Left card navigation tree -->
    <el-aside class="sidebar card-navigation-sidebar" :style="{ width: leftSidebarDisplayWidth + 'px' }" @contextmenu.prevent="onSidebarContextMenu">
      <div class="sidebar-header">
        <h3 class="sidebar-title">{{ t('editorPage.sidebarTitle') }}</h3>
        
      </div>

      <!-- Upper pane (type list + free card library) -->
      <div class="types-pane" :style="{ height: typesPaneHeight + 'px' }" @dragover.prevent @drop="onTypesPaneDrop">
        <div class="pane-title">{{ t('editorPage.existingCardTypes') }}</div>
        <el-scrollbar class="types-scroll">
          <ul class="types-list">
            <li v-for="t in cardStore.cardTypes" :key="t.id" class="type-item" draggable="true"
                @dragstart="onTypeDragStart(t)">
              <span class="type-name">{{ t.name }}</span>
            </li>
          </ul>
        </el-scrollbar>
      </div>
      <!-- Internal divider (vertical) -->
      <div class="inner-resizer" @mousedown="startResizingInner"></div>

      <!-- Lower pane: project card tree -->
      <div class="cards-pane" :style="{ height: `calc(100% - ${typesPaneHeight + innerResizerThickness}px)` }" @dragover.prevent @drop="onCardsPaneDrop">
        <div class="cards-title">
          <div class="cards-title-head">
            <div class="cards-title-text">{{ t('editorPage.currentProject', { name: projectStore.currentProject?.name }) }}</div>
            <div v-if="selectedCardIds.length > 0" class="cards-selection-chip">{{ t('editorPage.selectedCount', { count: selectedCardIds.length }) }}</div>
          </div>
          <div class="cards-title-actions">
            <el-button
              class="toolbar-action"
              :class="selectedCardIds.length > 0 ? 'toolbar-action-create-split' : 'toolbar-action-create-full'"
              size="small"
              type="primary"
              :icon="Plus"
              @click="openCreateRoot"
            >
              {{ t('editorPage.newCard') }}
            </el-button>
            <el-button
              v-if="selectedCardIds.length > 0"
              class="toolbar-action toolbar-action-danger toolbar-action-danger-split"
              size="small"
              type="danger"
              :icon="Delete"
              @click="batchDeleteCards"
            >
              {{ t('editorPage.deleteSelected', { count: selectedCardIds.length }) }}
            </el-button>
            <el-button v-if="!isFreeProject" class="toolbar-action toolbar-action-secondary" size="small" :icon="Upload" @click="openImportFreeCards">{{ t('editorPage.importCards') }}</el-button>
            <el-button class="toolbar-action toolbar-action-secondary" :class="{ 'toolbar-action-secondary--solo': isFreeProject }" size="small" :icon="Download" @click="openExportDialog">{{ t('editorPage.exportCards') }}</el-button>
          </div>
        </div>
        
        <!-- Search box -->
        <div class="search-box" style="padding: 0 8px 8px;">
           <el-input 
             v-model="searchQuery" 
             :placeholder="t('editorPage.searchCardsPlaceholder')" 
             :prefix-icon="Search"
             clearable
             @input="handleSearch"
           />
        </div>

        <!-- Search results -->
        <div v-if="isSearching" class="search-results-list" v-loading="searchLoading">
           <div 
             v-for="card in searchResults" 
             :key="card.id" 
             class="search-item" 
             @click="handleNodeClick({ id: card.id, title: card.title, card_type: card.card_type })"
           >
              <el-icon class="card-icon"><component :is="getIconByCardType(card.card_type?.name)" /></el-icon>
              <span class="search-item-title">{{ card.title }}</span>
           </div>
           <el-empty v-if="!searchLoading && searchResults.length === 0" :description="t('editorPage.noSearchResults')" :image-size="60" />
        </div>

        <template v-else>
          <el-tree
            v-if="groupedTree.length > 0"
            ref="treeRef"
            :data="groupedTree"
            node-key="id"
            :default-expanded-keys="expandedKeys"
            :expand-on-click-node="false"
            @node-click="handleNodeClick"
            @node-expand="onNodeExpand"
            @node-collapse="onNodeCollapse"
            draggable
            :allow-drop="handleAllowDrop"
            :allow-drag="handleAllowDrag"
            @node-drop="handleNodeDrop"
            class="card-tree"
          >
            <template #default="{ node, data }">
              <el-dropdown class="full-row-dropdown" trigger="contextmenu" @command="(cmd:string) => handleContextCommand(cmd, data)">
                <div 
                  class="custom-tree-node full-row" 
                  :class="{ 'selected': isCardSelected(data.id) }"
                  @click.stop="handleCardClick($event, data)"
                  @dragover.prevent 
                  @drop="(e:any) => onExternalDropToNode(e, data)" 
                  @dragenter.prevent
                >
                  <el-icon class="card-icon"> 
                    <component :is="getIconByCardType(data.card_type?.name || data.__groupType)" />
                  </el-icon>
                  <span class="label">{{ node.label || data.title }}</span>
                  <span v-if="data.children && data.children.length > 0" class="child-count">{{ data.children.length }}</span>
                </div>
                <template #dropdown>
                  <el-dropdown-menu>
                    <template v-if="!data.__isGroup">
                      <el-dropdown-item command="create-child" :disabled="selectedCardIds.length > 1">{{ t('editorPage.newChildCard') }}</el-dropdown-item>
                      <el-dropdown-item command="rename" :disabled="selectedCardIds.length > 1">{{ t('common.rename') }}</el-dropdown-item>
                      <el-dropdown-item command="edit-structure" :disabled="selectedCardIds.length > 1">{{ t('editorPage.editStructure') }}</el-dropdown-item>
                      <el-dropdown-item command="add-as-reference" :disabled="selectedCardIds.length > 1">{{ t('editorPage.addAsReference') }}</el-dropdown-item>
                      <el-dropdown-item v-if="selectedCardIds.length > 1" command="batch-delete" divided>{{ t('editorPage.deleteSelectedCards', { count: selectedCardIds.length }) }}</el-dropdown-item>
                      <el-dropdown-item v-else command="delete" divided>{{ t('editorPage.deleteCard') }}</el-dropdown-item>
                    </template>
                    <template v-else>
                      <el-dropdown-item command="create-child-in-group">{{ t('editorPage.newChildCard') }}</el-dropdown-item>
                      <el-dropdown-item command="delete-group" divided>{{ t('editorPage.deleteAllCardsInGroup') }}</el-dropdown-item>
                    </template>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </template>
          </el-tree>
          <el-empty v-else :description="t('editorPage.noCards')" :image-size="80"></el-empty>
        </template>
      </div>

      <!-- Blank area context menu (manually triggered) -->
      <span ref="blankMenuRef" class="blank-menu-ref" :style="{ position: 'fixed', left: blankMenuX + 'px', top: blankMenuY + 'px', width: '1px', height: '1px' }"></span>
      <el-dropdown v-model:visible="blankMenuVisible" trigger="manual">
        <span></span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item @click="openCreateRoot">{{ t('editorPage.newCard') }}</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </el-aside>
    
    <!-- Drag handle -->
    <div v-if="isLeftSidebarVisible" class="resizer left-resizer" @mousedown="startResizing('left')"></div>

    <!-- Center main content area -->
    <el-main class="main-content">
      <el-tabs v-model="activeTab" type="border-card" class="main-tabs">
        <el-tab-pane :label="t('editorPage.tabMarket')" name="market">
          <CardMarket @edit-card="handleEditCard" />
        </el-tab-pane>
        <el-tab-pane :label="t('editorPage.tabEditor')" name="editor">
          <template v-if="activeCard">
            <CardEditorHost :card="activeCard" :prefetched="prefetchedContext" />
          </template>
          <el-empty v-else :description="t('editorPage.selectCardToEdit')" />
        </el-tab-pane>
        <el-tab-pane :label="t('editorPage.tabRelationGraph')" name="relation-graph">
          <RelationGraphPanel :refresh-seq="relationGraphRefreshSeq" />
        </el-tab-pane>
      </el-tabs>
    </el-main>

    <!-- Right assistant panel divider and panel -->
    <div class="resizer right-resizer" @mousedown="startResizing('right')"></div>
    <el-aside class="sidebar assistant-sidebar" :style="{ width: rightSidebarWidth + 'px' }">
      <!-- Chapter text card: show 4 tabs -->
      <template v-if="showRightSidebarTabs">
        <el-tabs v-model="activeRightTab" type="card" class="right-tabs">
          <el-tab-pane :label="t('editorPage.tabAssistant')" name="assistant">
            <AssistantPanel
              :resolved-context="assistantResolvedContext"
              :llm-config-id="assistantParams.llm_config_id as any"
              :prompt-name="'Inspiration Dialogue'"
              :temperature="assistantParams.temperature as any"
              :max_tokens="assistantParams.max_tokens as any"
              :timeout="assistantParams.timeout as any"
              :effective-schema="assistantEffectiveSchema"
              :generation-prompt-name="assistantParams.prompt_name as any"
              :current-card-title="assistantSelectionCleared ? '' : (activeCard?.title as any)"
              :current-card-content="assistantSelectionCleared ? null : (activeCard?.content as any)"
              @refresh-context="refreshAssistantContext"
              @reset-selection="resetAssistantSelection"
              @finalize="assistantFinalize"
              @jump-to-card="handleJumpToCard"
            />
          </el-tab-pane>
          
          <template v-if="isChapterContent">
          <el-tab-pane :label="t('editorPage.tabParticipants')" name="context">
            <ContextPanel 
              :project-id="projectStore.currentProject?.id"
              :prefetched="prefetchedContext"
              :volume-number="chapterVolumeNumber"
              :chapter-number="chapterChapterNumber"
              :participants="chapterParticipants"
              @update:participants="handleContextParticipantsUpdate"
              @context-updated="handleContextAssembledUpdate"
            />
          </el-tab-pane>
          
          <el-tab-pane :label="t('editorPage.tabExtract')" name="extract">
            <ChapterToolsPanel />
          </el-tab-pane>
          
          <el-tab-pane :label="t('editorPage.tabOutline')" name="outline">
            <OutlinePanel 
              :active-card="activeCard"
              :volume-number="chapterVolumeNumber"
              :chapter-number="chapterChapterNumber"
            />
          </el-tab-pane>
          </template>
          
          <el-tab-pane :label="t('editorPage.tabReviewResult')" name="review-history">
            <ReviewHistoryPanel
              :target-card-id="reviewTargetCardIdForSidebar"
            />
          </el-tab-pane>
        </el-tabs>
      </template>
      
      <!-- Other cards: assistant only -->
      <AssistantPanel
        v-else
        :resolved-context="assistantResolvedContext"
        :llm-config-id="assistantParams.llm_config_id as any"
        :prompt-name="'Inspiration Dialogue'"
        :temperature="assistantParams.temperature as any"
        :max_tokens="assistantParams.max_tokens as any"
        :timeout="assistantParams.timeout as any"
        :effective-schema="assistantEffectiveSchema"
        :generation-prompt-name="assistantParams.prompt_name as any"
        :current-card-title="assistantSelectionCleared ? '' : (activeCard?.title as any)"
        :current-card-content="assistantSelectionCleared ? null : (activeCard?.content as any)"
        @refresh-context="refreshAssistantContext"
        @reset-selection="resetAssistantSelection"
        @finalize="assistantFinalize"
        @jump-to-card="handleJumpToCard"
      />
    </el-aside>
    <el-tooltip :content="isLeftSidebarVisible ? t('editorPage.collapseLeftNav') : t('editorPage.expandLeftNav')" placement="right">
      <button
        type="button"
        class="sidebar-edge-toggle"
        :class="{ 'is-collapsed': !isLeftSidebarVisible }"
        :style="{ left: `${leftSidebarToggleOffset}px` }"
        :aria-label="isLeftSidebarVisible ? t('editorPage.collapseLeftNav') : t('editorPage.expandLeftNav')"
        @click="toggleLeftSidebar"
      >
        <el-icon class="sidebar-edge-toggle__icon">
          <component :is="isLeftSidebarVisible ? ArrowLeft : ArrowRight" />
        </el-icon>
      </button>
    </el-tooltip>
  </div>

  <!-- New card dialog -->
  <el-dialog v-model="isCreateCardDialogVisible" :title="t('editorPage.newCardDialogTitle')" width="500px">
    <el-form :model="newCardForm" label-position="top">
      <el-form-item :label="t('editorPage.cardTitle')">
        <el-input v-model="newCardForm.title" :placeholder="t('editorPage.cardTitlePlaceholder')"></el-input>
      </el-form-item>
      <el-form-item :label="t('editorPage.cardType')">
        <el-select v-model="newCardForm.card_type_id" :placeholder="t('editorPage.cardTypePlaceholder')" style="width: 100%">
          <el-option
            v-for="type in cardStore.cardTypes"
            :key="type.id"
            :label="type.name"
            :value="type.id"
          ></el-option>
        </el-select>
      </el-form-item>
      <el-form-item :label="t('editorPage.parentCardOptional')">
                <el-tree-select
           v-model="newCardForm.parent_id"
           :data="cardTree"
           :props="treeSelectProps"
           check-strictly
           :render-after-expand="false"
           :placeholder="t('editorPage.selectParentCard')"
           clearable
           style="width: 100%"
         />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="isCreateCardDialogVisible = false">{{ t('common.cancel') }}</el-button>
      <el-button type="primary" @click="handleCreateCard">{{ t('common.create') }}</el-button>
    </template>
  </el-dialog>

  <!-- Import cards dialog -->
  <el-dialog v-model="importDialog.visible" :title="t('editorPage.importCards')" width="900px" class="nf-import-dialog">
    <div style="display:flex; gap:12px; align-items:center; margin-bottom:8px; flex-wrap: wrap;">
      <el-select v-model="importDialog.sourcePid" :placeholder="t('editorPage.sourceProject')" style="width:220px" @change="onImportSourceChange($event as any)">
        <el-option v-for="p in importDialog.projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-input v-model="importDialog.search" :placeholder="t('editorPage.searchSourceCards')" clearable style="flex:1; min-width: 200px" />
      <el-select v-model="importFilter.types" multiple collapse-tags :placeholder="t('editorPage.typeFilter')" style="min-width:220px;" :max-collapse-tags="2">
        <el-option v-for="t in cardStore.cardTypes" :key="t.id" :label="t.name" :value="t.id!" />
      </el-select>
      <el-tree-select
        v-model="importDialog.parentId"
        :data="cardTree"
        :props="treeSelectProps"
        check-strictly
        :render-after-expand="false"
        :placeholder="t('editorPage.targetParentOptional')"
        clearable
        popper-class="nf-tree-select-popper"
        style="width: 300px"
      />
    </div>
    <el-table :data="filteredImportCards" height="360px" border @selection-change="onImportSelectionChange">
      <el-table-column type="selection" width="48" />
      <el-table-column :label="t('common.title')" prop="title" min-width="220" />
      <el-table-column :label="t('common.type')" min-width="160">
        <template #default="{ row }">{{ row.card_type?.name }}</template>
      </el-table-column>
      <el-table-column :label="t('common.createdAt')" min-width="160">
        <template #default="{ row }">{{ (row as any).created_at }}</template>
      </el-table-column>
    </el-table>
    <template #footer>
      <el-button @click="importDialog.visible = false">{{ t('common.cancel') }}</el-button>
      <el-button type="primary" :disabled="!selectedImportIds.length" @click="confirmImportCards">{{ t('editorPage.importSelected') }}</el-button>
    </template>
  </el-dialog>

  <SchemaStudio v-model:visible="schemaStudio.visible" :mode="'card'" :target-id="schemaStudio.cardId" :context-title="schemaStudio.cardTitle" @saved="onCardSchemaSaved" />
  <CardExportDialog
    v-model="exportDialogVisible"
    :project-id="projectStore.currentProject?.id"
    :project-name="projectStore.currentProject?.name"
    :cards="cards as any"
    :card-types="cardStore.cardTypes as any"
    :initial-card-id="selectedCardIds.length === 1 ? selectedCardIds[0] : ((activeCard as any)?.id ?? null)"
  />

  
</template>

<script setup lang="ts">
import { ref, onMounted, reactive, defineAsyncComponent, onBeforeUnmount, computed, watch, nextTick } from 'vue'
import { storeToRefs } from 'pinia'
import { Plus, Search, Upload, Download, Delete, ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { debounce } from 'lodash-es'
import { useI18n } from 'vue-i18n'
import { 
  Box,
  CollectionTag,
  MagicStick,
  ChatLineRound,
  List,
  Connection,
  Tickets,
  Notebook,
  User,
  OfficeBuilding,
  Document,
  Folder,
} from '@element-plus/icons-vue'
import type { components } from '@renderer/types/generated'
import { useSidebarResizer } from '@renderer/composables/useSidebarResizer'
import AssistantPanel from '@renderer/components/assistants/AssistantPanel.vue'
import ContextPanel from '@renderer/components/panels/ContextPanel.vue'
import ChapterToolsPanel from '@renderer/components/panels/ChapterToolsPanel.vue'
import OutlinePanel from '@renderer/components/panels/OutlinePanel.vue'
import ReviewHistoryPanel from '@renderer/components/panels/ReviewHistoryPanel.vue'
import RelationGraphPanel from '@renderer/components/panels/RelationGraphPanel.vue'
import { useCardStore } from '@renderer/stores/useCardStore'
import { useEditorStore } from '@renderer/stores/useEditorStore'
import { useProjectStore } from '@renderer/stores/useProjectStore'
import { useAssistantStore } from '@renderer/stores/useAssistantStore'
import SchemaStudio from '@renderer/components/shared/SchemaStudio.vue'
import { getCardSchema, createCardType } from '@renderer/api/setting'
import { getProjects } from '@renderer/api/projects'
import { getCardsForProject, copyCard, getCardAIParams, searchCards } from '@renderer/api/cards'
import { generateAIContent } from '@renderer/api/ai'
import type { AssistantRef, ChapterExcerptRef, ReviewResultRef } from '@renderer/api/ai'
 
 // Mock components that will be created later
 const CardEditorHost = defineAsyncComponent(() => import('@renderer/components/cards/CardEditorHost.vue'));
 const CardMarket = defineAsyncComponent(() => import('@renderer/components/cards/CardMarket.vue'));
 const CardExportDialog = defineAsyncComponent(() => import('@renderer/components/cards/CardExportDialog.vue'));


 type Project = components['schemas']['ProjectRead']
 type CardRead = components['schemas']['CardRead']
 type CardCreate = components['schemas']['CardCreate']
const { t } = useI18n()

 // Import cards dialog state
 const importDialog = ref<{ visible: boolean; search: string; parentId: number | null; sourcePid: number | null; projects: Array<{id:number; name:string}> }>({ visible: false, search: '', parentId: null, sourcePid: null, projects: [] })
 const importSourceCards = ref<CardRead[]>([])
 const selectedImportIds = ref<number[]>([])
 
 // Filter: type + title
 const importFilter = ref<{ types: number[] }>({ types: [] })
 
 const filteredImportCards = computed(() => {
   const q = (importDialog.value.search || '').trim().toLowerCase()
   let list = importSourceCards.value || []
   if (importFilter.value.types.length) {
     const typeSet = new Set(importFilter.value.types)
     list = list.filter(c => c.card_type?.id && typeSet.has(c.card_type.id))
   }
   if (q) {
     list = list.filter(c => (c.title || '').toLowerCase().includes(q))
   }
   return list
 })

async function openImportFreeCards() {
  try {
    const list = await getProjects()
    const currentId = projectStore.currentProject?.id
     importDialog.value.projects = (list || []).filter(p => p.id !== currentId).map(p => ({ id: p.id!, name: p.name! }))
     importDialog.value.sourcePid = importDialog.value.projects[0]?.id ?? null
     selectedImportIds.value = []
     await onImportSourceChange(importDialog.value.sourcePid as any)
     importDialog.value.visible = true
   } catch { ElMessage.error(t('editorPage.loadSourceProjectsFailed')) }
 }

function openExportDialog() {
  if (!projectStore.currentProject?.id) {
    ElMessage.warning(t('editorPage.selectProjectFirst'))
    return
  }
  if ((cards.value || []).length === 0) {
    ElMessage.warning(t('editorPage.noCardsToExport'))
    return
  }
  exportDialogVisible.value = true
}

 async function onImportSourceChange(pid: number | null) {
   importSourceCards.value = []
   if (!pid) return
   try { importSourceCards.value = await getCardsForProject(pid) } catch { importSourceCards.value = [] }
 }

 function onImportSelectionChange(rows: any[]) {
   selectedImportIds.value = (rows || []).map(r => Number(r.id)).filter(n => Number.isFinite(n))
 }

 async function confirmImportCards() {
   try {
     const pid = projectStore.currentProject?.id
     if (!pid) return
     const targetParent = importDialog.value.parentId || null
     for (const id of selectedImportIds.value) {
       await copyCard(id, { target_project_id: pid, parent_id: targetParent as any })
     }
     await cardStore.fetchCards(pid)
     ElMessage.success(t('editorPage.importedSelectedCards'))
     importDialog.value.visible = false
   } catch { ElMessage.error(t('editorPage.importFailed')) }
 }

 // Props
 const props = defineProps<{
   initialProject: Project
 }>()

 // Store
 const cardStore = useCardStore()
 const { cardTree, activeCard, cards } = storeToRefs(cardStore)
 const editorStore = useEditorStore()
 const { expandedKeys } = storeToRefs(editorStore)
 const projectStore = useProjectStore()
 const assistantStore = useAssistantStore()
 const isFreeProject = computed(() => (projectStore.currentProject?.name || '') === '__free__')

  // --- Frontend auto-grouper ---
  // When a node's direct child cards contain any "type count > 2", create a virtual group node for that type;
  // Other types with count <= 2 are displayed as-is (even if a parent has only one type, as long as its count > 2 it is grouped).
  // This structure is entirely frontend-side and does not affect backend data
 interface TreeNode { id: number | string; title: string; children?: TreeNode[]; card_type?: { name: string }; __isGroup?: boolean; __groupType?: string }


 function buildGroupedNodes(nodes: any[]): any[] {
  return nodes.map(n => {
    const node: TreeNode = { ...n }
    // Group nodes do not participate in grouping logic, recurse into their children directly
    if ((n as any).__isGroup) {
      if (Array.isArray(n.children) && n.children.length > 0) {
        node.children = buildGroupedNodes(n.children as any)
      }
      return node
    }
    if (Array.isArray(n.children) && n.children.length > 0) {
      // Count child node types
      const byType: Record<string, any[]> = {}
      n.children.forEach((c: any) => {
        const typeName = c.card_type?.name || t('editorPage.unknownType')
        if (!byType[typeName]) byType[typeName] = []
        byType[typeName].push(c)
      })
      const types = Object.keys(byType)
        const grouped: any[] = []
        types.forEach(t => {
          const list = byType[t]
        if (list.length > 2) {
            // Create virtual group node (id uses a string to avoid conflicts)
            grouped.push({
              id: `group:${n.id}:${t}`,
              title: `${t}`,
              __isGroup: true,
              __groupType: t,
              __parentCardId: n.id,  // Keep actual parent card ID
              children: list.map(x => ({ ...x }))
            })
          } else {
          // Count is 1 or 2, flatten directly
          grouped.push(...list)
          }
        })
      // Recurse into subtrees (group nodes and normal nodes both recurse their children)
      node.children = grouped.map((x: any) => {
        const copy = { ...x }
        if (Array.isArray(copy.children) && copy.children.length > 0) {
          copy.children = buildGroupedNodes(copy.children as any)
        }
        return copy
      })
    }
    return node
  })
}

// Compute the grouped tree based on the raw cardTree
const groupedTree = computed(() => buildGroupedNodes(cardTree.value as unknown as any[]))

// Local State
const activeTab = ref('market')
const relationGraphRefreshSeq = ref(0)
const activeRightTab = ref('assistant')
const isCreateCardDialogVisible = ref(false)
const exportDialogVisible = ref(false)
const prefetchedContext = ref<any>(null)
const newCardForm = reactive<Partial<CardCreate>>({
  title: '',
  card_type_id: undefined,
  parent_id: '' as any
})

// Card multi-select state
const selectedCardIds = ref<number[]>([])
const lastSelectedCardId = ref<number | null>(null)

// Blank area menu state
const blankMenuVisible = ref(false)
const blankMenuX = ref(0)
const blankMenuY = ref(0)
const blankMenuRef = ref<HTMLElement | null>(null)

// Search State
const searchQuery = ref('')
const searchResults = ref<CardRead[]>([])
const isSearching = computed(() => searchQuery.value.trim().length > 0)
const searchLoading = ref(false)

const handleSearch = debounce(async (query: string) => {
  if (!query.trim()) {
    searchResults.value = []
    return
  }
  searchLoading.value = true
  try {
    const pid = projectStore.currentProject?.id
    if (pid) {
      searchResults.value = await searchCards(pid, query)
    }
  } catch (e) {
    console.error(e)
  } finally {
    searchLoading.value = false
  }
}, 300)

// Composables
const { leftSidebarWidth, rightSidebarWidth, startResizing } = useSidebarResizer()
const isLeftSidebarVisible = ref(true)
const leftSidebarDisplayWidth = computed(() => (isLeftSidebarVisible.value ? leftSidebarWidth.value : 0))
const leftSidebarToggleOffset = computed(() => (isLeftSidebarVisible.value ? Math.max(leftSidebarDisplayWidth.value - 18, 8) : 10))

function toggleLeftSidebar() {
  isLeftSidebarVisible.value = !isLeftSidebarVisible.value
}
  
 // Unify TreeSelect style/props to ensure options are visible
 const treeSelectProps = {
   value: 'id',
   label: 'title',
   children: 'children'
 } as const
 
 // Internal vertical split: type/card height
  const typesPaneHeight = ref(180)
  const innerResizerThickness = 6
  // Left width drag uses useSidebarResizer.startResizing('left')

 function startResizingInner() {
   const startY = (event as MouseEvent).clientY
   const startH = typesPaneHeight.value
   const onMove = (e: MouseEvent) => {
     const dy = e.clientY - startY
     const next = Math.max(120, Math.min(startH + dy, 400))
     typesPaneHeight.value = next
   }
   const onUp = () => {
     window.removeEventListener('mousemove', onMove)
     window.removeEventListener('mouseup', onUp)
   }
   window.addEventListener('mousemove', onMove)
   window.addEventListener('mouseup', onUp)
 }

// Drag: from type to card area to create a new instance
function onTypeDragStart(t: any) {
  try { (event as DragEvent).dataTransfer?.setData('application/x-card-type-id', String(t.id)) } catch {}
}
async function onCardsPaneDrop(e: DragEvent) {
 try {
   const typeId = e.dataTransfer?.getData('application/x-card-type-id')
   if (typeId) {
      // Drag from type list to blank area, create new card at root
     newCardForm.title = (cardStore.cardTypes.find(ct => ct.id === Number(typeId))?.name || t('editorPage.newCardDefault'))
     newCardForm.card_type_id = Number(typeId)
     newCardForm.parent_id = '' as any
     handleCreateCard()
     return
   }
    // Cross-project drag copy from __free__ project to blank area
   const freeCardId = e.dataTransfer?.getData('application/x-free-card-id')
   if (freeCardId) {
     await copyCard(Number(freeCardId), { target_project_id: projectStore.currentProject!.id, parent_id: null as any })
     await cardStore.fetchCards(projectStore.currentProject!.id)
     ElMessage.success(t('editorPage.freeCardCopiedToRoot'))
     return
   }
    // Note: in-project card dragging is now handled by el-tree's native drag (handleNodeDrop)
 } catch {}
}

// Promote a card instance to a type: drop on the upper pane
async function onTypesPaneDrop(e: DragEvent) {
 try {
   const cardIdStr = e.dataTransfer?.getData('application/x-card-id')
   const cardId = cardIdStr ? Number(cardIdStr) : NaN
   if (!cardId || Number.isNaN(cardId)) return
    // Read the card's effective schema
   const resp = await getCardSchema(cardId)
   const effective = resp?.effective_schema || resp?.json_schema
   if (!effective) { ElMessage.warning(t('editorPage.noStructureForType')); return }
    // Default name: card title or "new type"
   const old = cards.value.find(c => (c as any).id === cardId)
   const defaultName = (old?.title || t('editorPage.newType')) as string
   const { value } = await ElMessageBox.prompt(t('editorPage.createTypeFromInstancePrompt'), t('editorPage.createCardTypeTitle'), {
     inputValue: defaultName,
     confirmButtonText: t('common.create'),
     cancelButtonText: t('common.cancel'),
     inputValidator: (v:string) => v.trim().length > 0 || t('editorPage.nameCannotBeEmpty')
   })
   const finalName = String(value).trim()
   await createCardType({ name: finalName, description: t('editorPage.defaultTypeDescription', { name: finalName }), json_schema: effective } as any)
   ElMessage.success(t('editorPage.typeCreatedFromInstance'))
   await cardStore.fetchCardTypes()
 } catch (err) {
    // User cancelled or error ignored
 }
}

// ===== el-tree native drag feature =====

// Control which nodes can be dragged
function handleAllowDrag(draggingNode: any): boolean {
  // Group nodes cannot be dragged
  if (draggingNode.data.__isGroup) {
    return false
  }
  return true
}

// Control drop position
// type: 'prev' | 'inner' | 'next' means drop before/inside/after the target node
function handleAllowDrop(draggingNode: any, dropNode: any, type: 'prev' | 'inner' | 'next'): boolean {
  // Group nodes only allow being an "inner" target (i.e. dropping a card into the group)
  if (dropNode.data.__isGroup) {
    return type === 'inner'
  }

  // Normal card nodes allow all drop positions
  return true
}

// Handle drag completion
async function handleNodeDrop(
  draggingNode: any,
  dropNode: any,
  dropType: 'before' | 'after' | 'inner',
  ev: DragEvent
) {
  try {
    const draggedCard = draggingNode.data
    const targetCard = dropNode.data
    
    // If dropped into a group, set parent_id to null (root level)
    if (targetCard.__isGroup && dropType === 'inner') {
      // Compute the next display_order at root level
      const rootCards = cards.value.filter(c => c.parent_id === null)
      const maxOrder = rootCards.length > 0 ? Math.max(...rootCards.map(c => c.display_order || 0)) : -1
      
      await cardStore.modifyCard(draggedCard.id, { 
        parent_id: null,
        display_order: maxOrder + 1
      }, { skipHooks: true })
      ElMessage.success(t('editorPage.movedToRoot', { title: draggedCard.title }))
      await cardStore.fetchCards(projectStore.currentProject!.id)
      
      // Record move operation (including hierarchy change info)
      assistantStore.recordOperation(projectStore.currentProject!.id, {
        type: 'move',
        cardId: draggedCard.id,
        cardTitle: draggedCard.title,
        cardType: draggedCard.card_type?.name || 'Unknown',
        detail: t('editorPage.movedFromChildToRoot')
      })
      
      // Update project structure
      updateProjectStructureContext(activeCard.value?.id)
      return
    }
    
    // If dropped inside a card (becomes a child card)
    if (dropType === 'inner') {
      // Compute the next display_order of the target card's children
      const children = cards.value.filter(c => c.parent_id === targetCard.id)
      const maxOrder = children.length > 0 ? Math.max(...children.map(c => c.display_order || 0)) : -1
      
      await cardStore.modifyCard(draggedCard.id, { 
        parent_id: targetCard.id,
        display_order: maxOrder + 1
      }, { skipHooks: true })
      ElMessage.success(t('editorPage.setAsChild', { dragged: draggedCard.title, target: targetCard.title }))
      await cardStore.fetchCards(projectStore.currentProject!.id)
      
      // Record move operation (including hierarchy change info)
      assistantStore.recordOperation(projectStore.currentProject!.id, {
        type: 'move',
        cardId: draggedCard.id,
        cardTitle: draggedCard.title,
        cardType: draggedCard.card_type?.name || 'Unknown',
        detail: t('editorPage.setAsChildDetail', { title: targetCard.title, type: targetCard.card_type?.name || 'Unknown', id: targetCard.id })
      })
      
      // Update project structure
      updateProjectStructureContext(activeCard.value?.id)
      return
    }
    
    // If dropped before/after a card (sibling reordering)
    const newParentId = targetCard.parent_id || null
    
    // Get all sibling cards sorted by display_order (excluding the dragged card)
    const siblings = cards.value
      .filter(c => (c.parent_id || null) === newParentId && c.id !== draggedCard.id)
      .sort((a, b) => (a.display_order || 0) - (b.display_order || 0))
    
    // Find the target card's position among siblings
    const targetIndex = siblings.findIndex(c => c.id === targetCard.id)
    
    // Build the new order array (insert the dragged card)
    let newSiblings = [...siblings]
    if (dropType === 'before') {
      // Insert before the target card
      newSiblings.splice(targetIndex, 0, draggedCard)
    } else {
      // Insert after the target card
      newSiblings.splice(targetIndex + 1, 0, draggedCard)
    }
    
    // Batch update display_order of all affected cards (using batch API)
    const updates: Array<{ card_id: number; display_order: number; parent_id?: number | null }> = []
    
    newSiblings.forEach((card, index) => {
      if (card.id === draggedCard.id) {
        // The dragged card needs both parent_id and display_order updated
        updates.push({
          card_id: card.id,
          display_order: index,
          parent_id: newParentId
        })
      } else if (card.display_order !== index) {
        // Other cards only need display_order updated (if changed)
        // ⚠️ Important: parent_id must be passed, otherwise the backend would incorrectly set it to null!
        updates.push({
          card_id: card.id,
          display_order: index,
          parent_id: card.parent_id || null  // Keep original parent_id
        })
      }
    })
    
    // Call batch update API
    if (updates.length > 0) {
      const { batchReorderCards } = await import('@renderer/api/cards')
      await batchReorderCards({ updates })
    }
    
    ElMessage.success(t('editorPage.positionAdjusted', { title: draggedCard.title }))
    await cardStore.fetchCards(projectStore.currentProject!.id)
    
    // Record move operation (including position and parent info)
    const targetCardTitle = targetCard?.title || t('editorPage.root')
    const positionText = dropType === 'before' ? t('editorPage.positionBefore') : t('editorPage.positionAfter')
    let moveDetail = t('editorPage.movedTo', { title: targetCardTitle, position: positionText })
    
    // If the parent changed, note it specifically
    if (draggedCard.parent_id !== newParentId) {
      // Optimization: build a Map to avoid repeated find (only when parent changed)
      const cardMap = new Map(cards.value.map(c => [(c as any).id, c.title]))
      const oldParentName = draggedCard.parent_id 
        ? cardMap.get(draggedCard.parent_id) || t('common.unknown') 
        : t('editorPage.root')
      const newParentName = newParentId 
        ? cardMap.get(newParentId) || t('common.unknown') 
        : t('editorPage.root')
      moveDetail +=  t('editorPage.movedFromTo', { old: oldParentName, new: newParentName })
    }
    
    assistantStore.recordOperation(projectStore.currentProject!.id, {
      type: 'move',
      cardId: draggedCard.id,
      cardTitle: draggedCard.title,
      cardType: draggedCard.card_type?.name || 'Unknown',
      detail: moveDetail
    })
    
    // Update project structure immediately so the inspiration assistant perceives hierarchy changes
    updateProjectStructureContext(activeCard.value?.id)
    
  } catch (err: any) {
    console.error('Drag failed:', err)
    ElMessage.error(err?.message || t('editorPage.dragFailed'))
    // Refresh to restore state
    await cardStore.fetchCards(projectStore.currentProject!.id)
    // Update structure even on failure
    updateProjectStructureContext(activeCard.value?.id)
  }
}

// --- Drag: from external (type list, free cards) to card tree ---
// Note: in-tree card dragging is handled by handleNodeDrop, here we only handle external drops

function getDraggedTypeId(e: DragEvent): number | null {
 try {
   const raw = e.dataTransfer?.getData('application/x-card-type-id') || ''
   const n = Number(raw)
   return Number.isFinite(n) && n > 0 ? n : null
 } catch { return null }
}

async function onExternalDropToNode(e: DragEvent, nodeData: any) {
 // Only handle drags from the type list or cross-project, not in-tree card drags
  const typeId = getDraggedTypeId(e)
  if (typeId) {
    // Drag from type list to create a new card
   if (nodeData?.__isGroup) return
   const newCard = await cardStore.addCard({ title: t('editorPage.newCard'), card_type_id: typeId, parent_id: nodeData?.id } as any)
   
    //  Record create operation
   if (newCard && projectStore.currentProject?.id) {
     const cardType = cardStore.cardTypes.find(ct => ct.id === typeId)
     assistantStore.recordOperation(projectStore.currentProject.id, {
       type: 'create',
       cardId: (newCard as any).id,
       cardTitle: newCard.title,
       cardType: cardType?.name || 'Unknown'
     })
   }
   
   return
 }
 
 try {
    // Handle cross-project drag copy from __free__
   const freeCardId = e.dataTransfer?.getData('application/x-free-card-id')
   if (freeCardId) {
     if (nodeData?.__isGroup) return
     await copyCard(Number(freeCardId), { target_project_id: projectStore.currentProject!.id, parent_id: Number(nodeData?.id) })
     await cardStore.fetchCards(projectStore.currentProject!.id)
     ElMessage.success(t('editorPage.freeCardCopiedToNode'))
     return
   }
 } catch (err) {
    console.error('External drag failed:', err)
 }
}

 // --- Methods ---

// Click behavior does not open editing for "group nodes", only expand/collapse. Actual cards trigger editing.
function handleNodeClick(data: any) {
  if (data.__isGroup) return
  
  // Ensure the clicked card is selected (for UI highlight), overriding the clearing in handleCardClick
  selectedCardIds.value = [data.id]
  lastSelectedCardId.value = data.id

  // Chapter text is now also opened in the center editor
  cardStore.setActiveCard(data.id)
  assistantSelectionCleared.value = false
  activeTab.value = 'editor'
  try {
    const pid = projectStore.currentProject?.id as number
    const pname = projectStore.currentProject?.name || ''
    const full = (cards.value || []).find((c:any) => c.id === data.id)
    const title = (full?.title || data.title || '') as string
    const content = (full?.content || (data as any).content || {})
    if (pid && data?.id) {
      // Only append auto refs: store rules keep existing manual refs, they won't be overwritten by auto
      assistantStore.addAutoRef({
        refType: 'card',
        projectId: pid,
        projectName: pname,
        cardId: data.id,
        cardTitle: title,
        content,
      })
    }
  } catch {}
}

// Card click handler (supports multi-select)
function handleCardClick(event: MouseEvent, data: any) {
  // Group nodes do not support multi-select
  if (data.__isGroup) {
    handleNodeClick(data)
    return
  }
  
  const cardId = data.id
  
  // Ctrl key: toggle multi-select
  if (event.ctrlKey || event.metaKey) {
    const index = selectedCardIds.value.indexOf(cardId)
    if (index > -1) {
      // Deselect
      selectedCardIds.value.splice(index, 1)
    } else {
      // Add to selection
      selectedCardIds.value.push(cardId)
    }
    lastSelectedCardId.value = cardId
    event.stopPropagation()
    return
  }
  
  // Shift key: continuous multi-select
  if (event.shiftKey && lastSelectedCardId.value !== null) {
    // Get all visible card IDs (flatten the tree structure)
    const flatCards: number[] = []
    function flattenTree(nodes: any[]) {
      for (const node of nodes) {
        if (!node.__isGroup && node.id) {
          flatCards.push(node.id)
        }
        if (node.children && node.children.length > 0) {
          flattenTree(node.children)
        }
      }
    }
    flattenTree(groupedTree.value)
    
    // Find start and end positions
    const startIndex = flatCards.indexOf(lastSelectedCardId.value)
    const endIndex = flatCards.indexOf(cardId)
    
    if (startIndex !== -1 && endIndex !== -1) {
      const minIndex = Math.min(startIndex, endIndex)
      const maxIndex = Math.max(startIndex, endIndex)
      
      // Select all cards within the range
      selectedCardIds.value = flatCards.slice(minIndex, maxIndex + 1)
    }
    
    event.stopPropagation()
    return
  }
  
  // Normal click: delegate to handleNodeClick for selection and activation
  handleNodeClick(data)
}

// Check whether a card is selected
function isCardSelected(cardId: number): boolean {
  return selectedCardIds.value.includes(cardId)
}

// Batch delete cards
async function batchDeleteCards() {
  if (selectedCardIds.value.length === 0) {
    ElMessage.warning(t('editorPage.selectCardsToDeleteFirst'))
    return
  }
  
  try {
    await ElMessageBox.confirm(
      t('editorPage.batchDeleteConfirm', { count: selectedCardIds.value.length }),
      t('editorPage.batchDeleteTitle'),
      { type: 'warning' }
    )
    
    // Record deleted card info
    const deletedCards = selectedCardIds.value.map(id => {
      const card = cards.value.find(c => (c as any).id === id)
      return {
        id,
        title: card?.title || t('common.unknown'),
        cardType: (card as any)?.card_type?.name || 'Unknown'
      }
    })
    
    // If the currently active card is in the delete list, clear active state first
    if (activeCard.value && selectedCardIds.value.includes((activeCard.value as any).id)) {
      cardStore.setActiveCard(null as any)
    }
    
    // Optimization: filter out child cards that will be cascade-deleted
    // Only delete top-level cards (i.e. cards that are not descendants of other selected cards)
    const selectedSet = new Set(selectedCardIds.value)
    const cardsToDelete: number[] = []
    
    // Check whether a card is a descendant of another selected card
    function isDescendantOfSelected(cardId: number): boolean {
      const card = cards.value.find(c => (c as any).id === cardId)
      if (!card) return false
      
      let parentId = (card as any).parent_id
      while (parentId) {
        if (selectedSet.has(parentId)) {
          return true  // Is a descendant of a selected card
        }
        const parent = cards.value.find(c => (c as any).id === parentId)
        if (!parent) break
        parentId = (parent as any).parent_id
      }
      return false
    }
    
    // Keep only top-level cards (not descendants of other selected cards)
    for (const cardId of selectedCardIds.value) {
      if (!isDescendantOfSelected(cardId)) {
        cardsToDelete.push(cardId)
      }
    }
    
    // Batch delete (only delete top-level cards, child cards are cascade-deleted by the backend)
    let successCount = 0
    for (const cardId of cardsToDelete) {
      try {
        await cardStore.removeCard(cardId)
        successCount++
      } catch (error: any) {
        console.error(`Failed to delete card ${cardId}:`, error)
        ElMessage.error(t('editorPage.deleteCardFailedMsg', { msg: error.message || t('editorPage.unknownError') }))
      }
    }
    
    // Record delete operation (record all selected cards, including cascade-deleted ones)
    if (projectStore.currentProject?.id) {
      for (const card of deletedCards) {
        assistantStore.recordOperation(projectStore.currentProject.id, {
          type: 'delete',
          cardId: card.id,
          cardTitle: card.title,
          cardType: card.cardType
        })
      }
    }
    
    // Clear selection state
    selectedCardIds.value = []
    lastSelectedCardId.value = null
    
    ElMessage.success(t('editorPage.deletedCards', { count: selectedCardIds.value.length || deletedCards.length }))
  } catch (e) {
    // User cancelled
  }
}

// Fallback: also auto-inject once when activeCard changes
watch(activeCard, (c) => {
 try {
   if (!c) return
   const pid = projectStore.currentProject?.id as number
   const pname = projectStore.currentProject?.name || ''
  assistantStore.addAutoRef({
    refType: 'card',
    projectId: pid,
    projectName: pname,
    cardId: (c as any).id,
    cardTitle: (c as any).title || '',
    content: (c as any).content || {},
  })
   
   //  Update card context (used by inspiration assistant tool calls)
   assistantStore.updateActiveCard(c as any, pid)
   
   //  Update project structure (when the current card changes)
   updateProjectStructureContext((c as any)?.id)
 } catch (err) {
   console.error('🔄 [Editor] Failed to update card context:', err)
 }
})

//  Watch project switch, initialize structure and operation history
watch(() => projectStore.currentProject, (newProject) => {
  if (!newProject?.id) return
  
  // Reset search when switching projects
  searchQuery.value = ''
  searchResults.value = []

  try {
    // Load operation history
    assistantStore.loadOperations(newProject.id)
    
    // Update card type list
    assistantStore.updateProjectCardTypes(cardStore.cardTypes.map(ct => ct.name))
    
    // Build project structure
    updateProjectStructureContext(activeCard.value?.id)
  } catch (err) {
    console.error('📦 [Editor] Failed to initialize assistant context:', err)
  }
}, { immediate: true })

//  Watch card count changes (add/delete), auto-update project structure
// Optimization: only watch count changes, hierarchy changes are triggered manually by drag operations
watch(() => cards.value.length, () => {
  try {
    updateProjectStructureContext(activeCard.value?.id)
  } catch (err) {
    console.error('🔄 [Editor] Failed to update project structure:', err)
  }
})

//  Unified function to update project structure
function updateProjectStructureContext(currentCardId?: number) {
  const project = projectStore.currentProject
  if (!project?.id) return
  
  assistantStore.updateProjectStructure(
    project.id,
    project.name,
    cards.value,
    cardStore.cardTypes,
    currentCardId
  )
}

function onNodeExpand(_: any, node: any) {
  editorStore.addExpandedKey(String(node.key))
}

function onNodeCollapse(_: any, node: any) {
  // Recursively remove the expanded state of this node and all its descendants
  // This prevents a child node from triggering the parent to auto-expand on data refresh
  const removeRecursively = (n: any) => {
    if (n.key) {
      editorStore.removeExpandedKey(String(n.key))
    }
    if (n.childNodes && n.childNodes.length > 0) {
      n.childNodes.forEach((child: any) => removeRecursively(child))
    }
  }
  removeRecursively(node)
}

function handleEditCard(cardId: number) {
  cardStore.setActiveCard(cardId);
  activeTab.value = 'editor';
}

async function handleCreateCard() {
  if (!newCardForm.title || !newCardForm.card_type_id) {
    ElMessage.warning(t('editorPage.fillTitleAndType'));
    return;
  }
  const payload: any = {
    ...newCardForm,
    parent_id: (newCardForm as any).parent_id === '' ? undefined : (newCardForm as any).parent_id
  }
  const newCard = await cardStore.addCard(payload as CardCreate);
  
  //  Record create operation
  if (newCard && projectStore.currentProject?.id) {
    const cardType = cardStore.cardTypes.find(ct => ct.id === newCardForm.card_type_id)
    assistantStore.recordOperation(projectStore.currentProject.id, {
      type: 'create',
      cardId: (newCard as any).id,
      cardTitle: newCard.title,
      cardType: cardType?.name || 'Unknown'
    })
  }
  
  isCreateCardDialogVisible.value = false;
  // Reset form
  Object.assign(newCardForm, { title: '', card_type_id: undefined, parent_id: '' as any });
}

// Return the icon component based on card type
function getIconByCardType(typeName?: string) {
  // Convention: if backend default type names change, adjust them in this mapping
  switch (typeName) {
    case 'Work Tags':
      return CollectionTag
    case 'Special Ability':
      return MagicStick
    case 'One Sentence Summary':
      return ChatLineRound
    case 'Story Outline':
      return List
    case 'Worldview Setting':
      return Connection
    case 'Core Blueprint':
      return Tickets
    case 'Volume Outline':
      return Notebook
    case 'Chapter Outline':
      return Document
    case 'Character Card':
      return User
    case 'Scene Card':
      return OfficeBuilding
    case 'Organization Card':
      return Connection
    case 'Item Card':
      return Box
    case 'Concept Card':
      return CollectionTag
    case 'Folder':
      return Folder
    default:
      return Document // Generic default icon
  }
}

// Context menu command handler (new child card, delete card)
function handleContextCommand(command: string, data: any) {
  if (command === 'create-child') {
    openCreateChild(data.id)
  } else if (command === 'create-child-in-group') {
    // Group node: use the actual parent card ID and preset the card type
    openCreateChildInGroup(data.__parentCardId, data.__groupType)
  } else if (command === 'delete') {
    deleteNode(data.id, data.title)
  } else if (command === 'batch-delete') {
    batchDeleteCards()
  } else if (command === 'delete-group') {
    deleteGroupNodes(data)
  } else if (command === 'edit-structure') {
     if (!data?.id || data.__isGroup) return
     openCardSchemaStudio(data)
  } else if (command === 'rename') {
    if (!data?.id || data.__isGroup) return
    renameCard(data.id, data.title || '')
  } else if (command === 'add-as-reference') {
    try {
      if (!data?.id || data.__isGroup) return
      const pid = projectStore.currentProject?.id as number
      const pname = projectStore.currentProject?.name || ''
      const full = (cards.value || []).find((c:any) => c.id === data.id)
      const title = (full?.title || data.title || '') as string
      const content = (full?.content || (data as any).content || {})
      assistantStore.addInjectedRefDirect({
        refType: 'card',
        projectId: pid,
        projectName: pname,
        cardId: data.id,
        cardTitle: title,
        content,
      }, 'manual')
      ElMessage.success(t('editorPage.addedAsReference'))
    } catch {}
  }
}

function openCardSchemaStudio(card: any) {
  schemaStudio.value = { visible: true, cardId: card.id, cardTitle: card.title || '' }
}

const schemaStudio = ref<{ visible: boolean; cardId: number; cardTitle: string }>({ visible: false, cardId: 0, cardTitle: '' })

async function onCardSchemaSaved() {
  try {
    await cardStore.fetchCards(projectStore.currentProject?.id as number)
  } catch {}
}

function openCreateCardDialog(options?: { title?: string; cardTypeName?: string; parentId?: number | null }) {
  newCardForm.title = options?.title || ''
  newCardForm.parent_id = options?.parentId == null ? '' as any : options.parentId as any
  if (options?.cardTypeName) {
    const cardType = cardStore.cardTypes.find(ct => ct.name === options.cardTypeName)
    newCardForm.card_type_id = cardType?.id
  } else {
    newCardForm.card_type_id = undefined
  }
  activeTab.value = 'editor'
  isCreateCardDialogVisible.value = true
  blankMenuVisible.value = false
}

// Open the "new card" dialog and prefill the parent ID
function openCreateChild(parentId: number) {
  openCreateCardDialog({ parentId })
}

// Open the "new card" dialog (group node only): prefill parent ID and card type
function openCreateChildInGroup(parentId: number, groupType: string) {
  openCreateCardDialog({ parentId, cardTypeName: groupType })
}

function openCreateRoot() {
  openCreateCardDialog()
}

function onOpenCreateCardEvent(e: Event) {
  const detail = (e as CustomEvent)?.detail || {}
  openCreateCardDialog({
    title: typeof detail.title === 'string' ? detail.title : '',
    cardTypeName: typeof detail.cardTypeName === 'string' ? detail.cardTypeName : '',
    parentId: Number.isFinite(Number(detail.parentId)) ? Number(detail.parentId) : null,
  })
}

// Right-click on blank area: only show the menu when no node is hit
function onSidebarContextMenu(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (target.closest('.custom-tree-node')) return
  blankMenuX.value = e.clientX
  blankMenuY.value = e.clientY
  blankMenuVisible.value = true
}

// Delete a card (with confirmation)
async function deleteNode(cardId: number, title: string) {
  try {
    await ElMessageBox.confirm(t('editorPage.deleteCardConfirm', { title }), t('editorPage.deleteConfirmTitle'), { type: 'warning' })
    
    //  Record card info before deletion
    const card = cards.value.find(c => (c as any).id === cardId)
    const cardType = card ? ((card as any).card_type?.name || 'Unknown') : 'Unknown'
    
    // If the deleted card is the currently active card, clear active state first
    if (activeCard.value && (activeCard.value as any).id === cardId) {
      cardStore.setActiveCard(null as any)
    }
    
    try {
      await cardStore.removeCard(cardId)
      ElMessage.success(t('editorPage.cardDeleted'))
      
      //  Record delete operation
      if (projectStore.currentProject?.id) {
        assistantStore.recordOperation(projectStore.currentProject.id, {
          type: 'delete',
          cardId,
          cardTitle: title,
          cardType
        })
      }
    } catch (error: any) {
      console.error('Failed to delete card:', error)
      ElMessage.error(t('editorPage.deleteCardFailed'))
    }
  } catch (e) {
    // User cancelled
  }
}

async function deleteGroupNodes(groupData: any) {
  try {
    const title = groupData?.title || groupData?.__groupType || t('editorPage.thisGroup')
    await ElMessageBox.confirm(t('editorPage.deleteGroupConfirm', { title }), t('editorPage.deleteConfirmTitle'), { type: 'warning' })
    const directChildren: any[] = Array.isArray(groupData?.children) ? groupData.children : []
    const toDeleteOrdered: number[] = []

    // Recursive collection: leaves first (delete descendants before parents)
    function collectDescendantIds(parentId: number) {
      const childIds = (cards.value || []).filter((c: any) => c.parent_id === parentId).map((c: any) => c.id)
      for (const cid of childIds) collectDescendantIds(cid)
      toDeleteOrdered.push(parentId)
    }

    for (const child of directChildren) {
      collectDescendantIds(child.id)
    }

    // Deduplicate (theoretically no overlap)
    const seen = new Set<number>()
    for (const id of toDeleteOrdered) {
      if (seen.has(id)) continue
      seen.add(id)
      await cardStore.removeCard(id)
    }
  } catch (e) {
    // User cancelled
  }
}

// Rename feature
async function renameCard(cardId: number, oldTitle: string) {
  try {
    const { value } = await ElMessageBox.prompt(t('editorPage.renamePromptMsg'), t('common.rename'), {
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
      inputValue: oldTitle,
      inputPlaceholder: t('editorPage.enterCardTitle'),
      inputValidator: (v:string) => v.trim().length > 0 || t('editorPage.titleCannotBeEmpty')
    })
    const newTitle = String(value).trim()
    if (newTitle === oldTitle) return
    // Default: only update the shell card.title
    const card = (cards.value || []).find((c: any) => c.id === cardId) as any
    const payload: any = { title: newTitle }

    // Only apply the "title field bound to card name" optimization for chapter outline / chapter text
    const typeName = card?.card_type?.name || ''
    if ((typeName === 'Chapter Outline' || typeName === 'Chapter Text') && card?.content) {
      const content: any = { ...(card.content as any) }
      content.title = newTitle
      payload.content = content
    }
    await cardStore.modifyCard(cardId, payload)
    ElMessage.success(t('editorPage.renamed'))
  } catch {
    // User cancelled or failed
  }
}

// Assistant panel context
const assistantResolvedContext = ref<string>('')
const assistantEffectiveSchema = ref<any>(null)
const assistantSelectionCleared = ref<boolean>(false)
const assistantParams = ref<{ llm_config_id: number | null; prompt_name: string | null; temperature: number | null; max_tokens: number | null; timeout: number | null }>({ llm_config_id: null, prompt_name: 'Inspiration Dialogue', temperature: null, max_tokens: null, timeout: null })

// Determine whether the current card is a chapter text card
const isChapterContent = computed(() => {
  return activeCard.value?.card_type?.name === 'Chapter Text'
})

const showRightSidebarTabs = computed(() => {
  return Boolean(activeCard.value)
})

const reviewTargetCardIdForSidebar = computed<number | null>(() => {
  const card = activeCard.value as any
  if (!card) return null
  if (card?.card_type?.name === 'Content Review Card') {
    const target = Number(card?.content?.review_target_card_id || 0)
    return Number.isFinite(target) && target > 0 ? target : null
  }
  return Number(card.id || 0) || null
})

const rightSidebarTabNames = computed(() => {
  if (!showRightSidebarTabs.value) return [] as string[]
  if (isChapterContent.value) return ['assistant', 'context', 'extract', 'outline', 'review-history']
  return ['assistant', 'review-history']
})

// Chapter info extraction
const chapterVolumeNumber = computed(() => {
  if (!isChapterContent.value) return null
  const content: any = activeCard.value?.content || {}
  return content.volume_number ?? null
})

const chapterChapterNumber = computed(() => {
  if (!isChapterContent.value) return null
  const content: any = activeCard.value?.content || {}
  return content.chapter_number ?? null
})

const chapterParticipants = computed(() => {
  if (!isChapterContent.value) return []
  const content: any = activeCard.value?.content || {}
  const list = content.entity_list || []
  if (Array.isArray(list)) {
    return list.map((x: any) => typeof x === 'string' ? x : (x?.name || '')).filter(Boolean).slice(0, 6)
  }
  return []
})

// Auto-assemble chapter context (when entering chapter text for the first time)
watch(isChapterContent, async (val) => {
  if (val && activeCard.value) {
    await assembleChapterContext()
  }
}, { immediate: true })

watch(rightSidebarTabNames, (tabNames) => {
  if (!tabNames.includes(activeRightTab.value)) {
    activeRightTab.value = 'assistant'
  }
}, { immediate: true })

// When the card store content changes, if still on a chapter text card, re-assemble the context
watch(cards, async () => {
  if (isChapterContent.value && activeCard.value) {
    await assembleChapterContext()
  }
})

async function assembleChapterContext() {
  if (!isChapterContent.value || !projectStore.currentProject?.id) return
  
  try {
    const { assembleContext } = await import('@renderer/api/ai')
    const res = await assembleContext({
      project_id: projectStore.currentProject.id,
      volume_number: chapterVolumeNumber.value ?? undefined,
      chapter_number: chapterChapterNumber.value ?? undefined,
      participants: chapterParticipants.value,
      current_draft_tail: ''
    })
    prefetchedContext.value = res
  } catch (e) {
    console.error('Failed to assemble chapter context:', e)
  }
}

// When participants are added/removed manually in the right "participants" panel, write changes back to the current chapter card content
async function handleContextParticipantsUpdate(names: string[]) {
  try {
    if (!isChapterContent.value || !activeCard.value) return
    const card = activeCard.value as any
    const content: any = { ...(card.content || {}) }
    // Only use the name list as the source of the entity list (object form can still be filled in later by the analysis flow)
    const normalized = (names || [])
      .map(n => (typeof n === 'string' ? n.trim() : String(n || '')).trim())
      .filter(Boolean)
    content.entity_list = normalized
    await cardStore.modifyCard(card.id, { content } as any)
    // After modifyCard succeeds, the cards watcher will trigger assembleChapterContext using the new participants
  } catch (e) {
    console.error('Failed to update participants on card:', e)
  }
}

function handleContextAssembledUpdate(ctx: any) {
  prefetchedContext.value = ctx || null
}


async function refreshAssistantContext() {
  try {
    const card = assistantSelectionCleared.value ? null : (activeCard.value as any)
    if (!card) { assistantResolvedContext.value = ''; assistantEffectiveSchema.value = null; return }
    // Compute context (reuse contextResolver)
    const { resolveTemplate } = await import('@renderer/services/contextResolver')
    // Use the card's currently saved ai_context_template and content
    const resolved = resolveTemplate({
      template: card.ai_context_template || '',
      cards: cards.value,
      currentCard: card,
      assembledContext: prefetchedContext.value,
    })
    assistantResolvedContext.value = resolved
    // Read effective Schema
    const resp = await getCardSchema(card.id)
    assistantEffectiveSchema.value = resp?.effective_schema || resp?.json_schema || null
    // Read effective AI params (ensure llm_config_id exists)
    try {
      const ai = await getCardAIParams(card.id)
      const eff = (ai?.effective_params || {}) as any
      assistantParams.value = {
        llm_config_id: eff.llm_config_id ?? null,
        prompt_name: (eff.prompt_name ?? 'Inspiration Dialogue') as any,
        temperature: eff.temperature ?? null,
        max_tokens: eff.max_tokens ?? null,
        timeout: eff.timeout ?? null,
      }
    } catch {
      // Fallback: directly use the card's ai_params
      const p = (card?.ai_params || {}) as any
      assistantParams.value = {
        llm_config_id: p.llm_config_id ?? null,
        prompt_name: (p.prompt_name ?? 'Inspiration Dialogue') as any,
        temperature: p.temperature ?? null,
        max_tokens: p.max_tokens ?? null,
        timeout: p.timeout ?? null,
      }
    }
  } catch { assistantResolvedContext.value = '' }
}

watch(activeCard, () => { if (!assistantSelectionCleared.value) refreshAssistantContext() })
watch(prefetchedContext, () => { if (!assistantSelectionCleared.value) refreshAssistantContext() })

watch(activeTab, (tab) => {
  if (tab === 'relation-graph') {
    relationGraphRefreshSeq.value += 1
  }
})

function resetAssistantSelection() {
  assistantSelectionCleared.value = true
  assistantResolvedContext.value = ''
  assistantEffectiveSchema.value = null
}

const assistantFinalize = async (summary: string) => {
  try {
    const card = activeCard.value as any
    if (!card) return
    const evt = new CustomEvent('nf:assistant-finalize', { detail: { cardId: card.id, summary } })
    window.dispatchEvent(evt)
    ElMessage.success(t('editorPage.sentFinalizeToEditor'))
  } catch {}
}

function onAssistantAddRef(e: CustomEvent) {
  try {
    const payload = (e as any)?.detail || {}
    const ref = (payload.ref || payload) as AssistantRef
    assistantStore.addInjectedRefDirect(ref, (ref as any)?.source || 'manual')
    activeRightTab.value = 'assistant'
  } catch {}
}

function onAssistantAddExcerptRef(e: CustomEvent) {
  try {
    const payload = (e as any)?.detail || {}
    const ref = (payload.ref || payload) as ChapterExcerptRef
    assistantStore.addChapterExcerptRef(ref, (ref as any)?.source || 'manual')
    activeRightTab.value = 'assistant'
  } catch {}
}

function onAssistantAddReviewRef(e: CustomEvent) {
  try {
    const payload = (e as any)?.detail || {}
    const ref = (payload.ref || payload) as ReviewResultRef
    assistantStore.addReviewResultRef(ref, (ref as any)?.source || 'manual')
    activeRightTab.value = 'assistant'
  } catch {}
}

async function onAssistantFinalize(e: CustomEvent) {
  try {
    const card = activeCard.value as any
    if (!card) return
    const summary: string = (e as any)?.detail?.summary || ''
    const llmId = assistantParams.value.llm_config_id
    const promptName = (assistantParams.value.prompt_name || 'Content Generation') as string
    const schema = assistantEffectiveSchema.value
    if (!llmId) { ElMessage.warning(t('editorPage.selectModelFirst')); return }
    if (!schema) { ElMessage.warning(t('editorPage.noValidSchema')); return }
    // Assemble finalize input: context + finalize points
    const ctx = (assistantResolvedContext.value || '').trim()
    const inputText = [ctx ? (t('editorPage.contextLabel') + '\n' + ctx) : '', summary ? (t('editorPage.finalizePointsLabel') + '\n' + summary) : ''].filter(Boolean).join('\n\n')
    const result = await generateAIContent({
      input: { input_text: inputText },
      llm_config_id: llmId as any,
      prompt_name: promptName,
      response_model_schema: schema as any,
      temperature: assistantParams.value.temperature ?? undefined,
      max_tokens: assistantParams.value.max_tokens ?? undefined,
      timeout: assistantParams.value.timeout ?? undefined,
    } as any)
    if (result) {
      await cardStore.modifyCard(card.id, { content: result as any })
      ElMessage.success(t('editorPage.generatedAndWrittenBack'))
    } else {
      ElMessage.error(t('editorPage.finalizeFailedNoContent'))
    }
  } catch (err) {
    ElMessage.error(t('editorPage.finalizeFailed'))
    console.error(err)
  }
}

// Assistant chips jump to card
async function handleJumpToCard(payload: { projectId: number; cardId: number }) {
  try {
    const curPid = projectStore.currentProject?.id
    if (curPid !== payload.projectId) {
      // Switch project: find the target project from the full project list and set it
      const all = await getProjects()
      const target = (all || []).find(p => p.id === payload.projectId)
      if (target) {
        projectStore.setCurrentProject(target as any)
        await cardStore.fetchCards(target.id!)
      }
    }
    // Activate the target card (navigation only, do not modify injectedRefs)
    cardStore.setActiveCard(payload.cardId)
    activeTab.value = 'editor'
  } catch {}
}

function onJumpToCardEvent(e: CustomEvent) {
  const detail = (e as any)?.detail || {}
  const cardId = Number(detail.cardId || 0)
  if (!cardId) return
  void handleJumpToCard({
    projectId: Number(detail.projectId || projectStore.currentProject?.id || 0),
    cardId,
  })
}

// --- Lifecycle ---

onMounted(async () => {
  // Fetch initial data for the card system (like types and models)
  // Cards will be fetched automatically by the watcher in the card store
  await cardStore.fetchInitialData()
  // Refresh available models once when entering the editor page (handles models added on other pages)
  await cardStore.fetchAvailableModels()
  
  // Update the project card type list (used by inspiration assistant tool calls)
  try {
    const types = cardStore.cardTypes.map(t => t.name)
    assistantStore.updateProjectCardTypes(types)
  } catch {}
  
  window.addEventListener('nf:navigate', onNavigate as any)
  window.addEventListener('nf:assistant-finalize', onAssistantFinalize as any)
  window.addEventListener('nf:switch-main-tab', onSwitchMainTab as any)
  window.addEventListener('nf:switch-right-tab', onSwitchRightTab as any)
  window.addEventListener('nf:assistant-add-ref', onAssistantAddRef as any)
  window.addEventListener('nf:assistant-add-excerpt-ref', onAssistantAddExcerptRef as any)
  window.addEventListener('nf:assistant-add-review-ref', onAssistantAddReviewRef as any)
  window.addEventListener('nf:jump-to-card', onJumpToCardEvent as any)
  window.addEventListener('nf:open-create-card', onOpenCreateCardEvent as any)
  await refreshAssistantContext()
})

 onBeforeUnmount(() => {
   window.removeEventListener('nf:navigate', onNavigate as any)
   window.removeEventListener('nf:assistant-finalize', onAssistantFinalize as any)
   window.removeEventListener('nf:switch-main-tab', onSwitchMainTab as any)
   window.removeEventListener('nf:switch-right-tab', onSwitchRightTab as any)
   window.removeEventListener('nf:assistant-add-ref', onAssistantAddRef as any)
   window.removeEventListener('nf:assistant-add-excerpt-ref', onAssistantAddExcerptRef as any)
   window.removeEventListener('nf:assistant-add-review-ref', onAssistantAddReviewRef as any)
   window.removeEventListener('nf:jump-to-card', onJumpToCardEvent as any)
   window.removeEventListener('nf:open-create-card', onOpenCreateCardEvent as any)
  })

 function onNavigate(e: CustomEvent) {
   if ((e as any).detail?.to === 'market') {
     activeTab.value = 'market'
   }
 }

function onSwitchMainTab(e: CustomEvent) {
  const tab = (e as any)?.detail?.tab
  if (tab && ['market', 'editor', 'relation-graph'].includes(tab)) {
    activeTab.value = tab
  }
}

function onSwitchRightTab(e: CustomEvent) {
  const tab = (e as any)?.detail?.tab
  if (tab && rightSidebarTabNames.value.includes(tab)) {
    activeRightTab.value = tab
  }
}

 // Hide the blank menu on any page click
 document.addEventListener('click', () => (blankMenuVisible.value = false))

 const treeRef = ref<any>(null)

 watch(groupedTree, async () => {
   // Wait for the tree to re-render with new data
   await nextTick()
   try { 
     if (expandedKeys.value.length > 0) {
       // Using Element Plus Tree store API to set expanded keys
       // This is more reliable than manipulating nodes directly
       treeRef.value?.store?.setDefaultExpandedKeys(expandedKeys.value)
     }
   } catch (e) {
     console.error('Failed to restore expanded state:', e)
   }
 }, { deep: true })
</script>

<style scoped>
/* Make the right-click trigger area span the full row */
.full-row-dropdown { display: block; width: 100%; }
.blank-menu-ref { pointer-events: none; }

.editor-layout {
  display: flex;
  height: 100%;
  width: 100%;
  position: relative;
  background-color: var(--el-fill-color-lighter); /* Adapt for dark mode */
}

.sidebar {
  display: flex;
  flex-direction: column;
  background-color: var(--el-fill-color-lighter); /* Adapt for dark mode */
  transition: width 0.2s;
  flex-shrink: 0;
  overflow: hidden;
  border-right: none; /* Remove border */
}

.card-navigation-sidebar {
  padding: 8px;
}

/* The top title area has had its buttons removed, hide it here to eliminate the gap */
.sidebar-header { display: none; }

.sidebar-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.card-tree {
  background-color: transparent;
  flex-grow: 1;
}

.custom-tree-node {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 6px;
  font-size: 14px;
  padding-right: 8px;
}
.card-icon {
  color: var(--el-text-color-secondary);
}
.child-count {
  margin-left: auto;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.resizer {
  width: 5px;
  background: transparent;
  cursor: col-resize;
  z-index: 10;
  user-select: none;
  position: relative;
  transition: background-color 0.2s;
}
.resizer:hover {
  background: var(--el-color-primary-light-7);
}

.main-content {
  padding: 16px 8px; /* Leave margins */
  display: flex;
  flex-direction: column;
  background-color: transparent; /* Transparent background */
}

.main-tabs {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  background-color: var(--el-bg-color); /* Adapt for dark mode */
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08); /* Subtle shadow */
  border-radius: 8px; /* Rounded corners */
  overflow: hidden; /* Ensure content does not overflow rounded corners */
  border: none; /* Remove default border */
}

:deep(.el-tabs__content) {
  flex-grow: 1;
  overflow-y: auto;
}
:deep(.el-tab-pane) {
  height: 100%;
}

.custom-tree-node.full-row { 
  display: flex;
  align-items: center;
  width: 100%;
  padding: 3px 6px;
  border-radius: 4px;
  transition: background-color 0.2s;
}
.custom-tree-node.full-row .label {
  flex: 1;
}
.custom-tree-node.full-row.selected {
  background-color: var(--el-color-primary-light-9);
  border: 1px solid var(--el-color-primary-light-7);
}
.custom-tree-node.full-row.selected .label {
  color: var(--el-color-primary);
  font-weight: 500;
}


.types-pane { display: flex; flex-direction: column; border-bottom: 1px solid var(--el-border-color-light); background: var(--el-fill-color-lighter); padding: 6px; box-shadow: 0 2px 6px -2px var(--el-box-shadow-lighter); border-radius: 6px; }
.pane-title { font-size: 12px; color: var(--el-text-color-regular); font-weight: 600; padding: 2px 4px 6px 4px; }
.types-scroll { flex: 1; background: var(--el-fill-color-lighter); }
.types-list { list-style: none; padding: 0; margin: 0; }
.type-item { padding: 6px 8px; cursor: grab; display: flex; align-items: center; color: var(--el-text-color-primary); font-size: 13px; border-radius: 4px; }
.type-item:hover { background: var(--el-fill-color-light); color: var(--el-color-primary); }
.type-name { flex: 1; }

.inner-resizer { height: 6px; cursor: row-resize; background: var(--el-fill-color-light); border-top: 1px solid var(--el-border-color-light); border-bottom: 1px solid var(--el-border-color-light); transition: height .12s ease, background-color .12s ease, border-color .12s ease; }
.inner-resizer:hover { height: 8px; background: var(--el-fill-color); border-top: 1px solid var(--el-border-color); border-bottom: 1px solid var(--el-border-color); }
/* Lower pane: pin title to top and set scroll container */
.cards-pane { position: relative; padding-top: 8px; overflow: auto; overflow-x: hidden; }
.cards-title {
  position: sticky;
  top: 0;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-regular);
  padding: 8px;
  background: color-mix(in srgb, var(--el-bg-color) 92%, transparent);
  backdrop-filter: blur(14px);
  border: 1px solid color-mix(in srgb, var(--el-border-color-light) 82%, transparent);
  border-radius: 12px;
  margin: 0 2px 8px;
  box-shadow: 0 10px 24px -22px rgba(15, 23, 42, 0.45);
}
.cards-title-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.cards-title-text {
  min-width: 0;
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cards-selection-chip {
  flex-shrink: 0;
  padding: 4px 9px;
  border-radius: 999px;
  font-size: 11px;
  line-height: 1;
  color: var(--el-color-danger);
  background: color-mix(in srgb, var(--el-color-danger-light-9) 78%, var(--el-bg-color));
  border: 1px solid color-mix(in srgb, var(--el-color-danger-light-7) 82%, transparent);
}
.cards-title-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  width: 100%;
}
.toolbar-action {
  width: 100%;
  min-width: 0;
  margin: 0 !important;
  justify-content: center;
}
.toolbar-action-create-full {
  grid-column: 1 / -1;
}
.toolbar-action-create-split {
  grid-column: span 1;
}
.toolbar-action-secondary {
  grid-column: span 1;
}
.toolbar-action-secondary--solo {
  grid-column: 1 / -1;
}
.toolbar-action-danger-split {
  grid-column: span 1;
}
.cards-title-actions :deep(.el-button > span) {
  min-width: 0;
}
.assistant-sidebar { 
  border-left: none; 
  background: transparent; 
  flex-shrink: 0; 
  padding: 16px 8px 16px 0; /* Right padding */
}
.right-resizer { cursor: col-resize; width: 5px; background: transparent; }
.right-resizer:hover { background: var(--el-color-primary-light-7); }
.sidebar-edge-toggle {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  z-index: 30;
  display: grid;
  place-items: center;
  align-items: center;
  width: 36px;
  height: 36px;
  padding: 0;
  border: 1px solid color-mix(in srgb, var(--el-border-color) 84%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--el-bg-color) 94%, rgba(255,255,255,0.65));
  box-shadow:
    0 10px 22px -18px rgba(15, 23, 42, 0.34),
    0 3px 8px -6px rgba(15, 23, 42, 0.18);
  color: var(--el-text-color-regular);
  cursor: pointer;
  transition:
    left 0.2s ease,
    box-shadow 0.18s ease,
    border-color 0.18s ease,
    color 0.18s ease,
    background-color 0.18s ease,
    transform 0.18s ease,
    opacity 0.18s ease;
  backdrop-filter: blur(14px);
  opacity: 0.92;
}
.sidebar-edge-toggle:hover,
.sidebar-edge-toggle:focus-visible {
  transform: translateY(-50%) scale(1.04);
  box-shadow:
    0 14px 28px -20px rgba(37, 99, 235, 0.28),
    0 4px 10px -8px rgba(15, 23, 42, 0.2);
  border-color: color-mix(in srgb, var(--el-color-primary-light-6) 68%, transparent);
  color: var(--el-color-primary);
  outline: none;
  opacity: 1;
}
.sidebar-edge-toggle.is-collapsed {
  background: color-mix(in srgb, var(--el-bg-color) 96%, rgba(255,255,255,0.72));
}
.sidebar-edge-toggle__icon {
  font-size: 15px;
  line-height: 1;
}
.nf-import-dialog :deep(.el-input__wrapper) { font-size: 14px; }
.nf-import-dialog :deep(.el-input__inner) { font-size: 14px; }
.nf-import-dialog :deep(.el-table .cell) { font-size: 14px; color: var(--el-text-color-primary); }
.nf-import-dialog :deep(.el-table__row) { height: 40px; }
.nf-tree-select-popper { min-width: 320px; }
.nf-tree-select-popper { background: var(--el-bg-color-overlay, #fff); color: var(--el-text-color-primary); }
.nf-tree-select-popper :deep(.el-select-dropdown__item) { color: var(--el-text-color-primary); }
.nf-tree-select-popper :deep(.el-tree) { background: transparent; }
.nf-tree-select-popper :deep(.el-tree-node__content) { background: transparent; }
.nf-tree-select-popper :deep(.el-tree-node__label) { font-size: 14px; color: var(--el-text-color-primary); }
.nf-tree-select-popper :deep(.is-current > .el-tree-node__content),
.nf-tree-select-popper :deep(.el-tree-node__content:hover) { background: var(--el-fill-color-light); }

/* Right column tab styles */
.right-tabs {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color);
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}
.right-tabs :deep(.el-tabs__header) {
  margin: 0;
  border-bottom: 1px solid var(--el-border-color-light);
  padding: 12px 12px 0 12px;
  background: var(--el-fill-color-lighter);
}
.right-tabs :deep(.el-tabs__nav-wrap) {
  padding: 0;
}
.right-tabs :deep(.el-tabs__item) {
  font-size: 13px;
  font-weight: 500;
  padding: 0 16px;
  height: 36px;
  line-height: 36px;
}
.right-tabs :deep(.el-tabs__item.is-active) {
  color: var(--el-color-primary);
}
.right-tabs :deep(.el-tabs__content) {
  flex: 1;
  overflow: hidden;
  padding: 0;
}
.right-tabs :deep(.el-tab-pane) {
  height: 100%;
  overflow-y: auto;
}

.search-results-list {
  flex-grow: 1;
  overflow-y: auto;
  padding: 0 8px;
}
.search-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  cursor: pointer;
  border-radius: 4px;
  color: var(--el-text-color-primary);
  font-size: 14px;
  transition: background-color 0.2s;
}
.search-item:hover {
  background-color: var(--el-fill-color-light);
}
.search-item-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* i18n: keep longer English tab/button labels on one line */
.main-tabs :deep(.el-tabs__item),
.right-tabs :deep(.el-tabs__item) {
  white-space: nowrap;
}
.toolbar-action,
.cards-title-actions :deep(.el-button) {
  white-space: nowrap;
}
:deep(.el-form-item__label) {
  white-space: nowrap;
}
</style>
