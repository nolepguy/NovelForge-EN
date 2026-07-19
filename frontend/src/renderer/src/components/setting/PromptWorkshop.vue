<template>
  <div class="prompt-workshop">
    <div class="toolbar">
      <h2>{{ t('settings.promptWorkshop') }}</h2>
      <el-button type="primary" @click="handleCreate">{{ t('settings.newPrompt') }}</el-button>
    </div>
    <el-table v-loading="loading" :data="prompts" style="width: 100%">
      <el-table-column prop="name" :label="t('common.name')" width="180" />
      <el-table-column prop="description" :label="t('common.description')" />
      <el-table-column :label="t('common.action')" width="240">
        <template #default="{ row }">
          <el-button size="small" @click="handleEdit(row)">{{ t('common.edit') }}</el-button>
          <el-popconfirm
            v-if="!isBuiltInPrompt(row)"
            :title="t('settings.confirmDeletePrompt')"
            @confirm="handleDelete(row.id)"
          >
            <template #reference>
              <el-button size="small" type="danger" :disabled="isBuiltInPrompt(row)">{{
                t('common.delete')
              }}</el-button>
            </template>
          </el-popconfirm>
          <el-button v-else size="small" type="danger" plain disabled>{{
            t('common.delete')
          }}</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Drawer editor -->
    <el-drawer v-model="drawerVisible" :title="dialogTitle" size="60%" append-to-body>
      <el-form ref="promptForm" :model="currentPrompt" label-width="120px" class="form-grid">
        <el-form-item
          :label="t('common.name')"
          prop="name"
          :rules="{ required: true, message: t('settings.ruleEnterName'), trigger: 'blur' }"
        >
          <el-input v-model="currentPrompt.name" />
        </el-form-item>
        <el-form-item :label="t('common.description')" prop="description">
          <el-input v-model="currentPrompt.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item :label="t('settings.structuredEdit')">
          <el-switch v-model="useStructured" />
          <span class="hint">{{ t('settings.structuredEditHint') }}</span>
        </el-form-item>

        <!-- Structured edit mode -->
        <template v-if="useStructured">
          <el-divider content-position="left">Role</el-divider>
          <el-input v-model="structured.role" :placeholder="t('settings.rolePlaceholder')" />

          <el-divider content-position="left">Skills</el-divider>
          <el-input
            v-model="structured.skills"
            type="textarea"
            :rows="2"
            :placeholder="t('settings.skillsPlaceholder')"
          />

          <el-divider content-position="left">Goals</el-divider>
          <el-input
            v-model="structured.goals"
            type="textarea"
            :rows="4"
            :placeholder="t('settings.goalsPlaceholder')"
          />

          <el-divider content-position="left">{{ t('settings.knowledgeOptional') }}</el-divider>
          <div class="knowledge-grid">
            <div class="row">
              <span class="label">{{ t('settings.referenceMode') }}</span>
              <el-radio-group v-model="knowledgeMode" size="small">
                <el-radio-button label="id">{{ t('settings.byId') }}</el-radio-button>
                <el-radio-button label="name">{{ t('settings.byName') }}</el-radio-button>
              </el-radio-group>
              <span class="hint" style="margin-left: 8px">{{
                t('settings.knowledgeRefHint')
              }}</span>
            </div>
            <el-select
              v-model="selectedKnowledgeIds"
              multiple
              filterable
              :placeholder="t('settings.selectKnowledgePlaceholder')"
              style="width: 100%"
            >
              <el-option
                v-for="kb in knowledgeItems"
                :key="kb.id"
                :label="kb.name"
                :value="kb.id"
              />
            </el-select>
          </div>

          <el-divider content-position="left">{{ t('settings.outputFormatOptional') }}</el-divider>
          <el-input
            v-model="structured.outputFormat"
            type="textarea"
            :rows="2"
            :placeholder="t('settings.outputFormatPlaceholder')"
          />

          <el-divider content-position="left">{{ t('settings.preview') }}</el-divider>
          <el-input :model-value="composedTemplate" type="textarea" :rows="10" readonly />
        </template>

        <!-- Raw template mode -->
        <template v-else>
          <el-form-item
            :label="t('settings.template')"
            prop="template"
            :rules="{ required: true, message: t('settings.ruleEnterTemplate'), trigger: 'blur' }"
          >
            <el-input v-model="currentPrompt.template" type="textarea" :rows="14" />
            <div class="template-hint">
              {{ t('settings.templateHintPrefix') }}<code>${variable}</code
              >{{ t('settings.templateHintMiddle') }}<code>${text_content}</code
              >{{ t('settings.templateHintSuffix') }}
            </div>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <div class="drawer-footer">
          <el-button @click="drawerVisible = false">{{ t('common.cancel') }}</el-button>
          <el-button type="primary" :loading="saving" @click="handleSave">{{
            t('common.save')
          }}</el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance } from 'element-plus'
