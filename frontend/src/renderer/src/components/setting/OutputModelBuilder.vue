<template>
  <div class="schema-builder">
    <div class="toolbar">
      <el-button type="primary" @click="addField">{{ t('settings.addField') }}</el-button>
    </div>
    <el-table :data="localFields" size="small" class="field-table">
      <el-table-column :label="t('common.action')" width="100" align="left">
        <template #default="{ $index }">
          <div class="ops-col">
            <el-button
              class="ops-btn"
              size="small"
              :disabled="$index === 0"
              @click="moveUp($index)"
              >{{ t('settings.moveUp') }}</el-button
            >
            <el-button
              class="ops-btn"
              size="small"
              :disabled="$index === localFields.length - 1"
              @click="moveDown($index)"
              >{{ t('settings.moveDown') }}</el-button
            >
            <el-button
              class="ops-btn"
              size="small"
              type="danger"
              plain
              @click="removeField($index)"
              >{{ t('common.delete') }}</el-button
            >
          </div>
        </template>
      </el-table-column>
      <el-table-column :label="t('common.name')" width="160">
        <template #default="{ row }">
          <el-input v-model="row.name" :placeholder="t('settings.fieldNamePlaceholder')" />
        </template>
      </el-table-column>
      <el-table-column :label="t('settings.displayNameCol')" width="160">
        <template #default="{ row }">
          <el-input v-model="row.label" :placeholder="t('settings.displayNamePlaceholder')" />
        </template>
      </el-table-column>
      <el-table-column :label="t('common.type')" width="160">
        <template #default="{ row }">
          <el-select v-model="row.kind" @change="onKindChange(row)">
            <el-option v-for="kind in baseKinds" :key="kind" :label="kind" :value="kind" />
            <el-option label="relation(embed)" value="relation" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column :label="t('settings.array')" width="90" align="center">
        <template #default="{ row }">
          <el-switch v-model="row.isArray" />
        </template>
      </el-table-column>
      <el-table-column :label="t('common.required')" width="100" align="center">
        <template #default="{ row }">
          <el-switch v-model="row.required" />
        </template>
      </el-table-column>
      <el-table-column :label="t('settings.aiExclude')" width="110" align="center">
        <template #default="{ row }">
          <el-switch v-model="row.aiExclude" />
        </template>
      </el-table-column>
      <el-table-column :label="t('settings.annotation')" min-width="240">
        <template #default="{ row }">
          <el-input v-model="row.description" :placeholder="t('settings.descriptionPlaceholder')" />
        </template>
      </el-table-column>
      <el-table-column :label="t('settings.example')" min-width="220">
        <template #default="{ row }">
          <el-input v-model="row.example" :placeholder="t('settings.examplePlaceholder')" />
        </template>
      </el-table-column>
      <el-table-column :label="t('settings.tupleElements')" min-width="260">
        <template #default="{ row }">
          <div v-if="row.kind === 'tuple'" class="tuple-editor">
            <div v-for="(_t, i) in row.tupleItems" :key="i" class="tuple-chip">
              <el-select v-model="row.tupleItems[i]" size="small" style="width: 120px">
                <el-option v-for="tk in tupleKinds" :key="tk" :label="tk" :value="tk" />
              </el-select>
              <el-button
                size="small"
                text
                type="danger"
                :disabled="(row.tupleItems?.length || 0) <= 1"
                @click="removeTupleItem(row, i)"
                >{{ t('common.delete') }}</el-button
              >
            </div>
            <el-button size="small" text type="primary" @click="addTupleItem(row)">{{
              t('settings.addElement')
            }}</el-button>
          </div>
          <div v-else class="rel-config muted">—</div>
        </template>
      </el-table-column>
      <el-table-column :label="t('settings.relationConfig')" min-width="240">
        <template #default="{ row }">
          <div v-if="row.kind === 'relation'" class="rel-config">
            <el-select
              v-model="row.relation.targetModelName"
              filterable
              :placeholder="t('settings.selectTargetModel')"
              style="width: 260px"
            >
              <el-option
                v-for="tm in targetModels"
                :key="tm.name"
                :label="tm.name"
                :value="tm.name"
                :disabled="isEmbedSelf(row, tm.name)"
              />
            </el-select>
          </div>
          <div v-else class="rel-config muted">—</div>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { type BuilderField } from '@renderer/utils/outputModelSchemaUtils'

