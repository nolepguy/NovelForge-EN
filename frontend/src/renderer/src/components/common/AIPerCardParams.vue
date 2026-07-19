<template>
	<div class="ai-param-inline">
		<el-popover placement="bottom" trigger="manual" v-model:visible="visible" width="360">
			<template #reference>
				<el-button type="primary" size="small" class="model-trigger" @click="visible = !visible">
					<template #icon>
						<el-icon><Setting /></el-icon>
					</template>
					<span class="model-label">{{ t('misc.modelLabel') }}</span>
					<span class="model-name">{{ selectedModelName || t('common.notSet') }}</span>
				</el-button>
			</template>
			<div class="ai-config-form">
				<el-form label-width="110px" size="small">
					<el-form-item :label="t('misc.modelId')">
						<el-select v-model="editing.llm_config_id" :placeholder="t('misc.selectModel')" style="width: 240px;" :teleported="false">
							<el-option v-for="m in (aiOptions?.llm_configs || [])" :key="m.id" :label="m.display_name || String(m.id)" :value="Number(m.id)" />
						</el-select>
					</el-form-item>
					<el-form-item :label="t('misc.prompt')">
						<el-select v-model="editing.prompt_name" :placeholder="t('misc.selectPrompt')" filterable style="width: 240px;" :teleported="false">
							<el-option v-for="p in (aiOptions?.prompts || [])" :key="p.id" :label="p.name" :value="p.name" />
						</el-select>
					</el-form-item>
					<el-form-item :label="t('misc.temperature')">
						<el-input-number v-model="editing.temperature" :min="0" :max="2" :step="0.1" />
					</el-form-item>
					<el-form-item :label="t('misc.maxTokens')">
						<el-input-number v-model="editing.max_tokens" :min="1" :step="256" />
					</el-form-item>
					<el-form-item :label="t('misc.timeoutSeconds')">
						<el-input-number v-model="editing.timeout" :min="1" :step="5" />
					</el-form-item>
					<el-form-item>
						<div class="ai-actions">
							<div class="left">
								<el-button type="primary" size="small" @click="saveLocal">{{ t('common.save') }}</el-button>
								<el-button size="small" @click="resetToPreset">{{ t('misc.resetToPreset') }}</el-button>
							</div>
							<div class="right">
								<el-button size="small" type="warning" plain @click="restoreFollowType">{{ t('misc.restoreFollowType') }}</el-button>
								<el-button size="small" type="primary" plain @click="applyToType">{{ t('misc.applyToType') }}</el-button>
							</div>
						</div>
					</el-form-item>
				</el-form>
			</div>
		</el-popover>
	</div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Setting } from '@element-plus/icons-vue'
import { usePerCardAISettingsStore, type PerCardAIParams } from '@renderer/stores/usePerCardAISettingsStore'
import { getAIConfigOptions, type AIConfigOptions } from '@renderer/api/ai'
import { getCardAIParams, updateCardAIParams, applyCardAIParamsToType } from '@renderer/api/setting'
import { ElMessage } from 'element-plus'

const props = defineProps<{ cardId: number; cardTypeName?: string }>()
const { t } = useI18n()

const store = usePerCardAISettingsStore()
const visible = ref(false)
const aiOptions = ref<AIConfigOptions | null>(null)
const editing = ref<PerCardAIParams>({})

async function loadOptions() { try { aiOptions.value = await getAIConfigOptions() } catch {} }

const saved = computed(() => store.getByCardId(props.cardId))
const selectedModelName = computed(() => {
	try {
		const raw = (saved.value || editing.value)?.llm_config_id as any
		const id = raw == null ? undefined : Number(raw)
		const list = aiOptions.value?.llm_configs || []
		const found = list.find(m => Number(m.id) === id)
		return found?.display_name || (id != null ? String(id) : '')
	} catch { return '' }
})

watch(() => props.cardId, async (id) => {
	if (!id) return
	await loadOptions()
	try {
		const resp = await getCardAIParams(id)
		const eff = (resp as any)?.effective_params
		if (eff && Object.keys(eff).length) {
			const fixed = { ...eff, llm_config_id: eff.llm_config_id == null ? eff.llm_config_id : Number(eff.llm_config_id) }
			editing.value = fixed
			store.setForCard(id, { ...fixed })
			return
		}
	} catch {}
	// fallback to saved or preset
	if (saved.value) {
		const sv = saved.value as any
		editing.value = { ...sv, llm_config_id: sv?.llm_config_id == null ? sv?.llm_config_id : Number(sv.llm_config_id) }
	} else {
		const preset = getPresetForType(props.cardTypeName)
		if (!preset.llm_config_id) {
			const first = aiOptions.value?.llm_configs?.[0]; if (first) preset.llm_config_id = Number(first.id)
		}
		editing.value = { ...preset, llm_config_id: preset.llm_config_id == null ? preset.llm_config_id : Number(preset.llm_config_id) }
		store.setForCard(id, editing.value)
	}
}, { immediate: true })