import {
  listKnowledge,
  type Knowledge,
  listPrompts,
  createPrompt,
  updatePrompt,
  deletePrompt
} from '@renderer/api/setting'

const { t } = useI18n()

interface Prompt {
  id: number
  name: string
  description: string
  template: string
  built_in?: boolean
}

const defaultOutputFormat = computed(() => t('settings.defaultOutputFormat'))

const prompts = ref<Prompt[]>([])
const loading = ref(false)
const drawerVisible = ref(false)
const saving = ref(false)
const currentPrompt = ref<Partial<Prompt>>({})
const promptForm = ref<FormInstance>()

const dialogTitle = computed(() =>
  currentPrompt.value.id ? t('settings.editPrompt') : t('settings.newPrompt')
)

const isBuiltInPrompt = (row: Prompt) => !!row.built_in

// Structured edit related
const useStructured = ref(false)
const structured = ref({ role: '', skills: '', goals: '', knowledge: '', outputFormat: '' })

// Knowledge base selection and mode
const knowledgeItems = ref<Knowledge[]>([])
const selectedKnowledgeIds = ref<number[]>([])
const knowledgeMode = ref<'id' | 'name'>('name')

// Compose preview
const composedTemplate = computed(() => composeTemplate(structured.value))

function composeTemplate(s: {
  role: string
  skills: string
  goals: string
  knowledge?: string
  outputFormat?: string
}) {
  const lines: string[] = []
  if (s.role?.trim()) lines.push(`- Role: ${s.role.trim()}`)
  if (s.skills?.trim()) lines.push(`- Skills: ${s.skills.trim()}`)
  if (s.goals?.trim()) {
    lines.push('- Goals:')
    // Indent multi-line goals
    const gl = s.goals
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter(Boolean)
    for (const g of gl) lines.push(`    - ${g}`)
  }
  // Knowledge base placeholder reference
  if (selectedKnowledgeIds.value.length) {
    lines.push('\n- knowledge:')
    for (const kid of selectedKnowledgeIds.value) {
      const item = knowledgeItems.value.find((k) => k.id === kid)
      if (!item) continue
      if (knowledgeMode.value === 'id') {
        lines.push(`    - @KB{ id=${kid} }  # ${item.name}`)
      } else {
        lines.push(`    - @KB{ name=${item.name} }`)
      }
    }
  }
  if (s.outputFormat?.trim()) lines.push(`\n- OutputFormat: ${s.outputFormat.trim()}`)
  return lines.join('\n')
}

async function fetchPrompts() {
  loading.value = true
  try {
    prompts.value = await listPrompts()
  } catch (error) {
    ElMessage.error(t('settings.loadPromptsFailed'))
  } finally {
    loading.value = false
  }
}

async function fetchKnowledgeList() {
  try {
    knowledgeItems.value = await listKnowledge()
  } catch {
    knowledgeItems.value = []
  }
}

function resetStructuredDefaults() {
  structured.value = {
    role: '',
    skills: '',
    goals: '',
    knowledge: '',
    outputFormat: defaultOutputFormat.value
  }
  selectedKnowledgeIds.value = []
  knowledgeMode.value = 'name'
}

function handleCreate() {
  currentPrompt.value = { name: '', description: '', template: '' }
  resetStructuredDefaults()
  useStructured.value = false
  drawerVisible.value = true
}

