<template>
  <div class="card-filter-bar">
    <div class="left">
      <el-input v-model="keyword" :placeholder="t('misc.searchCardTitle')" clearable class="search-input" @clear="emitChange" @input="emitChange">
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-select v-model="selectedTypes" multiple collapse-tags :placeholder="t('misc.typeFilter')" class="type-select" @change="emitChange">
        <el-option v-for="t in typeOptions" :key="t.value" :label="t.label" :value="t.value" />
      </el-select>
    </div>
    <div class="right">
      <el-select v-model="sortKey" class="sort-select" @change="emitChange">
        <el-option :label="t('misc.sortRecent')" value="recent" />
        <el-option :label="t('misc.sortTitle')" value="title" />
        <el-option :label="t('misc.sortType')" value="type" />
      </el-select>
      <el-segmented v-model="density" :options="densityOptions" @change="emitChange" class="density-seg" />
      <el-segmented v-model="viewMode" :options="viewOptions" @change="emitChange" class="view-seg" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { ElInput, ElSelect, ElOption, ElSegmented, ElIcon } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import type { components } from '@renderer/types/generated'

const props = defineProps<{ cardTypes: components['schemas']['CardTypeRead'][] }>()
const { t } = useI18n()
const emit = defineEmits<{
  (e: 'change', payload: { keyword: string; types: number[]; sortKey: 'recent'|'title'|'type'; density: 'comfortable'|'compact'; view: 'card'|'list' }): void
}>()

const keyword = ref('')
const selectedTypes = ref<number[]>([])
const sortKey = ref<'recent'|'title'|'type'>('recent')
const density = ref<'comfortable'|'compact'>('comfortable')
const viewMode = ref<'card'|'list'>('card')

const densityOptions = computed(() => [{ label: t('misc.comfortable'), value: 'comfortable' }, { label: t('misc.compact'), value: 'compact' }])
const viewOptions = computed(() => [{ label: t('misc.cardView'), value: 'card' }, { label: t('misc.listView'), value: 'list' }])

const typeOptions = computed(() => (props.cardTypes || []).map(t => ({ label: t.name, value: t.id! })))

function emitChange() {
  emit('change', { keyword: keyword.value, types: selectedTypes.value, sortKey: sortKey.value, density: density.value, view: viewMode.value })
}
</script>

<style scoped>
.card-filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding: 8px 0 16px 0;
}
.left { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; flex: 1; }
.right { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
.search-input { max-width: 360px; width: 100%; }
.type-select { min-width: 220px; }
.sort-select { width: 140px; }
.density-seg, .view-seg { --el-segmented-padding: 2px; }
</style> 