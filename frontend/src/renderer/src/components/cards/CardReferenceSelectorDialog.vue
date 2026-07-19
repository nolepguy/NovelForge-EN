<template>
  <el-dialog
    :model-value="modelValue"
    :title="t('card.referenceTitle')"
    width="84%"
    @update:modelValue="$emit('update:modelValue', $event)"
    @close="reset"
  >
    <div class="selector-container">
      <!-- Left column: mode selection + list area -->
      <div class="column left">
        <h3>{{ t('card.selectReferenceMethod') }}</h3>
        <el-radio-group v-model="mode" size="small">
          <el-radio-button label="title">{{ t('card.byTitle') }}</el-radio-button>
          <el-radio-button label="type">{{ t('card.byType') }}</el-radio-button>
          <el-radio-button label="special">{{ t('card.special') }}</el-radio-button>
        </el-radio-group>

        <!-- By-title mode: original card list -->
        <template v-if="mode === 'title'">
          <el-input v-model="cardSearch" :placeholder="t('card.searchCardPlaceholder')" clearable class="mt8" />
          <el-scrollbar class="list-container">
            <ul class="card-list">
              <li
                v-for="card in filteredCards"
                :key="card.id"
                :class="{ selected: selectedKard?.id === card.id }"
                @click="handleCardSelect(card)"
              >
                {{ card.title }}
              </li>
            </ul>
          </el-scrollbar>
        </template>

        <!-- By-type mode: type selection + filter method (previous/sibling/first/last/index) + index expression -->
        <template v-else-if="mode === 'type'">
          <div class="mt8">
            <el-select v-model="selectedTypeName" :placeholder="t('card.selectCardTypePlaceholder')" style="width: 100%" @change="handleTypeChange">
              <el-option v-for="t in cardTypeNames" :key="t" :label="t" :value="t" />
            </el-select>
          </div>
          <div class="mt8">
            <el-radio-group v-model="typeFilterMode" size="small">
              <el-radio-button label="first" :title="t('card.filterTipFirst')">first</el-radio-button>
              <el-radio-button label="last" :title="t('card.filterTipLast')">last</el-radio-button>
              <el-radio-button label="previous" :title="t('card.filterTipPrevious')">previous</el-radio-button>
              <el-radio-button label="sibling" :title="t('card.filterTipSibling')" :disabled="!hasParent">sibling</el-radio-button>
              <el-radio-button label="index" :title="t('card.filterTipIndex')">index</el-radio-button>
            </el-radio-group>
          </div>
          <div class="mt8" v-if="typeFilterMode === 'previous'">
            <el-radio-group v-model="previousMode" size="small">
              <el-radio-button label="global" :title="t('card.previousModeTipGlobal')">{{ t('card.previousGlobal') }}</el-radio-button>
              <el-radio-button label="local" :title="t('card.previousModeTipLocal')" :disabled="!hasParent">{{ t('card.previousLocal') }}</el-radio-button>
            </el-radio-group>
          </div>
          <div class="mt8" v-if="typeFilterMode === 'previous' && previousMode === 'global'">
            <el-input v-model="previousCount" :placeholder="t('card.previousCountPlaceholder')" />
          </div>
          <div class="mt8" v-if="typeFilterMode === 'index'">
            <el-input v-model="indexExpr" :placeholder="t('card.indexExprPlaceholder')" />
            <div class="mt8">
              <el-checkbox v-model="advMode">{{ t('card.advancedMode') }}</el-checkbox>
            </div>
            <div class="mt8 adv-grid" v-if="advMode">
              <div class="cond-list">
                <div class="cond-item" v-for="(c, idx) in advConds" :key="idx">
                  <el-select v-model="c.field" :placeholder="t('card.selectFieldPlaceholder')" style="width: 45%">
                    <el-option v-for="fp in flatFieldList" :key="fp.path" :label="fp.label + ' ('+fp.path+')'" :value="fp.path" />
                  </el-select>
                  <el-select v-model="c.op" :placeholder="t('card.operatorPlaceholder')" style="width: 12%">
                    <el-option label="=" value="=" />
                    <el-option label="in" value="in" />
                    <el-option label="<" value="<" />
                    <el-option label=">" value=">" />
                  </el-select>
                  <el-input v-model="c.rhs" :placeholder="t('card.rhsPlaceholder')" style="width: 40%" />
                  <el-button text type="danger" @click="removeCond(idx)">{{ t('common.delete') }}</el-button>
                </div>
                <div class="mt8">
                  <el-button size="small" @click="addCond">{{ t('card.addCondition') }}</el-button>
                </div>
              </div>
            </div>
            <div class="hint" v-if="advMode">{{ t('card.hintPrefix', { preview: advCondPreview }) }}</div>
          </div>
        </template>

        <!-- Special mode: self / parent / stage:current -->
        <template v-else>
          <div class="mt8">
            <el-select v-model="specialKey" :placeholder="t('card.selectSpecialReference')" style="width: 100%">
              <el-option :label="t('card.specialSelf')" value="self" />
              <el-option :label="t('card.specialParent')" value="parent" :disabled="!hasParent" />
              <el-option :label="t('card.specialStageCurrent')" value="stage:current" />
            </el-select>
          </div>
          <div class="mt8" v-if="specialKey === 'self' || specialKey === 'stage:current'">
            <el-input v-model="specialPath" :placeholder="t('card.specialPathPlaceholder')" />
          </div>
        </template>
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
          @node-click="handleFieldSelect"
          @check="handleTreeCheck"
          class="field-tree"
          highlight-current
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
          <el-button type="primary" @click="handleConfirm" :disabled="!canConfirm">
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
import { ElDialog, ElInput, ElScrollbar, ElTree, ElButton, ElRadioGroup, ElRadioButton, ElSelect, ElOption, ElCheckbox } from 'element-plus'

