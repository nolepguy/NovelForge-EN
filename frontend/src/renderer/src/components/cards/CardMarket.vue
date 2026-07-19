<template>
  <div class="card-market">
    <CardFilterBar :card-types="cardTypes" @change="handleFilterChange" />
    <el-scrollbar>
      <div v-if="viewMode === 'card'">
        <div v-if="filteredCards.length > 0" class="card-grid" :class="{ compact: density==='compact' }">
          <el-card v-for="card in filteredCards" :key="card.id" class="card-item" shadow="hover">
            <template #header>
              <div class="card-header">
                <div class="header-left">
                  <el-tag size="small" effect="plain">{{ card.card_type.name }}</el-tag>
                  <span class="title">{{ card.title }}</span>
                </div>
                <div class="header-right">
                  <el-tooltip :content="t('common.edit')">
                    <el-button text size="small" @click="onEditCard(card.id)">{{ t('common.edit') }}</el-button>
                  </el-tooltip>
                  <el-popconfirm
                    :title="t('misc.confirmDeleteCard')"
                    :confirm-button-text="t('common.confirm')"
                    :cancel-button-text="t('common.cancel')"
                    @confirm="onDeleteCard(card.id)"
                  >
                    <template #reference>
                      <el-button text type="danger" size="small">{{ t('common.delete') }}</el-button>
                    </template>
                  </el-popconfirm>
                </div>
              </div>
            </template>
            <div class="card-content">
              <p class="meta">{{ t('misc.createdAt', { time: formatDate(card.created_at) }) }}</p>
            </div>
          </el-card>
        </div>
        <el-empty v-else :description="t('misc.noMatchingCards')" />
      </div>

      <div v-else>
        <el-table :data="filteredCards" size="small" border stripe>
          <el-table-column prop="title" :label="t('common.title')" />
          <el-table-column :label="t('common.type')" width="140">
            <template #default="{ row }">
              <el-tag size="small">{{ row.card_type.name }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('misc.createdTime')" width="200">
            <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
          </el-table-column>
          <el-table-column :label="t('common.action')" width="160">
            <template #default="{ row }">
              <el-button size="small" type="primary" plain @click="onEditCard(row.id)">{{ t('common.edit') }}</el-button>
              <el-popconfirm :title="t('misc.confirmDeleteShort')" @confirm="onDeleteCard(row.id)">
                <template #reference>
                  <el-button size="small" type="danger" plain>{{ t('common.delete') }}</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-scrollbar>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useCardStore } from '@renderer/stores/useCardStore'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'
import CardFilterBar from './CardFilterBar.vue'

const emit = defineEmits<{ (e: 'edit-card', id: number): void }>()

const cardStore = useCardStore()
const { cards, cardTypes } = storeToRefs(cardStore)
const { t } = useI18n()

const keyword = ref('')
const selectedTypes = ref<number[]>([])
const sortKey = ref<'recent'|'title'|'type'>('recent')
const density = ref<'comfortable'|'compact'>('comfortable')
const viewMode = ref<'card'|'list'>('card')

const filteredCards = computed(() => {
  let list = [...cards.value]
  if (keyword.value.trim()) {
    const keywords = keyword.value.trim().toLowerCase().split(/\s+/)
    list = list.filter(c => {
      const t = (c.title || '').toLowerCase()
      return keywords.every(k => t.includes(k))
    })
  }
  if (selectedTypes.value.length) {
    const set = new Set(selectedTypes.value)
    list = list.filter(c => set.has(c.card_type_id))
  }
  switch (sortKey.value) {
    case 'title':
      list.sort((a, b) => a.title.localeCompare(b.title)); break
    case 'type':
      list.sort((a, b) => a.card_type.name.localeCompare(b.card_type.name)); break
    default:
      list.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
  }
  return list
})

function handleFilterChange(payload: { keyword: string; types: number[]; sortKey: 'recent'|'title'|'type'; density: 'comfortable'|'compact'; view: 'card'|'list' }) {
  keyword.value = payload.keyword
  selectedTypes.value = payload.types
  sortKey.value = payload.sortKey
  density.value = payload.density
  viewMode.value = payload.view
}

function onEditCard(id: number) { emit('edit-card', id) }
async function onDeleteCard(id: number) { await cardStore.removeCard(id) }
function formatDate(dt: string) { return new Date(dt).toLocaleString() }
</script>

<style scoped>
.card-market { height: 100%; padding: 16px 20px; box-sizing: border-box; display: flex; flex-direction: column; gap: 8px; }
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.card-grid.compact { grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }
.card-item { display: flex; flex-direction: column; }
.card-header { display: flex; justify-content: space-between; align-items: center; gap: 8px; min-width: 0; }
.header-left { display: flex; align-items: center; gap: 8px; min-width: 0; flex: 1; }
.title { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.card-content { flex-grow: 1; color: var(--el-text-color-secondary); font-size: 13px; }
.meta { margin: 0; }
:deep(.header-right) { white-space: nowrap; }
:deep(.el-button) { white-space: nowrap; }
</style> 