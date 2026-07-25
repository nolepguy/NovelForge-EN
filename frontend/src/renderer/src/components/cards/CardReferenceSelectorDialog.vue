<template>
  <el-dialog
    :model-value="modelValue"
    :title="t('card.referenceTitle')"
    width="84%"
    @update:model-value="$emit('update:modelValue', $event)"
    @close="reset"
  >
    <div class="selector-container">
      <!-- Left column: search + type-grouped card tree (multi-select via checkboxes) -->
      <div class="column left">
        <el-input
          v-model="cardSearch"
          :placeholder="t('card.searchCardPlaceholder')"
          clearable
          class="mt8"
        />
        <el-tree
          ref="cardTreeRef"
          :data="cardTreeData"
          :props="{ label: 'label', children: 'children' }"
          node-key="key"
          show-checkbox
          :default-expand-all="false"
          :expand-on-click-node="false"
          class="card-tree"
          @node-click="handleTreeNodeClick"
          @check="handleCardTreeCheck"
        />
      </div>

      <!-- Right column: field tree of the focused card -->
      <div class="column">
        <div class="row-head">
          <h3>{{ t('card.selectFieldOptional') }}</h3>
          <span class="focused-title">
            {{
              focusedCard
                ? t('card.fieldsForCard', { title: focusedCard.title })
                : t('card.selectFieldHint')
            }}
          </span>
        </div>
        <el-tree
          v-if="fieldPaths.length"
          ref="treeRef"
          :data="fieldPaths"
          :props="{ label: 'label', children: 'children' }"
          node-key="path"
          show-checkbox
          :check-strictly="true"
          class="field-tree"
          highlight-current
          @check="handleTreeCheck"
        />
        <div v-else class="empty-state">
          <p>{{ t('card.selectFieldHint') }}</p>
        </div>
      </div>
    </div>

    <!-- Footer -->
    <template #footer>
      <div class="footer-container">
        <span class="selection-preview" :title="selectionPreview">
          {{ t('card.previewLabel') }} <strong>{{ selectionPreview || '—' }}</strong>
        </span>
        <span class="dialog-footer">
          <el-button @click="$emit('update:modelValue', false)">{{ t('common.cancel') }}</el-button>
          <el-button type="primary" :disabled="!canConfirm" @click="handleConfirm">
            {{ t('common.confirm') }}
          </el-button>
        </span>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import type { CardRead } from '@renderer/api/cards'
import { schemaService, type JSONSchema } from '@renderer/api/schema'
import { getCardSchema } from '@renderer/api/setting'
import { ElDialog, ElInput, ElTree, ElButton } from 'element-plus'

interface FieldPath {
  label: string
  path: string
  children?: FieldPath[]
}

interface CardTreeNode {
  key: string
  label: string
  card?: CardRead
  children?: CardTreeNode[]
}

interface CardSchemaResponse {
  effective_schema?: JSONSchema
  json_schema?: JSONSchema
}

interface TreeInstanceProxy {
  getCheckedNodes: (leafOnly?: boolean) => FieldPath[]
  setCheckedKeys: (keys: string[]) => void
}

interface CardTreeCheckMeta {
  checkedKeys: string[]
  halfCheckedKeys: string[]
}

const props = defineProps<{ modelValue: boolean; cards: CardRead[]; currentCardId?: number }>()
const emit = defineEmits(['update:modelValue', 'confirm'])
const { t } = useI18n()

// Search
const cardSearch = ref('')

// Multi-card selection state
const checkedCardIds = ref<number[]>([]) // insertion-ordered list of checked card ids
const focusedCardId = ref<number | null>(null) // card whose field tree is shown on the right
const cardFieldSelection = ref<Record<number, string[]>>({}) // cardId -> selected field paths (empty = whole card .content)

// Tree instances
const cardTreeRef = ref<TreeInstanceProxy>()
const treeRef = ref<TreeInstanceProxy>()

// Field tree of the focused card
const fieldPaths = ref<FieldPath[]>([])