interface FieldPath {
  label: string
  path: string
  children?: FieldPath[]
}

const props = defineProps<{ modelValue: boolean; cards: CardRead[]; currentCardId?: number }>()
const emit = defineEmits(['update:modelValue', 'confirm'])
const { t } = useI18n()

// --- Mode and selection ---
const mode = ref<'title' | 'type' | 'special'>('title')

// Current card and parent card
const currentCard = computed(() => props.cards.find(c => c.id === props.currentCardId))
const parentCard = computed(() => props.cards.find(c => c.id === (currentCard.value?.parent_id || -1)))
const hasParent = computed(() => !!parentCard.value)

// By title
const cardSearch = ref('')
const selectedKard = ref<CardRead | null>(null)

// By type
const selectedTypeName = ref<string | undefined>(undefined)
const typeFilterMode = ref<'previous' | 'sibling' | 'first' | 'last' | 'index'>('first')
const previousMode = ref<'global' | 'local'>('global')
const indexExpr = ref<string>('1')
const previousCount = ref<string>('')


// Special
const specialKey = ref<string | undefined>(undefined)
const specialPath = ref<string>('')

// Field tree
const treeRef = ref()
const selectedFieldPath = ref<string | null>(null)
const selectedFieldPaths = ref<string[]>([])
const multiMode = ref<boolean>(false)
const fieldPaths = ref<FieldPath[]>([])
// Advanced mode (index only): multiple conditions
const advMode = ref<boolean>(false)
type AdvCond = { field: string; op: '='|'in'|'<'|'>'; rhs: string }
const advConds = ref<AdvCond[]>([])

const flatFieldList = computed(() => {
  const out: { label: string; path: string }[] = []
  function walk(nodes: FieldPath[]) {
    for (const n of nodes) {
      out.push({ label: n.label, path: n.path })
      if (n.children && n.children.length) walk(n.children)
    }
  }
  walk(fieldPaths.value)
  return out
})

// Filter cards (by title)
const filteredCards = computed(() => props.cards.filter(card => card.title.toLowerCase().includes(cardSearch.value.toLowerCase())))

// All type names
const cardTypeNames = computed(() => Array.from(new Set(props.cards.map(c => c.card_type?.name).filter(Boolean) as string[])))

