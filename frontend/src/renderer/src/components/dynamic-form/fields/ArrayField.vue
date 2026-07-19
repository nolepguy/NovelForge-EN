<template>
  <el-card shadow="never" class="array-field-card">
    <template #header>
      <div class="card-header">
        <span>{{ label }}</span>
      </div>
    </template>

    <div v-if="!modelValue || modelValue.length === 0" class="empty-state">
      <p>{{ t('misc.noItems') }}</p>
    </div>

    <div v-for="(item, index) in modelValue" :key="index" class="array-item">
      <div class="array-item-content">
        <!-- For simple types, use the corresponding field component directly -->
        <component
          v-if="isSimpleTypeForIndex(index)"
          :is="getSimpleFieldComponentForIndex(index)"
          :label="t('misc.itemN', { n: index + 1 })"
          :prop="String(index)"
          :schema="getItemSchemaForIndex(index)"
          :model-value="item"
          @update:modelValue="updateItem(index, $event)"
        />
        <!-- For tuple types (array + prefixItems/anyOf), use TupleField to render each element -->
        <TupleField
          v-else-if="isTupleTypeForIndex(index)"
          :label="t('misc.itemN', { n: index + 1 })"
          :prop="String(index)"
          :schema="getItemSchemaForIndex(index)"
          :model-value="item"
          @update:modelValue="updateItem(index, $event)"
        />
        <!-- For complex object types, use ModelDrivenForm -->
        <ModelDrivenForm
          v-else
          :schema="getItemSchemaForIndex(index)"
          :model-value="item"
          :display-name-map="displayNameMap"
          @update:modelValue="updateItem(index, $event)"
        />
      </div>
      <div class="array-item-actions">
        <el-button
          type="danger"
          :icon="Delete"
          circle
          plain
          size="small"
          @click="removeItem(index)"
        />
      </div>
    </div>
    <el-button type="primary" :icon="Plus" plain @click="addItem" class="add-button">
      {{ t('misc.addItemName', { name: (displayNameMap && displayNameMap[itemSchema.title || '']) || itemSchema.title || t('misc.newItem') }) }}
    </el-button>
  </el-card>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue'
import { useI18n } from 'vue-i18n'
import type { JSONSchema } from '@renderer/api/schema'
import { Delete, Plus } from '@element-plus/icons-vue'
import { resolveActualSchema } from '@renderer/services/schemaFieldParser'

const ModelDrivenForm = defineAsyncComponent(() => import('../ModelDrivenForm.vue'))
const StringField = defineAsyncComponent(() => import('./StringField.vue'))
const NumberField = defineAsyncComponent(() => import('./NumberField.vue'))
const BooleanField = defineAsyncComponent(() => import('./BooleanField.vue'))
const TupleField = defineAsyncComponent(() => import('./TupleField.vue'))

const props = defineProps<{
  modelValue: any[] | undefined
  label: string
  schema: JSONSchema
  displayNameMap?: Record<string, string>
  readonly?: boolean
  contextData?: Record<string, any>
  ownerId?: number | null // ID passed from the outermost level
}>()

const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()


/**
 * Recursively resolve the schema, handling $ref and anyOf (Optional)
 */
// Removed duplicate resolveActualSchema function, use the shared service

const itemSchema = computed((): JSONSchema => {
  if (props.schema.items) {
    return resolveActualSchema(props.schema.items, props.schema)
  }
  return { type: 'string', title: t('misc.item') }
})

function getItemSchemaForIndex(index: number): JSONSchema {
  const base = itemSchema.value
  const value = (props.modelValue || [])[index]
  if ((base as any).anyOf) {
    const matched = resolveAnyOfForValue(base, value)
    if (matched) return matched
  }
  return base
}

// Determine if it's a simple type (by index)
function isSimpleTypeForIndex(index: number) {
  const actualSchema = getItemSchemaForIndex(index)
  return actualSchema.type === 'string' || actualSchema.type === 'number' || actualSchema.type === 'integer' || actualSchema.type === 'boolean'
}

// Determine if the array item is a tuple type (itself an array with prefixItems/anyOf)
function isTupleTypeForIndex(index: number) {
  const actualSchema = getItemSchemaForIndex(index) as any
  if (!actualSchema || actualSchema.type !== 'array') return false
  return Array.isArray(actualSchema.prefixItems) || Array.isArray(actualSchema.anyOf)
}

// Get the field component for a simple type (by index)
function getSimpleFieldComponentForIndex(index: number) {
  const actualSchema = getItemSchemaForIndex(index)
  switch (actualSchema.type) {
    case 'string':
      return StringField
    case 'number':
    case 'integer':
      return NumberField
    case 'boolean':
      return BooleanField
    default:
      return StringField
  }
}

function updateItem(index: number, newItem: any) {
  const newArray = [...(props.modelValue || [])]
  newArray[index] = newItem
  emit('update:modelValue', newArray)
}

function removeItem(index: number) {
  const newArray = [...(props.modelValue || [])]
  newArray.splice(index, 1)
  emit('update:modelValue', newArray)
}

function addItem() {
  const newArray = [...(props.modelValue || [])]
  const base = itemSchema.value
  let defaultValue: any

  if ((base as any).anyOf) {
    // Default new entry is character; switch via entity_type in UI
    defaultValue = { name: '', entity_type: 'character', life_span: 'Short Term' }
  } else {
    defaultValue = createArrayItemDefaultValue(base)
  }

  newArray.push(defaultValue)
  emit('update:modelValue', newArray)
}

/**
 * Intelligently create a valid default value for any schema, handling nested objects.
 */
// Removed duplicate createDefaultValue function, use the shared service

/**
 * Create a default value for an array item, ensuring compatibility with ModelDrivenForm
 */
function createArrayItemDefaultValue(schema: JSONSchema): any {
  const actualSchema = resolveActualSchema(schema, props.schema)

  if (actualSchema.default !== undefined) {
    return actualSchema.default
  }

  switch (actualSchema.type) {
    case 'string': return ''
    case 'number':
    case 'integer': return 0
    case 'boolean': return false
    case 'array': return []
    case 'object': return {}
    default: return null
  }
}

function resolveAnyOfForValue(base: JSONSchema, value: any): JSONSchema | null {
  if (!base.anyOf) return null

  // Simple implementation: find the first non-null schema
  const nonNullSchema = base.anyOf.find((s: any) => s && s.type !== 'null')
  return nonNullSchema ? resolveActualSchema(nonNullSchema as JSONSchema, props.schema) : null
}
</script>

<style scoped>
.array-field-card {
  margin-top: 10px;
  margin-bottom: 20px;
  background-color: var(--el-fill-color-lighter);
}
.empty-state {
  text-align: center;
  color: var(--el-text-color-secondary);
  padding: 20px 0;
}
.array-item {
  display: flex;
  align-items: flex-start;
  margin-bottom: 15px;
  padding: 15px;
  border: 1px dashed var(--el-border-color);
  border-radius: 4px;
}
.array-item-content {
  flex-grow: 1;
  padding-right: 15px;
}
.array-item-actions {
  flex-shrink: 0;
}
.add-button {
  margin-top: 10px;
  width: 100%;
}
</style>
