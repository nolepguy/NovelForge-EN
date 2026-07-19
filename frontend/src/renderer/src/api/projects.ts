import request from './request'
import type { components } from '@renderer/types/generated'

export type ProjectRead = components['schemas']['ProjectRead']
export type ProjectCreate = components['schemas']['ProjectCreate']
export type ProjectUpdate = components['schemas']['ProjectUpdate']

export const getFreeProject = async (): Promise<ProjectRead> => {
  try {
    return await request.get('/projects/free')
  } catch (err) {
    // Handle the case where the backend hasn't updated route order and /free hits /{project_id}: fall back to list lookup
    const list = await request.get<ProjectRead[]>('/projects')
    const found = (list || []).find(p => (p.name || '') === '__free__')
    if (!found) throw err
    return found
  }
}

export const getProjects = (): Promise<ProjectRead[]> => {
  return request.get('/projects')
}

export const createProject = (data: ProjectCreate): Promise<ProjectRead> => {
  return request.post('/projects/', data)
}

export const updateProject = (id: number, data: ProjectUpdate): Promise<void> => {
  return request.put(`/projects/${id}`, data)
}

export const deleteProject = (id: number): Promise<void> => {
  return request.delete(`/projects/${id}`)
} 