import { defineStore } from 'pinia'
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { components } from '@renderer/types/generated'
import { getProjects, createProject as apiCreateProject, updateProject as apiUpdateProject, deleteProject as apiDeleteProject } from '@renderer/api/projects'
import i18n from '@renderer/i18n'

type Project = components['schemas']['ProjectRead']
type ProjectCreate = components['schemas']['ProjectCreate']
type ProjectUpdate = components['schemas']['ProjectUpdate']

export const useProjectListStore = defineStore('projectList', () => {
  // Project list
  const projects = ref<Project[]>([])
  const isLoading = ref(false)

  // Actions
  async function fetchProjects() {
    isLoading.value = true
    try {
      const list = await getProjects()
      projects.value = (list || []).filter(p => (p.name || '') !== '__free__')
    } catch (error) {
      console.error('Failed to fetch project list:', error)
      ElMessage.error(i18n.global.t('app.project.fetchListFailed'))
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function createProject(projectData: ProjectCreate) {
    try {
      const newProject = await apiCreateProject(projectData)
      await fetchProjects()
      ElMessage.success(i18n.global.t('app.project.createSuccess'))
      return newProject
    } catch (error) {
      ElMessage.error(i18n.global.t('app.project.createFailed', { error: String(error) }))
      throw error
    }
  }

  async function updateProject(projectId: number, projectData: ProjectUpdate) {
    try {
      await apiUpdateProject(projectId, projectData)
      ElMessage.success(i18n.global.t('app.project.updateSuccess'))
      await fetchProjects()
    } catch (error) {
      ElMessage.error(i18n.global.t('app.project.updateFailed', { error: String(error) }))
      throw error
    }
  }

  async function deleteProject(projectId: number) {
    try {
      // Extra frontend protection: prevent deleting the reserved project
      const proj = projects.value.find(p => p.id === projectId)
      if (proj && (proj.name || '') === '__free__') {
      ElMessage.warning(i18n.global.t('app.project.deleteReservedWarning'))
        return
      }
      await apiDeleteProject(projectId)
      ElMessage.success(i18n.global.t('app.project.deleteSuccess'))
      await fetchProjects()
    } catch (error) {
      ElMessage.error(i18n.global.t('app.project.deleteFailed', { error: String(error) }))
      throw error
    }
  }

  function reset() {
    projects.value = []
    isLoading.value = false
  }

  return {
    // State
    projects,
    isLoading,
    
    // Actions
    fetchProjects,
    createProject,
    updateProject,
    deleteProject,
    reset
  }
}) 