function buildPathSpec(): string {
  if (multiMode.value && selectedFieldPaths.value.length > 0) {
    return ".{" + selectedFieldPaths.value.join(',') + "}"
  }
  if (selectedFieldPath.value) return `.${selectedFieldPath.value}`
  return ''
}

// Preview string
const selectionPreview = computed(() => {
  const pathSpec = buildPathSpec()
  if (mode.value === 'title') {
    if (!selectedKard.value) return ''
    // By-title mode: defaults to .content when no field is selected
    if (!pathSpec) return `@${selectedKard.value.title}.content`
    return `@${selectedKard.value.title}${pathSpec}`
  }
  if (mode.value === 'type') {
    if (!selectedTypeName.value) return ''
    let filter = ''
    if (typeFilterMode.value === 'previous') {
      const n = previousCount.value.trim()
      if (previousMode.value === 'local') {
        filter = '[previous:local]'
      } else {
        // global mode
        filter = n ? `[previous:global:${n}]` : '[previous:global]'
      }
    } else if (typeFilterMode.value === 'sibling') filter = '[sibling]'
    else if (typeFilterMode.value === 'first') filter = '[first]'
    else if (typeFilterMode.value === 'last') filter = '[last]'
    else if (typeFilterMode.value === 'index') filter = `[index=${indexExpr.value.trim()}]`
    // By-type mode: defaults to .content when no field is selected
    if (!pathSpec) return `@type:${selectedTypeName.value}${filter}.content`
    return `@type:${selectedTypeName.value}${filter}${pathSpec}`
  }
  if (mode.value === 'special') {
    if (!specialKey.value) return ''
    if (multiMode.value && selectedFieldPaths.value.length > 0) {
      return `@${specialKey.value}${pathSpec}`
    }
    if (selectedFieldPath.value) {
      return `@${specialKey.value}${pathSpec}`
    }
    // Special: parent/self default to .content; stage/chapters follow original rules
    let s = `@${specialKey.value}`
    if (specialKey.value === 'parent' || specialKey.value === 'self') {
      s += `.content`
    }
    if (specialPath.value && specialKey.value !== 'chapters:previous') s += `.${specialPath.value}`
    return s
  }
  return ''
})

const canConfirm = computed(() => {
  if (mode.value === 'title') return !!selectedKard.value
  if (mode.value === 'type') return !!selectedTypeName.value
  if (mode.value === 'special') return !!specialKey.value && (specialKey.value !== 'parent' || hasParent.value)
  return false
})

const advCondPreview = computed(() => {
  return advConds.value
    .filter(c => c.field && c.op && (c.rhs || c.op === 'in'))
    .map(c => `${c.field || 'content.<field>'} ${c.op} ${c.rhs || '<rhs>'}`)
    .join(' && ')
})

function addCond() {
  advConds.value.push({ field: 'content.name', op: 'in', rhs: '[]' })
}
function removeCond(idx: number) {
  advConds.value.splice(idx, 1)
}

// Sync the advanced mode expression to indexExpr (multiple conditions)
watch([advMode, advConds], () => {
  if (mode.value === 'type' && typeFilterMode.value === 'index' && advMode.value) {
    const expr = advCondPreview.value
    indexExpr.value = expr ? `filter:${expr}` : 'filter:'
  }
}, { deep: true })

watch(
  () => props.modelValue,
  isOpening => {
    if (isOpening) reset()
  }
)

function reset() {
  mode.value = 'title'
  // By-title mode
  cardSearch.value = ''
  selectedKard.value = null
  // By-type mode
  selectedTypeName.value = undefined
  typeFilterMode.value = 'first'
  previousMode.value = 'global'
  indexExpr.value = '1'
  previousCount.value = ''
  advMode.value = false
  advConds.value = []
  // Special mode
  specialKey.value = undefined
  specialPath.value = ''
  // Field tree and paths
  selectedFieldPath.value = null
  selectedFieldPaths.value = []
  multiMode.value = false
  fieldPaths.value = []
}

// --- Stage:Current support ---
function unwrapVolumeOutline(content: any): any {
  if (!content || typeof content !== 'object') return {}
  for (const k of ['volume_outline','VolumeOutline','volumeOutline','volume_outline_response','VolumeOutlineResponse']) {
    if (content[k] && typeof content[k] === 'object') return content[k]
  }
  return content
}