function getPresetForType(typeName?: string): PerCardAIParams {
	const map: Record<string, PerCardAIParams> = {
		'Special Ability': { prompt_name: 'Special Ability Generation', temperature: 0.6, max_tokens: 1024, timeout: 60 },
		'One Sentence Summary': { prompt_name: 'One Sentence Summary', temperature: 0.6, max_tokens: 1024, timeout: 60 },
		'Worldview Setting': { prompt_name: 'Worldview Setting', temperature: 0.6, max_tokens: 8192, timeout: 120 },
		'Core Blueprint': { prompt_name: 'Core Blueprint', temperature: 0.6, max_tokens: 8192, timeout: 120 },
		'Volume Outline': { prompt_name: 'Volume Outline', temperature: 0.6, max_tokens: 8192, timeout: 120 },
		'Stage Outline': { prompt_name: 'Stage Outline', temperature: 0.6, max_tokens: 8192, timeout: 120 },
		'Chapter Outline': { prompt_name: 'Chapter Outline', temperature: 0.6, max_tokens: 4096, timeout: 60 },
		'Writing Guide': { prompt_name: 'Writing Guide', temperature: 0.7, max_tokens: 8192, timeout: 60 },
		'Chapter Text': { prompt_name: 'Content Generation', temperature: 0.7, max_tokens: 8192, timeout: 60 },
	}
	return map[typeName || ''] || {}
}

function saveLocal() {
	try {
		const payload = { ...editing.value, llm_config_id: editing.value.llm_config_id == null ? editing.value.llm_config_id : Number(editing.value.llm_config_id) }
		// Write to backend database first
		updateCardAIParams(props.cardId, payload)
			.then(() => {
				store.setForCard(props.cardId, { ...payload })
				ElMessage.success(t('misc.saved'))
				visible.value = false
			})
			.catch(() => { ElMessage.error(t('misc.saveToBackendFailed')) })
	} catch { ElMessage.error(t('common.operationFailed')) }
}
function resetToPreset() {
	const preset = getPresetForType(props.cardTypeName)
	editing.value = { ...preset, llm_config_id: preset.llm_config_id == null ? preset.llm_config_id : Number(preset.llm_config_id) }
	store.setForCard(props.cardId, editing.value)
}
async function restoreFollowType() {
	try { await updateCardAIParams(props.cardId, null); ElMessage.success(t('misc.restoredFollowType')); const resp = await getCardAIParams(props.cardId); const eff = (resp as any)?.effective_params; if (eff) { editing.value = { ...eff }; store.setForCard(props.cardId, { ...eff }) } } catch { ElMessage.error(t('common.operationFailed')) }
}
async function applyToType() {
	try {
		await updateCardAIParams(props.cardId, { ...editing.value })
		await applyCardAIParamsToType(props.cardId)
		window.dispatchEvent(new Event('card-types-updated'))
		await updateCardAIParams(props.cardId, null)
		const resp = await getCardAIParams(props.cardId)
		const eff = (resp as any)?.effective_params
		if (eff) { editing.value = { ...eff }; store.setForCard(props.cardId, { ...eff }) }
		ElMessage.success(t('misc.appliedToTypeAndRestored'))
	} catch { ElMessage.error(t('misc.applyFailed')) }
}

</script>

<style scoped>
.ai-param-inline { 
  display: inline-flex; 
  align-items: center; 
}

.model-trigger { 
  min-width: 200px;
  max-width: 320px;
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  overflow: hidden; /* ensure the button itself doesn't overflow */
}

.model-trigger :deep(.el-button__content) {
  display: flex;
  align-items: center;
  width: 100%;
  max-width: 100%;
  overflow: hidden;
  flex: 1;
  min-width: 0;
}

.model-label { 
  flex-shrink: 0;
  margin-right: 4px;
  font-weight: 500;
}

.model-name { 
  flex: 1; 
  min-width: 0; 
  overflow: hidden; 
  text-overflow: ellipsis; 
  white-space: nowrap;
  text-align: left;
}
.ai-config-form :deep(.el-button) { white-space: nowrap; }
</style> 