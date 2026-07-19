<template>
  <div class="relation-graph-panel">
    <div class="toolbar">
      <el-input v-model="filters.keyword" :placeholder="t('panels.relationGraph.keywordPlaceholder')" clearable class="w-keyword" @keyup.enter="reload" />
      <el-select v-model="filters.kind" clearable :placeholder="t('panels.relationGraph.kindPlaceholder')" class="w-select">
        <el-option v-for="k in kindOptions" :key="k" :label="k" :value="k" />
      </el-select>
      <el-select v-model="filters.stance" clearable :placeholder="t('panels.relationGraph.stancePlaceholder')" class="w-select">
        <el-option v-for="s in stanceOptions" :key="s" :label="s" :value="s" />
      </el-select>
      <el-button type="primary" @click="reload">{{ t('panels.relationGraph.query') }}</el-button>
      <el-button @click="resetFilters">{{ t('common.reset') }}</el-button>
    </div>

    <div class="actions">
      <el-button type="primary" @click="openCreate">{{ t('panels.relationGraph.addRelation') }}</el-button>
      <el-button @click="openBatchCreate">{{ t('panels.relationGraph.batchAdd') }}</el-button>
      <el-button @click="openImport">{{ t('common.import') }}</el-button>
      <el-button :disabled="selectedKeys.length === 0" @click="exportSelected('json')">{{ t('panels.relationGraph.exportJson') }}</el-button>
      <el-button :disabled="selectedKeys.length === 0" @click="exportSelected('csv')">{{ t('panels.relationGraph.exportCsv') }}</el-button>
      <el-button :disabled="selectedKeys.length === 0" type="danger" @click="batchDelete">{{ t('panels.relationGraph.batchDelete') }}</el-button>
      <el-button :disabled="selectedKeys.length === 0" @click="batchKindVisible = true">{{ t('panels.relationGraph.batchChangeKind') }}</el-button>
      <el-button :disabled="selectedKeys.length === 0" @click="batchStanceVisible = true">{{ t('panels.relationGraph.batchChangeStance') }}</el-button>
      <el-button :disabled="selectedKeys.length === 0" @click="batchEventsVisible = true">{{ t('panels.relationGraph.batchAppendEvents') }}</el-button>
    </div>

    <el-table :data="rows" border stripe v-loading="loading" @selection-change="onSelectionChange">
      <el-table-column type="selection" width="48" />
      <el-table-column prop="source" label="A" min-width="140" />
      <el-table-column prop="target" label="B" min-width="140" />
      <el-table-column prop="kind_cn" :label="t('panels.relationGraph.colRelation')" width="140" />
      <el-table-column prop="stance" :label="t('panels.relationGraph.colStance')" width="110" />
      <el-table-column prop="fact" :label="t('panels.relationGraph.colFact')" min-width="260" show-overflow-tooltip />
      <el-table-column :label="t('panels.relationGraph.colUpdatedAt')" width="180">
        <template #default="{ row }">
          {{ row.updated_at ? new Date(row.updated_at).toLocaleString() : '' }}
        </template>
      </el-table-column>
      <el-table-column :label="t('common.action')" width="160" fixed="right">
        <template #default="scope">
          <el-button text size="small" @click="openEdit(scope.row)">{{ t('common.edit') }}</el-button>
          <el-button text size="small" type="danger" @click="removeOne(scope.row)">{{ t('common.delete') }}</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @change="reload"
      />
    </div>

    <el-dialog v-model="editVisible" :title="editMode === 'create' ? t('panels.relationGraph.addRelation') : t('panels.relationGraph.editRelation')" width="680px">
      <el-form label-width="120px">
        <el-form-item :label="t('panels.relationGraph.entityA')"><el-input v-model="form.source" /></el-form-item>
        <el-form-item :label="t('panels.relationGraph.relationType')">
          <el-select v-model="form.kind_cn" :placeholder="t('panels.relationGraph.selectRelationType')">
            <el-option v-for="k in kindOptions" :key="k" :label="k" :value="k" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('panels.relationGraph.entityB')"><el-input v-model="form.target" /></el-form-item>
        <el-form-item :label="t('panels.relationGraph.stance')">
          <el-select v-model="form.stance" clearable>
            <el-option v-for="s in stanceOptions" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('panels.relationGraph.fact')"><el-input v-model="form.fact" type="textarea" :rows="2" /></el-form-item>
        <el-form-item :label="t('panels.relationGraph.aCallsB')"><el-input v-model="form.a_to_b_addressing" /></el-form-item>
        <el-form-item :label="t('panels.relationGraph.bCallsA')"><el-input v-model="form.b_to_a_addressing" /></el-form-item>
        <el-form-item :label="t('panels.relationGraph.recentDialogues')">
          <el-input v-model="form.dialoguesText" type="textarea" :rows="3" :placeholder="t('panels.relationGraph.onePerLine')" />
        </el-form-item>
        <el-form-item :label="t('panels.relationGraph.recentEvents')">
          <el-input v-model="form.eventsText" type="textarea" :rows="3" :placeholder="t('panels.relationGraph.oneSummaryPerLine')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="submitEdit">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="batchKindVisible" :title="t('panels.relationGraph.batchModifyKind')" width="420px">
      <el-select v-model="batchKind" :placeholder="t('panels.relationGraph.selectNewType')" style="width: 100%">
        <el-option v-for="k in kindOptions" :key="k" :label="k" :value="k" />
      </el-select>
      <template #footer>
        <el-button @click="batchKindVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="applyBatchKind">{{ t('common.confirm') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="batchStanceVisible" :title="t('panels.relationGraph.batchModifyStance')" width="420px">
      <el-select v-model="batchStance" clearable :placeholder="t('panels.relationGraph.selectNewStance')" style="width: 100%">
        <el-option v-for="s in stanceOptions" :key="s" :label="s" :value="s" />
      </el-select>
      <template #footer>
        <el-button @click="batchStanceVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="applyBatchStance">{{ t('common.confirm') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="batchEventsVisible" :title="t('panels.relationGraph.batchAppendEventsTitle')" width="520px">
      <el-input v-model="batchEventsText" type="textarea" :rows="6" :placeholder="t('panels.relationGraph.oneEventPerLine')" />
      <template #footer>
        <el-button @click="batchEventsVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="applyBatchEvents">{{ t('common.confirm') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="batchCreateVisible" :title="t('panels.relationGraph.batchAddRelation')" width="680px">
      <div class="tip">{{ t('panels.relationGraph.batchCreateTip') }}</div>
      <el-input v-model="batchCreateText" type="textarea" :rows="12" />
      <template #footer>
        <el-button @click="batchCreateVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="submitBatchCreate">{{ t('panels.relationGraph.submit') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="importVisible" :title="t('panels.relationGraph.importRelationGraph')" width="680px">
      <div class="toolbar compact">
        <el-select v-model="importFormat" class="w-select">
          <el-option label="JSON" value="json" />
          <el-option label="CSV" value="csv" />
        </el-select>
        <el-button @click="pickFile">{{ t('panels.relationGraph.readFromFile') }}</el-button>
      </div>
      <input ref="fileInputRef" type="file" class="hidden" @change="onFileChange" />
      <el-input v-model="importContent" type="textarea" :rows="12" />
      <template #footer>
        <el-button @click="importVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="submitImport">{{ t('common.import') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useProjectStore } from '@renderer/stores/useProjectStore'
