<template>
  <div class="outline-panel">
    <div class="panel-pad">
      <template v-if="hasAny">
        <!-- Chapter outline -->
        <template v-if="chapterOutline">
          <h4 class="title">{{ t('panels.outline.chapterOutline') }}</h4>
          <div class="section">
            <div class="stage-head">
              <span class="name">{{ t('panels.outline.chapterFormat', { n: chapterOutline.chapter_number || '-', title: chapterOutline.title || t('common.unknown') }) }}</span>
              <span class="badge">{{ t('panels.outline.volumeBadge', { n: volumeNumber ?? '-' }) }}</span>
            </div>
            <p class="text">{{ chapterOutline.overview || t('panels.outline.noOverview') }}</p>
          </div>
        </template>

        <!-- Current stage (derived or passed in externally) -->
        <template v-if="stageNow">
          <h4 class="title">{{ t('panels.outline.currentStage') }}</h4>
          <div class="section">
            <div class="stage-head">
              <span class="name">{{ stageNow.stage_name || t('panels.outline.stageNumber', { n: stageNow.stage_number || '-' }) }}</span>
              <span v-if="Array.isArray(stageNow.reference_chapter) && stageNow.reference_chapter.length === 2" class="badge">{{ t('panels.outline.chapterRange', { a: stageNow.reference_chapter[0], b: stageNow.reference_chapter[1] }) }}</span>
            </div>
            <p class="text">{{ stageNow.overview || t('panels.outline.noOverview') }}</p>
            <p v-if="stageNow.analysis" class="analysis"><b>{{ t('panels.outline.creativeAnalysis') }}</b>{{ stageNow.analysis }}</p>
          </div>
        </template>

        <!-- Volume outline quick view (original) -->
        <template v-if="hasOutline">
          <h4 class="title">{{ t('panels.outline.volumeOutlineQuick') }}</h4>
          <div v-if="outline.thinking" class="section">
            <div class="sec-title">💭 {{ t('panels.outline.creativeThinking') }}</div>
            <p class="text">{{ outline.thinking }}</p>
          </div>
          <div v-if="outline.main_target" class="section">
            <div class="sec-title">🎯 {{ t('panels.outline.mainTarget') }}</div>
            <p class="text"><b>{{ t('panels.outline.nameLabel') }}</b>{{ outline.main_target.name || t('common.notSet') }}</p>
            <p class="text"><b>{{ t('panels.outline.overviewLabel') }}</b>{{ outline.main_target.overview || t('panels.outline.noOverview') }}</p>
          </div>
          <div v-if="Array.isArray(outline.branch_line) && outline.branch_line.length" class="section">
            <div class="sec-title">🌿 {{ t('panels.outline.branchLine') }}</div>
            <ul class="list">
              <li v-for="(b, i) in outline.branch_line" :key="i">{{ b.name || t('panels.outline.branchNumber', { n: Number(i)+1 }) }}: {{ b.overview || t('panels.outline.noOverview') }}</li>
            </ul>
          </div>
          <div v-if="Array.isArray(outline.stage_lines) && outline.stage_lines.length" class="section">
            <div class="sec-title">📖 {{ t('panels.outline.stageStoryline') }}</div>
            <div class="stage" v-for="(st, i) in outline.stage_lines" :key="i">
              <div class="stage-head">
                <span class="name">{{ st.stage_name || t('panels.outline.stageNumber', { n: Number(i)+1 }) }}</span>
                <span v-if="Array.isArray(st.reference_chapter) && st.reference_chapter.length === 2" class="badge">{{ t('panels.outline.chapterRange', { a: st.reference_chapter[0], b: st.reference_chapter[1] }) }}</span>
              </div>
              <p class="text">{{ st.overview || t('panels.outline.noOverview') }}</p>
              <p v-if="st.analysis" class="analysis"><b>{{ t('panels.outline.creativeAnalysis') }}</b>{{ st.analysis }}</p>
            </div>
          </div>
          <div v-if="Array.isArray(outline.character_snapshot) && outline.character_snapshot.length" class="section">
            <div class="sec-title">🧭 {{ t('panels.outline.volumeEndSnapshot') }}</div>
            <ul class="list">
              <li v-for="(s, i) in outline.character_snapshot" :key="i">{{ s }}</li>
            </ul>
          </div>
        </template>
      </template>
      <template v-else>
        <div class="placeholder">{{ t('panels.outline.noOutlineAvailable') }}</div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, watch, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCardStore } from '@renderer/stores/useCardStore'
