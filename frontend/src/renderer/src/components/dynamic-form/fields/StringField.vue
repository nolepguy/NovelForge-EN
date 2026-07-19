<template>
  <el-form-item :label="label" :prop="prop">
    <el-input
      v-if="!isLongText"
      :model-value="modelValue"
      @update:modelValue="emit('update:modelValue', $event)"
      :placeholder="placeholder"
      clearable
    />
    <el-input
      v-else
      type="textarea"
      :model-value="modelValue"
      @update:modelValue="emit('update:modelValue', $event)"
      :placeholder="placeholder"
      :autosize="{ minRows: 3, maxRows: 10 }"
      clearable
    />
  </el-form-item>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { JSONSchema } from '@renderer/api/schema'

const props = defineProps<{
  modelValue: string | undefined
  label: string
  prop: string
  schema: JSONSchema
}>()

const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()

// A simple heuristic: if the description or title indicates it is a long-text field, use a textarea.
// A more robust solution might include a custom attribute in the schema, such as `x-ui-control: 'textarea'`.
const isLongText = computed(() => {
  // New rule: if the schema defines minLength greater than 50, treat it as long text.
  if (props.schema.minLength !== undefined && props.schema.minLength > 50) {
    return true
  }
  const description = props.schema.description?.toLowerCase() || ''
  const title = props.schema.title?.toLowerCase() || ''
  // If the field name is overview, force textarea
  if (props.prop === 'overview'||props.prop==='content') return true
  return (
    description.includes('thinking') ||
    description.includes('process') ||
    description.includes('description') ||
    description.includes('overview') ||
    title.includes('thinking')
  )
})

const placeholder = computed(() => {
  return props.schema.description || t('misc.enterPrompt', { label: props.label })
})
</script>
