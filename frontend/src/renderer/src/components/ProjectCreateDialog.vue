<template>
  <el-dialog v-model="visible" :title="dialogTitle" width="520" >
    <el-form :model="form" ref="formRef" :rules="rules" label-width="130px" @submit.prevent="handleConfirm">
      <el-form-item :label="t('dashboard.projectName')" prop="name">
        <el-input v-model="form.name" />
      </el-form-item>
      <el-form-item :label="t('dashboard.projectDescription')" prop="description">
        <el-input v-model="form.description" type="textarea" />
      </el-form-item>
      <el-form-item v-if="!isEditMode" :label="t('dashboard.projectTemplate')">
        <el-select v-model="selectedTemplate" :placeholder="t('dashboard.selectTemplatePlaceholder')" filterable clearable :loading="loadingTemplates" style="width:100%">
          <el-option :label="t('dashboard.blankProject')" :value="null" />
          <el-option v-for="tpl in projectTemplates" :key="tpl.template" :label="tpl.workflow_name" :value="tpl.template" />
        </el-select>
      </el-form-item>
      <!-- Hidden submit button to ensure pressing Enter in inputs submits the form -->
      <button type="submit" style="display:none"></button>
    </el-form>
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="visible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="handleConfirm">{{ t('common.confirm') }}</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import type { FormInstance, FormRules } from 'element-plus'
import type { components } from '@renderer/types/generated'
import { getProjectTemplates } from '@renderer/api/workflows'

const { t } = useI18n()

type Project = components['schemas']['ProjectRead']
type ProjectCreate = components['schemas']['ProjectCreate']
type ProjectUpdate = components['schemas']['ProjectUpdate']

interface ProjectTemplate {
  workflow_id: number
  workflow_name: string
  template: string | null
  description?: string
}

const visible = ref(false)
const formRef = ref<FormInstance>()
const form = reactive<ProjectCreate | ProjectUpdate>({
  name: '',
  description: ''
})
const editingProject = ref<Project | null>(null)

// Project templates
const selectedTemplate = ref<string | null>(null)
const projectTemplates = ref<ProjectTemplate[]>([])
const loadingTemplates = ref(false)

const isEditMode = computed(() => !!editingProject.value)
const dialogTitle = computed(() => isEditMode.value ? t('dashboard.editProject') : t('dashboard.newProject'))

const rules = computed<FormRules>(() => ({
  name: [{ required: true, message: t('dashboard.nameRequired'), trigger: 'blur' }]
}))

const emit = defineEmits(['create', 'update'])

async function loadProjectTemplates() {
  try {
    loadingTemplates.value = true
    const response = await getProjectTemplates()
    projectTemplates.value = response.templates || []
    
    // Default-select the first template (if any)
    if (projectTemplates.value.length > 0) {
      selectedTemplate.value = projectTemplates.value[0].template
    }
  } catch (error) {
    console.error('Failed to load project templates:', error)
    ElMessage.error(t('dashboard.loadTemplatesFailed'))
  } finally {
    loadingTemplates.value = false
  }
}

function open(project: Project | null = null) {
  visible.value = true
  editingProject.value = project
  
  nextTick(() => {
    formRef.value?.resetFields()
    if (project) {
      form.name = project.name
      form.description = project.description || ''
    } else {
      form.name = ''
      form.description = ''
      selectedTemplate.value = null
      // Load project templates
      loadProjectTemplates()
    }
  })
}

function handleConfirm() {
  formRef.value?.validate((valid) => {
    if (valid) {
      if (isEditMode.value && editingProject.value) {
        emit('update', editingProject.value.id, { ...form })
      } else {
        const payload: any = { ...form }
        // Explicitly pass the template parameter (null means a blank project)
        payload.template = selectedTemplate.value
        emit('create', payload)
      }
      visible.value = false
    } else {
      ElMessage.error(t('dashboard.fillRequiredFields'))
    }
  })
}

// Expose the open method to the parent component
defineExpose({
  open
})
</script>

<style scoped>
.dialog-footer { display: flex; justify-content: flex-end; gap: 8px; }
.dialog-footer :deep(.el-button) { white-space: nowrap; }
.mode-switch { margin-bottom: 8px; }
.selector-block { width: 100%; }
:deep(.el-form-item__label) { white-space: nowrap; }
</style>