function findCurrentStage(cards: CardRead[], currentCardId?: number): { stage: any | null; volumeNumber?: number; chapterNumber?: number } {
  const cur = cards.find(c => c.id === currentCardId)
  if (!cur) return { stage: null }
  const c = (cur.content || {}) as any
  const vol = typeof c?.volume_number === 'number' ? c.volume_number : undefined
  const chn = typeof c?.chapter_number === 'number' ? c.chapter_number : undefined
  if (!vol || !chn) return { stage: null }
  const volCard = cards.find(x => (x.card_type as any)?.output_model_name === 'VolumeOutline' || x.card_type?.name === 'Volume Outline')
  if (!volCard) return { stage: null, volumeNumber: vol, chapterNumber: chn }
  const vo = unwrapVolumeOutline(volCard.content || {})
  const stages = Array.isArray(vo?.stage_lines) ? vo.stage_lines : []
  if (!stages.length) return { stage: null, volumeNumber: vol, chapterNumber: chn }
  const match = stages.find((st: any) => {
    const rc = st?.reference_chapter
    if (!Array.isArray(rc) || rc.length < 2) return false
    const [start, end] = rc
    return typeof start === 'number' && typeof end === 'number' && chn >= start && chn <= end
  })
  return { stage: match || null, volumeNumber: vol, chapterNumber: chn }
}

const stageFound = ref<boolean>(false)
const stageMeta = ref<{ volume?: number; chapter?: number; name?: string } | null>(null)

// When the special reference is set to parent, automatically load the parent card schema and render the field tree
watch(specialKey, async (key) => {
  selectedFieldPath.value = null
  selectedFieldPaths.value = []
  fieldPaths.value = []
  if (key === 'parent') {
    if (!hasParent.value) { fieldPaths.value = []; return }
    try {
      const resp = await getCardSchema(parentCard.value!.id)
      const sch = resp?.effective_schema || resp?.json_schema
      fieldPaths.value = sch ? generateFieldPaths(sch as any) : []
    } catch { fieldPaths.value = [] }
  } else if (key === 'self') {
    try {
      const resp = await getCardSchema(currentCard.value!.id)
      const sch = resp?.effective_schema || resp?.json_schema
      fieldPaths.value = sch ? generateFieldPaths(sch as any) : []
    } catch { fieldPaths.value = [] }
  } else if (key === 'stage:current') {
    // Automatically locate the stage of the current chapter; if matched, show the StageLine fields on the right
    const { stage, volumeNumber, chapterNumber } = findCurrentStage(props.cards, props.currentCardId)
    stageFound.value = !!stage
    stageMeta.value = { volume: volumeNumber, chapter: chapterNumber, name: typeof stage?.stage_name === 'string' ? stage.stage_name : undefined }
    await schemaService.loadSchemas()
    const stageSchema = schemaService.getSchema('StageLine')
    // For special objects, the path does not add the 'content.' prefix; show field names directly
    fieldPaths.value = stage ? (stageSchema ? generateFieldPaths(stageSchema, '') : []) : []
  } else {
    fieldPaths.value = []
  }
})

async function handleCardSelect(card: CardRead) {
  selectedKard.value = card
  selectedFieldPath.value = null
  selectedFieldPaths.value = []
  fieldPaths.value = []
  try {
    const resp = await getCardSchema(card.id)
    const sch = resp?.effective_schema || resp?.json_schema
    if (sch) fieldPaths.value = generateFieldPaths(sch as any)
  } catch {}
}

async function handleTypeChange() {
  // Select any card of the same type by type name to load its schema
  selectedFieldPath.value = null
  selectedFieldPaths.value = []
  fieldPaths.value = []
  const sample = props.cards.find(c => c.card_type?.name === selectedTypeName.value)
  if (sample) {
    try {
      const resp = await getCardSchema(sample.id)
      const sch = resp?.effective_schema || resp?.json_schema
      if (sch) fieldPaths.value = generateFieldPaths(sch as any)
    } catch {}
  }
}