import { storeToRefs } from 'pinia'
import type { CardRead } from '@renderer/api/cards'

const { t } = useI18n()

const props = defineProps<{ 
  outline?: any | null
  currentStage?: any | null
  volumeNumber?: number | null
  chapterNumber?: number | null
  activeCard?: CardRead | null
}>()

const { cards } = storeToRefs(useCardStore())

// Internal state: when activeCard exists and outline is not provided, look it up automatically
const internalOutline = ref<any | null>(null)
const internalCurrentStage = ref<any | null>(null)

// Look up the volume outline
function findVolumeOutline(card: CardRead | null): void {
  internalOutline.value = null
  internalCurrentStage.value = null
  
  if (!card || !card.parent_id) return
  
  const parent = cards.value?.find(c => c.id === card.parent_id)
  if (!parent) return
  
  if (parent.card_type?.name === 'Volume Outline') {
    internalOutline.value = parent.content
    
    // Match the current stage by chapter number
    try {
      const stageLines: any[] = Array.isArray((parent.content as any)?.stage_lines) 
        ? (parent.content as any).stage_lines 
        : []
      const chNo = props.chapterNumber
      
      if (typeof chNo === 'number') {
        internalCurrentStage.value = stageLines.find(st => 
          Array.isArray(st.reference_chapter) && 
          st.reference_chapter.length === 2 && 
          chNo >= st.reference_chapter[0] && 
          chNo <= st.reference_chapter[1]
        ) || null
      }
    } catch (e) {
      console.error('Failed to find stage line:', e)
    }
  } else {
    // Recursively look up the parent
    findVolumeOutline(parent as any)
  }
}

// When activeCard or the card store content changes, look up the outline automatically
watch(
  [() => props.activeCard, cards],
  ([card]) => {
    if (card && !props.outline) {
      findVolumeOutline(card as CardRead)
    } else if (!card) {
      internalOutline.value = null
      internalCurrentStage.value = null
    }
  },
  { immediate: true }
)

const hasOutline = computed(() => {
  const o = props.outline || internalOutline.value
  return !!o && typeof o === 'object'
})

const outline = computed(() => props.outline || internalOutline.value || {})

