<template>
  <el-form-item :label="label" :prop="prop">
    <el-select
      :model-value="modelValue"
      @update:modelValue="emit('update:modelValue', $event)"
      :placeholder="placeholder"
      :loading="isLoading"
      :no-data-text="noDataText"
      clearable
      style="width: 100%"
    >
      <el-option
        v-for="item in resolvedOptions"
        :key="String(item)"
        :label="getOptionLabel(item)"
        :value="item"
      />
    </el-select>
  </el-form-item>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { JSONSchema } from '@renderer/api/schema'
import { resolveKnowledgeOptions } from '@renderer/services/knowledgeOptionResolver'

const props = defineProps<{
  modelValue: string | number | undefined
  label: string
  prop: string
  schema: JSONSchema
}>()

const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()
const knowledgeOptions = ref<Array<string | number>>([])
const isLoading = ref(false)

function entityTypeLabel(key: string): string {
  switch (key) {
    case 'character': return t('misc.entityCharacter')
    case 'scene': return t('misc.entityScene')
    case 'organization': return t('misc.entityOrganization')
    case 'item': return t('misc.entityItem')
    case 'concept': return t('misc.entityConcept')
    default: return key
  }
}

watch(
  () => props.schema['x-knowledge-source'],
  async (knowledgeName) => {
    if (!knowledgeName) {
      knowledgeOptions.value = []
      return
    }

    isLoading.value = true
    knowledgeOptions.value = await resolveKnowledgeOptions(knowledgeName)
    isLoading.value = false
  },
  { immediate: true }
)

const resolvedOptions = computed(() => {
  const baseOptions = (props.schema.enum && props.schema.enum.length > 0)
    ? props.schema.enum
    : knowledgeOptions.value

  if (
    props.modelValue !== undefined
    && props.modelValue !== null
    && props.modelValue !== ''
    && !baseOptions.includes(props.modelValue)
  ) {
    return [props.modelValue, ...baseOptions]
  }

  return baseOptions
})

const placeholder = computed(() => {
  return props.schema.description || t('misc.selectPlaceholder', { label: props.label })
})

const noDataText = computed(() => {
  if (isLoading.value) {
    return t('misc.loadingOptions')
  }
  if (props.schema['x-knowledge-source']) {
    return t('misc.noOptionsFound')
  }
  return t('misc.noOptions')
})

function getOptionLabel(item: string | number): string {
  const raw = String(item)
  if (props.prop === 'entity_type') {
    return entityTypeLabel(raw)
  }
  return raw
}
</script>