const focusedCard = computed(() => props.cards.find((c) => c.id === focusedCardId.value) || null)

// Filter cards (by title)
const filteredCards = computed(() =>
  props.cards.filter((card) => card.title.toLowerCase().includes(cardSearch.value.toLowerCase()))
)

// Type-grouped tree data (mirrors the inspiration assistant "Add reference" tree)
const cardTreeData = computed<CardTreeNode[]>(() => {
  const byType: Record<string, CardRead[]> = {}
  for (const card of filteredCards.value) {
    const typeName = card.card_type?.name || t('app.assistant.uncategorized')
    ;(byType[typeName] ||= []).push(card)
  }
  return Object.keys(byType)
    .sort()
    .map((typeName, idx) => ({
      key: `type:${idx}`,
      label: typeName,
      children: byType[typeName].map((card) => ({
        key: `card:${card.id}`,
        label: card.title,
        card
      }))
    }))
})

function buildCardRef(card: CardRead): string {
  const paths = cardFieldSelection.value[card.id] || []
  if (paths.length === 0) return `@${card.title}.content`
  if (paths.length === 1) return `@${card.title}.${paths[0]}`
  return `@${card.title}.{${paths.join(',')}}`
}

// Combined preview string (one @ref per checked card, space-joined)
const selectionPreview = computed(() => {
  if (checkedCardIds.value.length === 0) return ''
  return checkedCardIds.value
    .map((id) => props.cards.find((c) => c.id === id))
    .filter((c): c is CardRead => !!c)
    .map(buildCardRef)
    .join(' ')
})

const canConfirm = computed(() => checkedCardIds.value.length > 0)

watch(
  () => props.modelValue,
  (isOpening) => {
    if (isOpening) reset()
  }
)

function reset(): void {
  cardSearch.value = ''
  checkedCardIds.value = []
  focusedCardId.value = null
  cardFieldSelection.value = {}
  fieldPaths.value = []
  nextTick(() => {
    cardTreeRef.value?.setCheckedKeys?.([])
    treeRef.value?.setCheckedKeys?.([])
  })
}

// Left tree: checkbox change
function handleCardTreeCheck(data: CardTreeNode, meta: CardTreeCheckMeta): void {
  const newIds = meta.checkedKeys
    .filter((k) => k.startsWith('card:'))
    .map((k) => Number(k.split(':')[1]))
    .filter((id) => Number.isFinite(id))
  const set = new Set(newIds)
  // Preserve insertion order: keep prior order for cards still checked, append new ones
  const ordered: number[] = checkedCardIds.value.filter((id) => set.has(id))
  for (const id of newIds) if (!ordered.includes(id)) ordered.push(id)
  // Initialize field state for newly checked cards (default empty = .content); drop unchecked
  for (const id of ordered) if (!(id in cardFieldSelection.value)) cardFieldSelection.value[id] = []
  for (const id of checkedCardIds.value) if (!set.has(id)) delete cardFieldSelection.value[id]
  checkedCardIds.value = ordered

  // Activate right field only when a single card leaf was directly checked (not a type group)
  if (data && data.card && set.has(data.card.id)) {
    focusedCardId.value = data.card.id
    void loadFieldTreeForFocused()
  }
  // If the focused card is no longer checked (via any path), deactivate the right field
  if (focusedCardId.value != null && !ordered.includes(focusedCardId.value)) {
    focusedCardId.value = null
    fieldPaths.value = []
  }
}

// Left tree: node click (focus only, does not toggle check; only checked cards can be focused)
function handleTreeNodeClick(data: CardTreeNode): void {
  if (data && data.card && checkedCardIds.value.includes(data.card.id)) {
    focusedCardId.value = data.card.id
    void loadFieldTreeForFocused()
  }
}