// If currentStage is not provided, derive it from the volume outline by chapter number
const stageNow = computed(() => {
  if (props.currentStage) return props.currentStage
  if (internalCurrentStage.value) return internalCurrentStage.value
  try {
    // 1) Prefer deriving from the volume outline's stage_lines
    const sl = (outline.value?.stage_lines || []) as any[]
    const ch = Number(props.chapterNumber)
    if (Array.isArray(sl) && sl.length && Number.isFinite(ch)) {
      const hit = sl.find(st => Array.isArray(st.reference_chapter) && st.reference_chapter.length === 2 && ch >= Number(st.reference_chapter[0]) && ch <= Number(st.reference_chapter[1]))
      if (hit) return hit
    }
    // 2) Fallback: look up a "Stage Outline" card in the card store
    const vol = Number(props.volumeNumber)
    if (!Number.isFinite(vol)) return null
    const all = (cards.value || [])
    if (!all.length) return null
    // Build an id->card map for tracing ancestors upward
    const idMap = new Map<number, any>(all.map(c => [c.id, c]))
    // Locate the volume outline card for the current volume
    const volumeCard = all.find(c => c?.card_type?.name === 'Volume Outline' && Number(((c.content as any)?.volume_outline?.volume_number)) === vol)
    // Candidate stage cards: card_type named "Stage Outline" and belonging to the same volume (ancestors include volumeCard, or content.volume_number==vol)
    const stageCards = all.filter(c => {
      if (c?.card_type?.name !== 'Stage Outline') return false
      const contentVol = Number(((c.content as any)?.volume_number))
      if (Number.isFinite(contentVol) && contentVol === vol) return true
      if (volumeCard && c.parent_id) {
        let p = c as any
        for (let i=0; i<6 && p?.parent_id; i++) {
          p = idMap.get(p.parent_id)
          if (p?.id === volumeCard.id) return true
        }
      }
      return false
    })
    if (!stageCards.length) return null
    // Prefer matching reference_chapter by chapter number
    if (Number.isFinite(ch)) {
      const byRange = stageCards.find(c => Array.isArray((c.content as any)?.reference_chapter) && ch >= Number((c.content as any).reference_chapter[0]) && ch <= Number((c.content as any).reference_chapter[1]))
      if (byRange) return (byRange.content as any)
    }
    // Secondary: if a card's content.stage_number happens to match props.currentStage?.stage_number (if provided externally)
    const sn = Number((props.currentStage as any)?.stage_number)
    if (Number.isFinite(sn)) {
      const byIndex = stageCards.find(c => Number((c.content as any)?.stage_number) === sn)
      if (byIndex) return (byIndex.content as any)
    }
    // Final fallback: take the first stage card
    const first = stageCards[0]
    return first ? (first.content as any) : null
  } catch { return null }
})

// Chapter outline: scan all cards, matching the current volume/chapter
const chapterOutline = computed(() => {
  try {
    const vol = Number(props.volumeNumber)
    const ch = Number(props.chapterNumber)
    if (!Number.isFinite(vol) || !Number.isFinite(ch)) return null
    const list = (cards.value || []).filter(c => c?.card_type?.name === 'Chapter Outline')
    for (const c of list) {
      const co = (c.content as any)?.chapter_outline || (c.content as any)
      const v = Number(co?.volume_number)
      const n = Number(co?.chapter_number)
      if (Number.isFinite(v) && Number.isFinite(n) && v === vol && n === ch) {
        return {
          title: co?.title || c.title,
          overview: co?.overview || '',
          volume_number: v,
          chapter_number: n,
        }
      }
    }
  } catch {}
  return null
})

const hasAny = computed(() => !!chapterOutline.value || !!stageNow.value || !!hasOutline.value)
</script>

<style scoped>
.outline-panel { height: 100%; overflow: auto; }
.panel-pad { padding: 10px; color: var(--el-text-color-regular); }
.title { margin: 0 0 8px 0; font-size: 16px; font-weight: 600; color: var(--el-text-color-primary); white-space: nowrap; }
.section { margin: 10px 0; padding: 12px; background: var(--el-fill-color-lighter); border-radius: 6px; }
.sec-title { font-weight: 600; margin-bottom: 6px; font-size: 14px; color: var(--el-text-color-primary); white-space: nowrap; }
.text { margin: 4px 0; white-space: pre-wrap; font-size: 14px; line-height: 1.8; letter-spacing: 0.2px; color: var(--el-text-color-primary); }
.list { margin: 0; padding-left: 16px; font-size: 14px; line-height: 1.8; color: var(--el-text-color-primary); }
.stage { margin: 8px 0; padding: 8px; background: var(--el-bg-color); border-radius: 6px; border-left: 3px solid var(--el-color-primary); }
.stage-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; gap: 8px; }
.name { font-weight: 600; font-size: 14px; color: var(--el-text-color-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.placeholder { color: var(--el-text-color-secondary); }
.badge { font-size: 12px; color: var(--el-color-warning); border: 1px solid var(--el-color-warning); border-radius: 3px; padding: 0 6px; white-space: nowrap; flex-shrink: 0; }
/* High-contrast debug styles */
.debug-box { background: #1e1e1e; border-radius: 6px; padding: 8px; max-height: 260px; overflow: auto; }
.debug-pre { color: #e6e6e6; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; font-size: 12px; line-height: 1.6; margin: 0; white-space: pre; }
</style>