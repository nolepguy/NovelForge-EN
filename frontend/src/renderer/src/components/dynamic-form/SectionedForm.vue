<template>
  <div class="sectioned-form">
    <el-collapse v-model="activeNames">
      <el-collapse-item v-for="(sec, idx) in sections" :key="idx" :name="String(idx)">
        <template #title>
          <span class="sec-title">{{ sec.title }}</span>
          <span class="sec-desc" v-if="sec.description">{{ sec.description }}</span>
        </template>
        <ModelDrivenForm
          :schema="schema"
          v-model="proxy"
          :include-fields="sec.include"
          :exclude-fields="sec.exclude"
        />
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import type { JSONSchema } from '@renderer/api/schema'
import ModelDrivenForm from './ModelDrivenForm.vue'
import type { SectionConfig } from '@renderer/services/uiLayoutService'

const props = defineProps<{ schema: JSONSchema | undefined; modelValue: any; sections: SectionConfig[] }>()
const emit = defineEmits(['update:modelValue'])

const proxy = ref<any>(props.modelValue)
watch(() => props.modelValue, v => proxy.value = v, { deep: true })
watch(proxy, v => emit('update:modelValue', v), { deep: true })

const activeNames = ref<string[]>([])

// Initialize expanded state when sections are first received; try to preserve currently expanded items on subsequent updates
let initialized = false
watch(() => props.sections, (secs) => {
  const namesAll = secs.map((_, i) => String(i))
  if (!initialized) {
    // Expand sections not marked collapsed
    activeNames.value = secs.map((s, i) => (!s.collapsed ? String(i) : '')).filter(Boolean) as string[]
    initialized = true
    return
  }
  // Preserve still-existing expanded items and auto-expand newly appeared sections that are not collapsed
  const preserved = activeNames.value.filter(n => namesAll.includes(n))
  const newlyOpen = secs
    .map((s, i) => ({ i, s }))
    .filter(({ i, s }) => !s.collapsed && !preserved.includes(String(i)))
    .map(({ i }) => String(i))
  activeNames.value = [...preserved, ...newlyOpen]
}, { immediate: true })
</script>

<style scoped>
.sectioned-form { display: flex; flex-direction: column; gap: 8px; }
.sec-title { font-weight: 600; margin-right: 8px; }
.sec-desc { color: var(--el-text-color-secondary); font-size: 12px; }
</style> 