async function loadFieldTreeForFocused(): Promise<void> {
  const card = focusedCard.value
  if (!card) {
    fieldPaths.value = []
    return
  }
  try {
    const resp = (await getCardSchema(card.id)) as CardSchemaResponse | undefined
    const sch = resp?.effective_schema || resp?.json_schema
    fieldPaths.value = sch ? generateFieldFields(sch) : []
  } catch {
    fieldPaths.value = []
  }
  // After data renders, sync checkbox state to this card's stored selection
  nextTick(() => {
    const saved = cardFieldSelection.value[card.id] || []
    treeRef.value?.setCheckedKeys?.(saved)
  })
}

// Right field tree: checkbox change → write back to focused card's field selection
function handleTreeCheck(): void {
  if (focusedCardId.value == null) return
  if (!checkedCardIds.value.includes(focusedCardId.value)) return
  const nodes = treeRef.value?.getCheckedNodes?.(false) || []
  cardFieldSelection.value[focusedCardId.value] = nodes.map((n) => n.path)
}

// Re-apply left-tree checked visuals after the filter recomputes the tree data
watch([cardTreeData], () => {
  nextTick(() => {
    const keys = checkedCardIds.value.map((id) => `card:${id}`)
    cardTreeRef.value?.setCheckedKeys?.(keys)
  })
})

function generateFieldFields(schema: JSONSchema, prefix = 'content'): FieldPath[] {
  const paths: FieldPath[] = []

  const resolveRef = (refStr?: string): JSONSchema | null => {
    if (!refStr || typeof refStr !== 'string') return null
    const name = refStr.split('/').pop() || ''
    return schemaService.getSchema(name) || null
  }

  const walkObject = (objSchema: JSONSchema, basePath: string): void => {
    const props = (objSchema && objSchema.properties) || {}
    for (const [key, propSchema] of Object.entries(props)) {
      const currentPath = basePath ? `${basePath}.${key}` : key
      const node: FieldPath = { label: propSchema.title || key, path: currentPath }

      if (propSchema.$ref) {
        const refSchema = resolveRef(propSchema.$ref)
        if (refSchema) node.children = generateFieldFields(refSchema, currentPath)
      } else if (propSchema.type === 'object' && propSchema.properties) {
        node.children = generateFieldFields(propSchema, currentPath)
      } else if (propSchema.type === 'array') {
        const items = propSchema.items
        if (items && (items.$ref || items.type === 'object')) {
          const itemSchema = items.$ref ? resolveRef(items.$ref) : items
          const arrayPath = `${currentPath}[]`
          const arrayNode: FieldPath = {
            label: propSchema.title || key,
            path: arrayPath,
            children: []
          }
          arrayNode.children = itemSchema ? generateFieldFields(itemSchema, arrayPath) : []
          node.children = node.children || []
          node.children.push(arrayNode)
        }
      }

      paths.push(node)
    }
  }

  if (schema && schema.properties) walkObject(schema, prefix)
  return paths
}

function handleConfirm(): void {
  if (selectionPreview.value) {
    emit('confirm', selectionPreview.value)
    emit('update:modelValue', false)
  }
}
</script>

<style scoped>
.selector-container {
  display: flex;
  gap: 20px;
  height: 60vh;
  border-top: 1px solid var(--el-border-color);
  border-bottom: 1px solid var(--el-border-color);
  padding: 10px 0;
}
.column {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-right: 1px solid var(--el-border-color);
  padding-right: 20px;
}
.column:last-child {
  border-right: none;
  padding-right: 0;
}
.column.left {
  width: 60%;
  max-width: 780px;
}
.card-tree {
  margin-top: 10px;
  flex-grow: 1;
  overflow: auto;
  border: 1px solid var(--el-border-color-light);
  padding: 8px;
  border-radius: 6px;
}
.field-tree {
  margin-top: 10px;
  flex-grow: 1;
  overflow: auto;
}
.empty-state {
  margin-top: 10px;
  color: var(--el-text-color-secondary);
  text-align: center;
  padding-top: 20px;
}
.footer-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  gap: 12px;
}
.selection-preview {
  font-size: 14px;
  color: var(--el-text-color-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 60%;
}
.mt8 {
  margin-top: 8px;
}
.row-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.focused-title {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dialog-footer .el-button {
  white-space: nowrap;
}
</style>