const { t } = useI18n()

export interface OutputModelLite {
  name: string
  json_schema?: any
}

const props = defineProps<{
  modelValue: BuilderField[]
  models: OutputModelLite[]
  currentModelName?: string
}>()
const emit = defineEmits<{ 'update:modelValue': [value: BuilderField[]] }>()

const baseKinds: Array<BuilderField['kind']> = ['string', 'number', 'integer', 'boolean', 'tuple']
const tupleKinds: Array<NonNullable<BuilderField['tupleItems']>[number]> = [
  'string',
  'number',
  'integer',
  'boolean'
]

const localFields = ref<BuilderField[]>(props.modelValue?.map(cloneField) || [])
const syncingFromProps = ref(false)
watch(
  () => props.modelValue,
  async (v) => {
    syncingFromProps.value = true
    localFields.value = (v || []).map(cloneField)
    await nextTick()
    syncingFromProps.value = false
  }
)
watch(
  localFields,
  (v) => {
    if (!syncingFromProps.value) emit('update:modelValue', v)
  },
  { deep: true }
)

const targetModels = computed(() => props.models || [])

function cloneField(f: BuilderField): BuilderField {
  return JSON.parse(JSON.stringify(f))
}
function addField() {
  localFields.value.push({
    name: '',
    label: '',
    kind: 'string',
    isArray: false,
    required: false,
    aiExclude: false,
    relation: { targetModelName: null },
    description: '',
    example: '',
    tupleItems: []
  })
}
function removeField(idx: number) {
  localFields.value.splice(idx, 1)
}
function moveUp(idx: number) {
  if (idx <= 0) return
  const a = localFields.value
  ;[a[idx - 1], a[idx]] = [a[idx], a[idx - 1]]
}
function moveDown(idx: number) {
  const a = localFields.value
  if (idx >= a.length - 1) return
  ;[a[idx + 1], a[idx]] = [a[idx], a[idx + 1]]
}
function onKindChange(row: BuilderField) {
  if (row.kind !== 'relation') row.relation = { targetModelName: null }
  if (row.kind === 'tuple') {
    if (!Array.isArray(row.tupleItems) || row.tupleItems.length === 0)
      row.tupleItems = ['string', 'string']
  } else {
    row.tupleItems = []
  }
}
function isEmbedSelf(row: BuilderField, targetName: string) {
  return row.kind === 'relation' && props.currentModelName && props.currentModelName === targetName
}

function addTupleItem(row: BuilderField) {
  if (!Array.isArray(row.tupleItems)) row.tupleItems = []
  row.tupleItems.push('string')
}
function removeTupleItem(row: BuilderField, idx: number) {
  if (!Array.isArray(row.tupleItems)) return
  row.tupleItems.splice(idx, 1)
}
</script>

<style scoped>
:deep(.el-button) {
  white-space: nowrap;
}

.schema-builder {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.toolbar {
  display: flex;
  gap: 8px;
}
.toolbar :deep(.el-button) {
  white-space: nowrap;
}
.field-table {
  width: 100%;
}
.rel-config {
  display: flex;
  gap: 8px;
  align-items: center;
}
.muted {
  color: var(--el-text-color-secondary);
}
.tuple-editor {
  display: flex;
  gap: 6px;
  align-items: center;
  flex-wrap: wrap;
}
.tuple-chip {
  display: flex;
  gap: 6px;
  align-items: center;
}
.ops-col {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: flex-start;
  width: 100%;
}
.ops-col .el-button + .el-button {
  margin-left: 0 !important;
}
.ops-btn {
  width: 100%;
  box-sizing: border-box;
  padding-left: 0;
  padding-right: 0;
  display: block;
  white-space: nowrap;
}
</style>
