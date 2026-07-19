<template>
  <el-dialog
    :model-value="modelValue"
    :title="t('card.referenceTitle')"
    width="84%"
    @update:model-value="$emit('update:modelValue', $event)"
    @close="reset"
  >
    <div class="selector-container">
      <!-- Left column: search + type-grouped card tree -->
      <div class="column left">
        <el-input
          v-model="cardSearch"
          :placeholder="t('card.searchCardPlaceholder')"
          clearable
          class="mt8"
        />
        <el-tree
          :data="cardTreeData"
          :props="{ label: 'label', children: 'children' }"
          node-key="key"
          :current-node-key="currentNodeKey || undefined"
          highlight-current
          :default-expand-all="false"
          :expand-on-click-node="false"
          class="card-tree"
          @node-click="handleTreeNodeClick"
        />
      </div>

      <!-- Right column: field tree -->
      <div class="column">
        <div class="row-head">
          <h3>{{ t('card.selectFieldOptional') }}</h3>
          <div class="right-tools">
            <el-checkbox v-model="multiMode">{{ t('card.multiSelectFields') }}</el-checkbox>
          </div>
        </div>
        <el-tree
          v-if="fieldPaths.length"
          ref="treeRef"
          :data="fieldPaths"
          :props="{ label: 'label', children: 'children' }"
          :show-checkbox="multiMode"
          :check-strictly="true"
          class="field-tree"
          highlight-current
          @node-click="handleFieldSelect"
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
        <span class="selection-preview">
          {{ t('card.previewLabel') }} <strong>{{ selectionPreview }}</strong>
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
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { CardRead } from '@renderer/api/cards'
import { schemaService, type JSONSchema } from '@renderer/api/schema'
import { getCardSchema } from '@renderer/api/setting'
import { ElDialog, ElInput, ElTree, ElButton, ElCheckbox } from 'element-plus'

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
}

const props = defineProps<{ modelValue: boolean; cards: CardRead[]; currentCardId?: number }>()
const emit = defineEmits(['update:modelValue', 'confirm'])
const { t } = useI18n()

// By title
const cardSearch = ref('')
const selectedKard = ref<CardRead | null>(null)

// Field tree
const treeRef = ref<TreeInstanceProxy>()
const selectedFieldPath = ref<string | null>(null)
const selectedFieldPaths = ref<string[]>([])
const multiMode = ref<boolean>(false)
const fieldPaths = ref<FieldPath[]>([])

// Current highlight key in the card tree
const currentNodeKey = ref<string | null>(null)

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

function buildPathSpec(): string {
  if (multiMode.value && selectedFieldPaths.value.length > 0) {
    return '.{' + selectedFieldPaths.value.join(',') + '}'
  }
  if (selectedFieldPath.value) return `.${selectedFieldPath.value}`
  return ''
}

// Preview string
const selectionPreview = computed(() => {
  if (!selectedKard.value) return ''
  const pathSpec = buildPathSpec()
  // By-title mode: defaults to .content when no field is selected
  return pathSpec
    ? `@${selectedKard.value.title}${pathSpec}`
    : `@${selectedKard.value.title}.content`
})

const canConfirm = computed(() => !!selectedKard.value)

watch(
  () => props.modelValue,
  (isOpening) => {
    if (isOpening) reset()
  }
)

function reset(): void {
  cardSearch.value = ''
  selectedKard.value = null
  selectedFieldPath.value = null
  selectedFieldPaths.value = []
  multiMode.value = false
  fieldPaths.value = []
  currentNodeKey.value = null
}

function handleTreeNodeClick(data: CardTreeNode): void {
  // Only leaf card nodes carry a `card` payload
  if (data && data.card) {
    handleCardSelect(data.card)
    currentNodeKey.value = data.key
  }
}

async function handleCardSelect(card: CardRead): Promise<void> {
  selectedKard.value = card
  selectedFieldPath.value = null
  selectedFieldPaths.value = []
  fieldPaths.value = []
  try {
    const resp = (await getCardSchema(card.id)) as CardSchemaResponse | undefined
    const sch = resp?.effective_schema || resp?.json_schema
    if (sch) fieldPaths.value = generateFieldFields(sch)
  } catch {
    // schema load failed: leave field tree empty
  }
}

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

function handleFieldSelect(data: FieldPath): void {
  if (multiMode.value) return // In multi-select mode, rely on checkboxes
  // Single select: allow non-leaf nodes
  selectedFieldPath.value = data.path
}

function handleTreeCheck(): void {
  const nodes = treeRef.value?.getCheckedNodes?.(false) || []
  selectedFieldPaths.value = nodes.map((n) => n.path)
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
}
.selection-preview {
  font-size: 14px;
  color: var(--el-text-color-secondary);
}
.mt8 {
  margin-top: 8px;
}
.row-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.right-tools {
  display: flex;
  align-items: center;
  gap: 8px;
}
.dialog-footer .el-button {
  white-space: nowrap;
}
</style>