import {
  batchAppendEventsRelationGraph,
  batchCreateRelationGraph,
  batchDeleteRelationGraph,
  batchUpdateKindRelationGraph,
  batchUpdateStanceRelationGraph,
  deleteRelationGraph,
  exportRelationGraph,
  getRelationGraphMeta,
  importRelationGraph,
  listRelationGraph,
  upsertRelationGraph,
  type RelationGraphKind,
  type RelationGraphKey,
  type RelationGraphRecord,
  type RelationGraphStance,
} from '@renderer/api/relationGraph'

const { t } = useI18n()

const props = defineProps<{ refreshSeq?: number }>()

const projectStore = useProjectStore()
const loading = ref(false)
const rows = ref<RelationGraphRecord[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const selectedRows = ref<RelationGraphRecord[]>([])

const filters = reactive<{ keyword: string; kind: RelationGraphKind | ''; stance: RelationGraphStance | '' }>({
  keyword: '',
  kind: '',
  stance: '',
})

const kindOptions = ref<RelationGraphKind[]>([])
const stanceOptions = ref<RelationGraphStance[]>([])

const editVisible = ref(false)
const editMode = ref<'create' | 'edit'>('create')
const editingKey = ref<RelationGraphKey | null>(null)
const form = reactive({
  source: '',
  target: '',
  kind_cn: '' as RelationGraphKind | '',
  stance: '' as RelationGraphStance | '',
  fact: '',
  a_to_b_addressing: '',
  b_to_a_addressing: '',
  dialoguesText: '',
  eventsText: '',
})

const batchKindVisible = ref(false)
const batchKind = ref<RelationGraphKind | ''>('')
const batchStanceVisible = ref(false)
const batchStance = ref<RelationGraphStance | ''>('')
const batchEventsVisible = ref(false)
const batchEventsText = ref('')
const batchCreateVisible = ref(false)
const batchCreateText = ref('')

const importVisible = ref(false)
const importFormat = ref<'json' | 'csv'>('json')
const importContent = ref('')
const fileInputRef = ref<HTMLInputElement | null>(null)

const selectedKeys = computed<RelationGraphKey[]>(() =>
  selectedRows.value
    .filter((r) => !!r.source && !!r.target && !!r.kind_en)
    .map((r) => ({ source: r.source!, target: r.target!, kind_en: r.kind_en! }))
)

function getProjectId(): number {
  const pid = projectStore.currentProject?.id
  if (!pid) throw new Error(t('panels.relationGraph.selectProjectFirst'))
  return pid
}

function parseLines(text: string): string[] {
  return (text || '').split(/\r?\n/).map((x) => x.trim()).filter(Boolean)
}

function resetForm() {
  form.source = ''
  form.target = ''
  form.kind_cn = ''
  form.stance = ''
  form.fact = ''
  form.a_to_b_addressing = ''
  form.b_to_a_addressing = ''
  form.dialoguesText = ''
  form.eventsText = ''
}

function openCreate() {
  editMode.value = 'create'
  editingKey.value = null
  resetForm()
  editVisible.value = true
}

function openEdit(row: RelationGraphRecord) {
  editMode.value = 'edit'
  editingKey.value = { source: row.source!, target: row.target!, kind_en: row.kind_en! }
  form.source = row.source || ''
  form.target = row.target || ''
  form.kind_cn = ((row.kind_cn || row.kind || '') as RelationGraphKind | '')
  form.stance = ((row.stance || '') as RelationGraphStance | '')
  form.fact = row.fact || ''
  form.a_to_b_addressing = row.a_to_b_addressing || ''
  form.b_to_a_addressing = row.b_to_a_addressing || ''
  form.dialoguesText = (row.recent_dialogues || []).join('\n')
  form.eventsText = (row.recent_event_summaries || []).map((e: any) => e.summary || '').filter(Boolean).join('\n')
  editVisible.value = true
}

async function reload() {
  try {
    const projectId = getProjectId()
    loading.value = true
    const resp = await listRelationGraph({
      project_id: projectId,
      keyword: filters.keyword || undefined,
      kinds: filters.kind ? [filters.kind] : [],
      stances: filters.stance ? [filters.stance] : [],
      offset: (page.value - 1) * pageSize.value,
      limit: pageSize.value,
    })
    rows.value = resp.items || []
    total.value = resp.total || 0
  } catch (e: any) {
    ElMessage.error(e?.message || t('panels.relationGraph.loadRelationGraphFailed'))
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.keyword = ''
  filters.kind = ''
  filters.stance = ''
  page.value = 1
  reload()
}

function onSelectionChange(list: RelationGraphRecord[]) {
  selectedRows.value = list || []
}

async function submitEdit() {
  try {
    const projectId = getProjectId()
    const saved = await upsertRelationGraph({
      project_id: projectId,
      relation: {
        source: form.source,
        target: form.target,
        kind_cn: form.kind_cn || undefined,
        fact: form.fact || undefined,
        a_to_b_addressing: form.a_to_b_addressing || undefined,
        b_to_a_addressing: form.b_to_a_addressing || undefined,
        stance: form.stance || undefined,
        recent_dialogues: parseLines(form.dialoguesText),
        recent_event_summaries: parseLines(form.eventsText).map((summary) => ({ summary })),
      },
    })

    if (editMode.value === 'edit' && editingKey.value) {
      const oldKey = editingKey.value
      const changedKey =
        oldKey.source !== saved.source ||
        oldKey.target !== saved.target ||
        oldKey.kind_en !== saved.kind_en
      if (changedKey) {
        await deleteRelationGraph({ project_id: projectId, key: oldKey })
      }
    }

    editVisible.value = false
    ElMessage.success(t('common.saveSuccess'))
    reload()
  } catch (e: any) {
    ElMessage.error(e?.message || t('panels.relationGraph.saveFailed'))
  }
}

async function removeOne(row: RelationGraphRecord) {
  try {
    const projectId = getProjectId()
    await ElMessageBox.confirm(t('panels.relationGraph.confirmDeleteRelation', { source: row.source, target: row.target }), t('panels.relationGraph.deleteConfirmTitle'), { type: 'warning' })
    await deleteRelationGraph({ project_id: projectId, key: { source: row.source!, target: row.target!, kind_en: row.kind_en! } })
    ElMessage.success(t('common.deleteSuccess'))
    reload()
  } catch {}
}

async function batchDelete() {
  try {
    const projectId = getProjectId()
    await ElMessageBox.confirm(t('panels.relationGraph.confirmBatchDelete', { count: selectedKeys.value.length }), t('panels.relationGraph.batchDeleteTitle'), { type: 'warning' })
    const resp = await batchDeleteRelationGraph({ project_id: projectId, keys: selectedKeys.value })
    ElMessage.success(t('panels.relationGraph.deletedCount', { count: resp.affected || 0 }))
    reload()
  } catch {}
}

async function applyBatchKind() {
  try {
    const projectId = getProjectId()
    const resp = await batchUpdateKindRelationGraph({
      project_id: projectId,
      keys: selectedKeys.value,
      new_kind_cn: batchKind.value || undefined,
    })
    ElMessage.success(t('panels.relationGraph.updatedCount', { count: resp.affected || 0 }))
    batchKindVisible.value = false
    batchKind.value = ''
    reload()
  } catch (e: any) {
    ElMessage.error(e?.message || t('panels.relationGraph.batchUpdateFailed'))
  }
}

async function applyBatchStance() {
  try {
    const projectId = getProjectId()
    const resp = await batchUpdateStanceRelationGraph({
      project_id: projectId,
      keys: selectedKeys.value,
      stance: batchStance.value || undefined,
    })
    ElMessage.success(t('panels.relationGraph.updatedCount', { count: resp.affected || 0 }))
    batchStanceVisible.value = false
    batchStance.value = ''
    reload()
  } catch (e: any) {
    ElMessage.error(e?.message || t('panels.relationGraph.batchUpdateFailed'))
  }
}

async function applyBatchEvents() {
  try {
    const projectId = getProjectId()
    const events = parseLines(batchEventsText.value).map((summary) => ({ summary }))
    const resp = await batchAppendEventsRelationGraph({ project_id: projectId, keys: selectedKeys.value, events, max_size: 20 })
    ElMessage.success(t('panels.relationGraph.updatedCount', { count: resp.affected || 0 }))
    batchEventsVisible.value = false
    batchEventsText.value = ''
    reload()
  } catch (e: any) {
    ElMessage.error(e?.message || t('panels.relationGraph.batchUpdateFailed'))
  }
}

function openBatchCreate() {
  batchCreateVisible.value = true
}

function parseBatchCreateInput(text: string) {
  const trimmed = text.trim()
  if (!trimmed) return []
  if (trimmed.startsWith('[')) {
    const arr = JSON.parse(trimmed)
    if (!Array.isArray(arr)) throw new Error(t('panels.relationGraph.jsonMustBeArray'))
    return arr
  }
  return parseLines(trimmed).map((line) => {
    const [source, target, kind_cn, stance] = line.split(',').map((x) => x.trim())
    return { source, target, kind_cn, stance }
  })
}

async function submitBatchCreate() {
  try {
    const projectId = getProjectId()
    const relations = parseBatchCreateInput(batchCreateText.value)
    const resp = await batchCreateRelationGraph({ project_id: projectId, relations })
    ElMessage.success(t('panels.relationGraph.processedCount', { count: resp.affected || 0 }))
    batchCreateVisible.value = false
    batchCreateText.value = ''
    reload()
  } catch (e: any) {
    ElMessage.error(e?.message || t('panels.relationGraph.batchAddFailed'))
  }
}

function saveDownload(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime || 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

async function exportSelected(format: 'json' | 'csv') {
  try {
    const projectId = getProjectId()
    const resp = await exportRelationGraph({ project_id: projectId, format, keys: selectedKeys.value })
    saveDownload(resp.filename || `relation-graph.${format}`, resp.content || '', resp.mime_type || 'text/plain')
    ElMessage.success(t('panels.relationGraph.exportDone'))
  } catch (e: any) {
    ElMessage.error(e?.message || t('panels.relationGraph.exportFailed'))
  }
}

function openImport() {
  importVisible.value = true
}

function pickFile() {
  fileInputRef.value?.click()
}

async function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  importContent.value = await file.text()
}

async function submitImport() {
  try {
    const projectId = getProjectId()
    const resp = await importRelationGraph({ project_id: projectId, format: importFormat.value, content: importContent.value })
    ElMessage.success(t('panels.relationGraph.importResult', { created: resp.created || 0, updated: resp.updated || 0, failed: resp.failed || 0 }))
    if ((resp.errors || []).length > 0) {
      ElMessage.warning(t('panels.relationGraph.importErrors', { count: resp.errors?.length }))
    }
    importVisible.value = false
    reload()
  } catch (e: any) {
    ElMessage.error(e?.message || t('panels.relationGraph.importFailed'))
  }
}

async function loadMeta() {
  try {
    const meta = await getRelationGraphMeta()
    kindOptions.value = (meta.kinds || []).map((item) => item.kind_cn).filter(Boolean)
    stanceOptions.value = (meta.stances || []).filter(Boolean)
  } catch (e: any) {
    ElMessage.error(e?.message || t('panels.relationGraph.loadMetaFailed'))
  }
}

onMounted(async () => {
  await loadMeta()
  reload()
})

watch(() => props.refreshSeq, (next, prev) => {
  if (next !== prev) {
    reload()
  }
})
</script>

<style scoped>
.relation-graph-panel { display: flex; flex-direction: column; gap: 12px; padding: 12px; height: 100%; }
.toolbar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.toolbar.compact { padding: 0 0 8px 0; }
.actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.w-keyword { width: 280px; }
.w-select { width: 140px; }
.pager { display: flex; justify-content: flex-end; padding-top: 8px; }
.hidden { display: none; }
.tip { color: var(--el-text-color-secondary); font-size: 12px; margin-bottom: 8px; }
.toolbar .el-button, .actions .el-button { white-space: nowrap; }
:deep(.el-table th .cell) { white-space: nowrap; }
</style>