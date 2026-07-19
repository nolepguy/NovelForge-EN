<template>
  <div class="ctx-panel">
    <div class="panel-header">
      <h3 class="panel-title">{{ t('panels.ctx.title') }}</h3>
      <el-button size="small" type="primary" :loading="assembling" @click="assemble">{{ t('panels.ctx.refreshContext') }}</el-button>
    </div>
    
    <el-form label-width="90px" class="controls">
      <el-form-item :label="t('panels.ctx.participants')">
        <el-select v-model="localParticipants" multiple filterable allow-create default-first-option :placeholder="t('panels.ctx.participantsPlaceholder')" @change="onParticipantsChange">
          <el-option-group v-for="g in participantGroups" :key="g.label" :label="groupLabel(g.label)">
            <el-option v-for="p in g.values" :key="p" :label="p" :value="p" />
          </el-option-group>
        </el-select>
      </el-form-item>
    </el-form>

    <div v-if="assembled" class="assembled">
      <div class="facts-structured" v-if="assembled.facts_structured">
        <div class="facts-title" v-if="Array.isArray((assembled.facts_structured as any)?.fact_summaries) && ((assembled.facts_structured as any)?.fact_summaries?.length > 0)">{{ t('panels.ctx.keyFacts') }}</div>
        <ul class="list" v-if="Array.isArray((assembled.facts_structured as any)?.fact_summaries) && ((assembled.facts_structured as any)?.fact_summaries?.length > 0)">
          <li v-for="(f, i0) in ((assembled.facts_structured as any)?.fact_summaries as string[] || [])" :key="i0">- {{ f }}</li>
        </ul>

        <div class="facts-title" v-if="Array.isArray((assembled.facts_structured as any)?.relation_summaries) && ((assembled.facts_structured as any)?.relation_summaries?.length > 0)">{{ t('panels.ctx.relationSummaries') }}</div>
        <ul class="list" v-if="Array.isArray((assembled.facts_structured as any)?.relation_summaries) && ((assembled.facts_structured as any)?.relation_summaries?.length > 0)">
          <li v-for="(r, idx) in ((assembled.facts_structured as any)?.relation_summaries as any[] || [])" :key="idx" class="relation-item">
            <div class="relation-head">{{ (r as any).a }} ↔ {{ (r as any).b }} ({{ (r as any).kind }})
              <el-tag v-if="(r as any).stance" size="small" style="margin-left:6px;">{{ (r as any).stance }}</el-tag>
            </div>
            <div v-if="(r as any).description" class="muted" style="margin: 2px 0;">{{ (r as any).description }}</div>
            <div v-if="(r as any).a_to_b_addressing || (r as any).b_to_a_addressing" class="muted addressing">
              <span v-if="(r as any).a_to_b_addressing">{{ t('panels.ctx.aCallsB') }}{{ (r as any).a_to_b_addressing }}</span>
              <span v-if="(r as any).b_to_a_addressing" style="margin-left:12px;">{{ t('panels.ctx.bCallsA') }}{{ (r as any).b_to_a_addressing }}</span>
            </div>
            <div v-if="Array.isArray((r as any)?.recent_dialogues) && ((r as any).recent_dialogues?.length > 0)" class="muted">
              {{ t('panels.ctx.dialogSamples') }}
              <ul class="list">
                <li v-for="(d, i3) in ((r as any).recent_dialogues as string[] || [])" :key="i3"><div class="dialog-text">{{ d }}</div></li>
              </ul>
            </div>
            <div v-if="Array.isArray((r as any)?.recent_event_summaries) && ((r as any).recent_event_summaries?.length > 0)" class="muted">
              {{ t('panels.ctx.recentEvents') }}
              <ul class="list">
                <li v-for="(ev, i4) in ((r as any).recent_event_summaries as any[] || [])" :key="i4">
                  <span>{{ (ev as any).summary }}</span>
                  <span class="badges" v-if="(ev as any).volume_number != null || (ev as any).chapter_number != null">
                    <el-tag size="small" type="info" v-if="(ev as any).volume_number != null">{{ t('panels.ctx.volumeBadge', { n: (ev as any).volume_number }) }}</el-tag>
                    <el-tag size="small" type="info" v-if="(ev as any).chapter_number != null" style="margin-left:6px;">{{ t('panels.ctx.chapterBadge', { n: (ev as any).chapter_number }) }}</el-tag>
                  </span>
                </li>
              </ul>
            </div>
          </li>
        </ul>

        <div class="facts-title" v-if="Array.isArray((assembled.facts_structured as any)?.item_summaries) && ((assembled.facts_structured as any)?.item_summaries?.length > 0)">{{ t('panels.ctx.itemSummaries') }}</div>
        <ul class="list" v-if="Array.isArray((assembled.facts_structured as any)?.item_summaries) && ((assembled.facts_structured as any)?.item_summaries?.length > 0)">
          <li v-for="(item, idx) in ((assembled.facts_structured as any)?.item_summaries as any[] || [])" :key="`item-${idx}`" class="relation-item">
            <div class="relation-head">
              {{ (item as any).name }}
              <el-tag v-if="(item as any).category" size="small" style="margin-left:6px;">{{ (item as any).category }}</el-tag>
            </div>
            <div v-if="(item as any).description" class="muted" style="margin: 2px 0;">{{ (item as any).description }}</div>
            <div v-if="(item as any).current_state" class="muted">{{ t('panels.ctx.currentState') }}{{ (item as any).current_state }}</div>
            <div v-if="(item as any).owner_hint" class="muted">{{ t('panels.ctx.ownerHint') }}{{ (item as any).owner_hint }}</div>
            <div v-if="(item as any).power_or_effect" class="muted">{{ t('panels.ctx.powerOrEffect') }}{{ (item as any).power_or_effect }}</div>
            <div v-if="(item as any).constraints" class="muted">{{ t('panels.ctx.constraints') }}{{ (item as any).constraints }}</div>
            <div v-if="Array.isArray((item as any)?.important_events) && ((item as any).important_events?.length > 0)" class="muted">
              {{ t('panels.ctx.importantEvents') }}
              <ul class="list">
                <li v-for="(eventText, eventIdx) in ((item as any).important_events as string[] || [])" :key="eventIdx">{{ eventText }}</li>
              </ul>
            </div>
          </li>
        </ul>

        <div class="facts-title" v-if="Array.isArray((assembled.facts_structured as any)?.concept_summaries) && ((assembled.facts_structured as any)?.concept_summaries?.length > 0)">{{ t('panels.ctx.conceptSummaries') }}</div>
        <ul class="list" v-if="Array.isArray((assembled.facts_structured as any)?.concept_summaries) && ((assembled.facts_structured as any)?.concept_summaries?.length > 0)">
          <li v-for="(concept, idx) in ((assembled.facts_structured as any)?.concept_summaries as any[] || [])" :key="`concept-${idx}`" class="relation-item">
            <div class="relation-head">
              {{ (concept as any).name }}
              <el-tag v-if="(concept as any).category" size="small" style="margin-left:6px;">{{ (concept as any).category }}</el-tag>
            </div>
            <div v-if="(concept as any).description" class="muted" style="margin: 2px 0;">{{ (concept as any).description }}</div>
            <div v-if="(concept as any).rule_definition" class="muted">{{ t('panels.ctx.ruleDefinition') }}{{ (concept as any).rule_definition }}</div>
            <div v-if="(concept as any).mastery_hint" class="muted">{{ t('panels.ctx.masteryHint') }}{{ (concept as any).mastery_hint }}</div>
            <div v-if="(concept as any).cost" class="muted">{{ t('panels.ctx.cost') }}{{ (concept as any).cost }}</div>
            <div v-if="Array.isArray((concept as any)?.known_by) && ((concept as any).known_by?.length > 0)" class="muted">{{ t('panels.ctx.knownBy') }}{{ ((concept as any).known_by as string[]).join(', ') }}</div>
            <div v-if="Array.isArray((concept as any)?.counter_relations) && ((concept as any).counter_relations?.length > 0)" class="muted">{{ t('panels.ctx.counterRelations') }}{{ ((concept as any).counter_relations as string[]).join(', ') }}</div>
          </li>
        </ul>
        
      </div>
      <pre class="pre" v-if="!assembled.facts_structured && assembled.facts_subgraph">{{ assembled.facts_subgraph }}</pre>
      <div v-if="!assembled.facts_structured && !assembled.facts_subgraph">{{ t('panels.ctx.noFactsHint') }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { assembleContext, type AssembleContextResponse } from '@renderer/api/ai'
import { ElMessage } from 'element-plus'
import { getCardsForProject, type CardRead } from '@renderer/api/cards'

const { t } = useI18n()

const props = defineProps<{ projectId?: number; participants?: string[]; volumeNumber?: number | null; stageNumber?: number | null; chapterNumber?: number | null; draftTail?: string; prefetched?: AssembleContextResponse | null }>()
const emit = defineEmits<{
  (e:'update:participants', v: string[]): void;
  (e:'update:volumeNumber', v: number | null): void;
  (e:'update:stageNumber', v: number | null): void;
  (e:'update:chapterNumber', v: number | null): void;
  (e:'context-updated', v: AssembleContextResponse): void;
}>()

const assembling = ref(false)
const assembled = ref<AssembleContextResponse | null>(null)
// Prefetch entry has been removed

type Group = { label: string; values: string[] }
const participantGroups = ref<Group[]>([])
const localParticipants = ref<string[]>(props.participants || [])
const localVolumeNumber = ref<number | null>(props.volumeNumber ?? null)
const localStageNumber = ref<number | null>(props.stageNumber ?? null)
const localChapterNumber = ref<number | null>(props.chapterNumber ?? null)

// Cache: name -> group label (matched via project cards)
const nameToGroup = ref<Record<string, string>>({})

// Internal group key -> display label mapping
const groupKeyMap: Record<string, string> = {
  'Character': 'character',
  'Scene': 'scene',
  'Organization': 'organization',
  'Item': 'item',
  'Concept': 'concept',
  'Other': 'other',
}
function groupLabel(label: string): string {
  const k = groupKeyMap[label] || 'other'
  return t(`panels.ctx.group.${k}`)
}

watch(() => props.participants, (v) => { localParticipants.value = [...(v || [])] })
watch(() => props.volumeNumber, (v) => { localVolumeNumber.value = v ?? null })
watch(() => props.stageNumber, (v) => { localStageNumber.value = v ?? null })
watch(() => props.chapterNumber, (v) => { localChapterNumber.value = v ?? null })
watch(() => props.prefetched, (v) => { if (v) assembled.value = v })
watch(() => props.projectId, async () => { await buildNameGroupCache(); await buildAllGroups() })

function emitParticipants() { emit('update:participants', [...localParticipants.value]) }
function emitVolume() { emit('update:volumeNumber', localVolumeNumber.value ?? null) }
function emitStage() { emit('update:stageNumber', localStageNumber.value ?? null) }
function emitChapter() { emit('update:chapterNumber', localChapterNumber.value ?? null) }

function detectTypeGroupByCard(c: CardRead): string {
  // 1) Prefer the entity type marker in content (added by backend)
  const et = (c.content as any)?.entity_type
  if (et === 'character') return 'Character'
  if (et === 'scene') return 'Scene'
  if (et === 'organization') return 'Organization'
  if (et === 'item') return 'Item'
  if (et === 'concept') return 'Concept'

  // 2) Categorize by card type name
  const tname = (c.card_type?.name || '').trim()
  if (tname.includes('Character')) return 'Character'
  if (tname.includes('Scene')) return 'Scene'
  if (tname.includes('Organization')) return 'Organization'
  if (tname.includes('Item')) return 'Item'
  if (tname.includes('Concept')) return 'Concept'

  // 3) Compatible with legacy model names: prefer instance/type model_name
  const m = (c as any).model_name || (c.card_type as any)?.model_name || ''
  if (m === 'CharacterCard') return 'Character'
  if (m === 'SceneCard') return 'Scene'
  if (m === 'OrganizationCard') return 'Organization'

  return 'Other'
}

async function buildNameGroupCache() {
  nameToGroup.value = {}
  if (!props.projectId) return
  try {
    const cards: CardRead[] = await getCardsForProject(props.projectId)
    for (const c of cards) {
      const nm = (c.title || '').trim()
      if (!nm) continue
      nameToGroup.value[nm] = detectTypeGroupByCard(c)
    }
  } catch {}
}

async function buildAllGroups() {
  if (!props.projectId) { participantGroups.value = []; return }
  try {
    const cards: CardRead[] = await getCardsForProject(props.projectId)
    const order = ['Character','Scene','Organization','Item','Concept','Other']
    const buckets = new Map<string, Set<string>>()
    order.forEach(t => buckets.set(t, new Set<string>()))
    for (const c of cards) {
      const t = detectTypeGroupByCard(c)
      const title = (c.title || '').trim()
      if (!title) continue
      buckets.get(t)!.add(title)
    }
    participantGroups.value = order
      .map(label => ({ label, values: Array.from(buckets.get(label) || []).sort((a,b)=>a.localeCompare(b)) }))
      .filter(g => g.values.length > 0)
  } catch {
    participantGroups.value = []
  }
}

function onParticipantsChange() {
  emitParticipants();
}

onMounted(async () => { await buildNameGroupCache(); await buildAllGroups(); if (props.prefetched) assembled.value = props.prefetched })

async function assemble() {
  try {
    assembling.value = true
    const res = await assembleContext({
      project_id: props.projectId,
      volume_number: localVolumeNumber.value ?? undefined,
      chapter_number: localChapterNumber.value ?? undefined,
      participants: localParticipants.value,
      current_draft_tail: props.draftTail || ''
    })
    assembled.value = res
    emit('context-updated', res)
    // Write latest local values back to parent to keep them in sync on save
    emitParticipants(); emitVolume(); emitStage(); emitChapter();
    ElMessage.success(t('panels.ctx.contextAssembled'))
  } catch (e:any) {
    ElMessage.error(t('panels.ctx.assembleFailed'))
  } finally {
    assembling.value = false
  }
}
</script>

<style scoped>
.ctx-panel { display: flex; flex-direction: column; gap: 0; height: 100%; }
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 2px solid var(--el-border-color-light);
  background: var(--el-fill-color-lighter);
}
.panel-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  white-space: nowrap;
}
.panel-header :deep(.el-button) { white-space: nowrap; }
.controls { padding: 12px 16px; border-bottom: 1px solid var(--el-border-color-light); }
.controls :deep(.el-form-item__label) { white-space: nowrap; }
.actions { display: flex; gap: 8px; }
.assembled { padding: 16px; overflow: auto; color: var(--el-text-color-primary); font-size: 14px; line-height: 1.8; }
.pre { white-space: pre-wrap; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; font-size: 13px; color: var(--el-text-color-primary); }
.facts-structured { margin-bottom: 8px; }
.facts-title { font-weight: 600; margin: 6px 0; color: var(--el-text-color-primary); white-space: nowrap; }
.list { margin: 0; padding-left: 16px; }
.list li { margin: 4px 0; }
.muted { color: var(--el-text-color-regular); }
.relation-item { margin-bottom: 10px; }
.relation-head { font-weight: 600; margin: 2px 0; color: var(--el-text-color-primary); }
.addressing span { display: inline-block; }
.dialog-text { white-space: pre-wrap; line-height: 1.8; font-size: 13.5px; color: var(--el-text-color-primary); }
.badges { margin-left: 8px; }
.raw-toggle { margin: 6px 0; }
</style>