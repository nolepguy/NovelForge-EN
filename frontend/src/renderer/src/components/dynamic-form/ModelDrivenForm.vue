<template>
  <div v-if="schema && modelValue !== undefined && typeof modelValue === 'object'" class="model-driven-form">
    <el-card shadow="never" class="form-card">
      <el-form :model="modelValue" label-position="top">
        <template v-for="(propSchema, propName) in visibleProperties" :key="propName">
          <component
            :is="getFieldComponent(propSchema)"
            :label="getFieldLabel(String(propName), propSchema)"
            :prop="String(propName)"
            :schema="resolveActualSchema(propSchema)"
            :display-name-map="displayNameMap"
            :model-value="modelValue[propName]"
            :readonly="readonlyFields.includes(String(propName))"
            :contextData="modelValue"
            :owner-id="ownerId"
            @update:modelValue="updateModel(String(propName), $event)"
          />
        </template>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { defineAsyncComponent, computed } from 'vue'
import type { JSONSchema } from '@renderer/api/schema'
import { schemaService } from '@renderer/api/schema'
import { resolveActualSchema as resolveSchemaUnified } from '@renderer/services/schemaFieldParser'

// --- Component imports ---
const StringField = defineAsyncComponent(() => import('./fields/StringField.vue'))
const NumberField = defineAsyncComponent(() => import('./fields/NumberField.vue'))
const BooleanField = defineAsyncComponent(() => import('./fields/BooleanField.vue'))
const ObjectField = defineAsyncComponent(() => import('./fields/ObjectField.vue'))
const ArrayField = defineAsyncComponent(() => import('./fields/ArrayField.vue'))
const EnumField = defineAsyncComponent(() => import('./fields/EnumField.vue'))
const TupleField = defineAsyncComponent(() => import('./fields/TupleField.vue'))
// Default fallback component for unsupported types
const FallbackField = defineAsyncComponent(() => import('./fields/FallbackField.vue'))

// --- Props & Emits ---
const props = defineProps<{
  schema: JSONSchema | undefined
  modelValue: Record<string, any>
  displayNameMap?: Record<string, string>
  readonlyFields?: string[]
  contextData?: Record<string, any>
  ownerId?: number | null
  includeFields?: string[]
  excludeFields?: string[]
}>()

const emit = defineEmits(['update:modelValue'])

// --- Default values ---
const readonlyFields = props.readonlyFields || []

const visibleProperties = computed(() => {
  const all = (props.schema?.properties || {}) as Record<string, JSONSchema>
  const entries = Object.entries(all)
  const included = props.includeFields && props.includeFields.length > 0
    ? entries.filter(([k]) => props.includeFields!.includes(k))
    : entries
  const excluded = props.excludeFields && props.excludeFields.length > 0
    ? included.filter(([k]) => !props.excludeFields!.includes(k))
    : included
  return Object.fromEntries(excluded)
})

// --- Logic ---
function resolveActualSchema(schema: JSONSchema): JSONSchema {
  // Use the unified schema resolver service
  return resolveSchemaUnified(schema, props.schema) as JSONSchema
}

function getFieldComponent(propSchema: JSONSchema) {
  const actualSchema = resolveActualSchema(propSchema);
  if (
    (actualSchema.enum && actualSchema.enum.length > 0)
    || actualSchema['x-knowledge-source']
  ) {
    return EnumField
  }
  if (actualSchema.type === 'array' && (actualSchema.prefixItems || actualSchema.anyOf)) {
    if (actualSchema.anyOf && !actualSchema.prefixItems) {
       return TupleField
    }
    if(actualSchema.prefixItems){
      return TupleField
    }
  }
  switch (actualSchema.type) {
    case 'string':
      return StringField
    case 'number':
    case 'integer':
      return NumberField
    case 'boolean':
      return BooleanField
    case 'object':
      return ObjectField
    case 'array':
      return ArrayField
    default:
      console.warn(`Unsupported field type: ${actualSchema.type} (property: ${actualSchema.title}). Fallback component used.`)
      return FallbackField
  }
}

function getFieldLabel(propName: string, propSchema: JSONSchema): string {
  const actualSchema = resolveActualSchema(propSchema)
  return (props.displayNameMap && props.displayNameMap[propName])
    || (propSchema as any).title
    || (actualSchema as any).title
    || propName
}

function updateModel(propName: string, value: any) {
  const newModel = { ...props.modelValue, [propName]: value }
  emit('update:modelValue', newModel)
}
</script>

<style scoped>
.model-driven-form { padding: 0; }
.form-card { border: none; }
:deep(.el-card__body) { padding: 20px; }
</style> 