function parseKnowledgeBlock(tpl: string) {
  // Extract the knowledge block
  const k = /-\s*knowledge:\s*([\s\S]*?)(?:\n-\s*OutputFormat\s*[:：]|$)/i.exec(tpl)
  const ids: number[] = []
  let mode: 'id' | 'name' = 'name'
  if (k && k[1]) {
    const block = k[1]
    const idReg = /@KB\{\s*id\s*=\s*(\d+)\s*\}/gi
    const nameReg = /@KB\{\s*name\s*=\s*([^}]+)\}/gi
    let m: RegExpExecArray | null
    while ((m = idReg.exec(block))) {
      const id = Number(m[1])
      if (!Number.isNaN(id)) ids.push(id)
    }
    if (!ids.length) {
      const names: string[] = []
      while ((m = nameReg.exec(block))) {
        const n = (m[1] || '').trim().replace(/^['"]|['"]$/g, '')
        if (n) names.push(n)
      }
      if (names.length) {
        mode = 'name'
        for (const n of names) {
          const found = knowledgeItems.value.find((kb) => kb.name === n)
          if (found) ids.push(found.id)
        }
      }
    } else {
      mode = 'id'
    }
  }
  selectedKnowledgeIds.value = Array.from(new Set(ids))
  knowledgeMode.value = mode
}

async function tryParseStructured(tpl?: string) {
  if (!tpl) return resetStructuredDefaults()
  // Rough parsing: only fill fields for common formats; on failure keep defaults
  try {
    const r = /-\s*Role:\s*(.*)/i.exec(tpl)
    const s =
      /-\s*Skills?:\s*([\s\S]*?)(?:\n-\s*Goals?:|\n-\s*knowledge:|\n-\s*OutputFormat\s*[:：]|$)/i.exec(
        tpl
      )
    const g = /-\s*Goals?:\s*([\s\S]*?)(?:\n-\s*knowledge:|\n-\s*OutputFormat\s*[:：]|$)/i.exec(tpl)
    const o = /-\s*OutputFormat\s*[:：]\s*([\s\S]*)/i.exec(tpl)
    structured.value.role = r?.[1]?.trim() || ''
    structured.value.skills = (s?.[1] || '').trim()
    structured.value.goals = (g?.[1] || '').replace(/^\s*-\s*/gm, '').trim()
    structured.value.outputFormat = (o?.[1] || defaultOutputFormat.value).trim()
    // Parse knowledge base references
    parseKnowledgeBlock(tpl)
  } catch {
    resetStructuredDefaults()
  }
}

async function handleEdit(prompt: any) {
  currentPrompt.value = { ...prompt }
  await fetchKnowledgeList()
  // Try parsing as a structured form; on failure fall back to raw template mode
  await tryParseStructured(prompt.template)
  useStructured.value = false
  drawerVisible.value = true
}

async function handleSave() {
  if (!promptForm.value) return
  await promptForm.value.validate(async (valid) => {
    if (valid) {
      saving.value = true
      try {
        const payload: any = { ...currentPrompt.value }
        // If structured editing, compose the template and write it back
        if (useStructured.value) {
          payload.template = composeTemplate(structured.value)
        }
        if (payload.id) {
          await updatePrompt(payload.id, payload)
        } else {
          await createPrompt(payload)
        }
        ElMessage.success(t('common.saveSuccess'))
        drawerVisible.value = false
        fetchPrompts()
      } catch (error) {
        ElMessage.error(t('common.operationFailed'))
      } finally {
        saving.value = false
      }
    }
  })
}

async function handleDelete(id: number) {
  try {
    await ElMessageBox.confirm(t('settings.confirmDeletePromptMsg'), t('common.warning'), {
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
      type: 'warning'
    })
    await deletePrompt(id)
    ElMessage.success(t('common.deleteSuccess'))
    fetchPrompts()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(t('common.operationFailed'))
    }
  }
}

onMounted(async () => {
  await fetchKnowledgeList()
  await fetchPrompts()
})
</script>

<style scoped>
:deep(.el-button) {
  white-space: nowrap;
}

.prompt-workshop {
  padding: 20px;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.toolbar :deep(.el-button) {
  white-space: nowrap;
}
.form-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.hint {
  color: var(--el-text-color-secondary);
  margin-left: 8px;
  font-size: 12px;
}
.template-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}
.template-hint :deep(code) {
  padding: 0 2px;
}
.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.knowledge-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.label {
  color: var(--el-text-color-regular);
}
:deep(.el-table .el-button) {
  white-space: nowrap;
}
</style>
