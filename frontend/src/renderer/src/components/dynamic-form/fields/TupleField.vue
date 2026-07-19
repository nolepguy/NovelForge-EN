<template>
  <el-form-item :label="label" :prop="prop">
    <div class="tuple-field-wrapper">
      <div v-for="(itemSchema, index) in itemSchemas" :key="index" class="tuple-item">
        <component
          :is="getFieldComponent(itemSchema)"
          :model-value="modelValue ? modelValue[index] : undefined"
          @update:modelValue="updateItem(index, $event)"
          :schema="itemSchema"
          label=""
          prop=""
        />
      </div>
    </div>
  </el-form-item>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue'
import type { JSONSchema } from '@renderer/api/schema'

// Avoid circular dependencies
const StringField = defineAsyncComponent(() => import('./StringField.vue'))
const NumberField = defineAsyncComponent(() => import('./NumberField.vue'))
const BooleanField = defineAsyncComponent(() => import('./BooleanField.vue'))
const FallbackField = defineAsyncComponent(() => import('./FallbackField.vue'))

const props = defineProps<{
  modelValue: any[] | undefined
  label: string
  prop: string
  schema: JSONSchema
}>()

const emit = defineEmits(['update:modelValue'])

// Determine the schema for each tuple element based on the schema
const itemSchemas = computed((): JSONSchema[] => {
  return props.schema.prefixItems || props.schema.anyOf || []
})

// Dynamically get the field component to use for each tuple element
function getFieldComponent(itemSchema: JSONSchema) {
  if (itemSchema.enum && itemSchema.enum.length > 0) {
    // Enums within a tuple are uncommon, but just in case
    // return EnumField - for simplicity, enums are not handled here for now
  }
  switch (itemSchema.type) {
    case 'string':
      return StringField
    case 'number':
    case 'integer':
      return NumberField
    case 'boolean':
      return BooleanField
    default:
      return FallbackField
  }
}

function updateItem(index: number, value: any) {
  const newTuple = [...(props.modelValue || [])]
  newTuple[index] = value
  emit('update:modelValue', newTuple)
}
</script>

<style scoped>
.tuple-field-wrapper {
  display: flex;
  gap: 10px;
  width: 100%;
}

.tuple-item {
  flex-grow: 1;
}

/* Remove default margin of inline el-form-item */
:deep(.el-form-item) {
  margin-bottom: 0;
}
</style> 