function generateFieldPaths(schema: JSONSchema, prefix = 'content'): FieldPath[] {
  const paths: FieldPath[] = []

  const resolveRef = (refStr?: string): any | null => {
    if (!refStr || typeof refStr !== 'string') return null
    const name = refStr.split('/').pop() || ''
    return schemaService.getSchema(name) || null
  }

  const walkObject = (objSchema: any, basePath: string) => {
    const props = (objSchema && objSchema.properties) || {}
    for (const [key, propSchema] of Object.entries(props)) {
      const currentPath = basePath ? `${basePath}.${key}` : key
      const node: FieldPath = { label: (propSchema as any).title || key, path: currentPath }

      if ((propSchema as any).$ref) {
        const refSchema = resolveRef((propSchema as any).$ref)
        if (refSchema) node.children = generateFieldPaths(refSchema as any, currentPath)
      } else if ((propSchema as any).type === 'object' && (propSchema as any).properties) {
        node.children = generateFieldPaths(propSchema as any, currentPath)
      } else if ((propSchema as any).type === 'array') {
        const items = (propSchema as any).items
        if (items && (items.$ref || items.type === 'object')) {
          const itemSchema = items.$ref ? resolveRef(items.$ref) : items
          const arrayPath = `${currentPath}[]`
          const arrayNode: FieldPath = { label: (propSchema as any).title || key, path: arrayPath, children: [] }
          arrayNode.children = itemSchema ? generateFieldPaths(itemSchema as any, arrayPath) : []
          node.children = node.children || []
          node.children.push(arrayNode)
        }
      }

      paths.push(node)
    }
  }

  if (schema && (schema as any).properties) walkObject(schema as any, prefix)
  return paths
}

function handleFieldSelect(data: FieldPath) {
  if (multiMode.value) return // In multi-select mode, rely on checkboxes
  // Single select: allow non-leaf nodes
  selectedFieldPath.value = data.path
}

function handleTreeCheck() {
  try {
    const nodes = (treeRef.value as any)?.getCheckedNodes?.(false) || []
    selectedFieldPaths.value = nodes.map((n: any) => n.path)
  } catch (e) {
    // ignore
  }
}

function handleConfirm() {
  if (selectionPreview.value) {
    emit('confirm', selectionPreview.value)
    emit('update:modelValue', false)
  }
}
</script>

<style scoped>
.selector-container { display: flex; gap: 20px; height: 60vh; border-top: 1px solid var(--el-border-color); border-bottom: 1px solid var(--el-border-color); padding: 10px 0; }
.column { flex: 1; display: flex; flex-direction: column; overflow: hidden; border-right: 1px solid var(--el-border-color); padding-right: 20px; }
.column:last-child { border-right: none; padding-right: 0; }
.column.left { width: 60%; max-width: 780px; }
.list-container { margin-top: 10px; flex-grow: 1; }
.card-list { list-style: none; padding: 0; margin: 0; }
.card-list li { padding: 8px 12px; cursor: pointer; border-radius: 4px; }
.card-list li:hover { background-color: var(--el-fill-color-light); }
.card-list li.selected { background-color: var(--el-color-primary-light-9); color: var(--el-color-primary); font-weight: bold; }
.field-tree { margin-top: 10px; flex-grow: 1; overflow: auto; }
.empty-state { margin-top: 10px; color: var(--el-text-color-secondary); text-align: center; padding-top: 20px; }
.footer-container { display: flex; justify-content: space-between; align-items: center; width: 100%; }
.selection-preview { font-size: 14px; color: var(--el-text-color-secondary); }
.mt8 { margin-top: 8px; }
.row-head { display: flex; align-items: center; justify-content: space-between; }
.right-tools { display: flex; align-items: center; gap: 8px; }
.adv-grid { display: flex; gap: 8px; align-items: center; }
.cond-list { display: flex; flex-direction: column; gap: 8px; width: 100%; }
.cond-item { display: flex; gap: 8px; align-items: center; }
.hint { margin-top: 6px; font-size: 12px; color: var(--el-text-color-secondary); }
.dialog-footer .el-button { white-space: nowrap; }
</style> 