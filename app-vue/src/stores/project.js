import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../utils/api.js'

export const useProjectStore = defineStore('project', () => {
  const projects = ref([])
  const activeProject = ref(null)
  const isPanelOpen = ref(false)
  const isLoading = ref(false)
  const isGeneratingBrief = ref(false)
  const lastError = ref('')

  function clearProjects() {
    projects.value = []
    activeProject.value = null
    isPanelOpen.value = false
    lastError.value = ''
  }

  async function loadProjects() {
    if (!localStorage.getItem('auth_token')) {
      clearProjects()
      return
    }
    isLoading.value = true
    lastError.value = ''
    try {
      const r = await api.listProjects()
      projects.value = r.projects || []
    } catch (e) {
      projects.value = []
      lastError.value = e.message || '加载项目失败'
    } finally {
      isLoading.value = false
    }
  }

  async function createProject(data = {}) {
    if (!localStorage.getItem('auth_token')) throw new Error('请先登录')
    const r = await api.createProject(data)
    activeProject.value = r.project
    isPanelOpen.value = true
    await loadProjects()
    return r.project
  }

  async function loadProject(id, openPanel = true) {
    if (!id) return null
    isLoading.value = true
    lastError.value = ''
    try {
      const r = await api.getProject(id)
      activeProject.value = r.project
      if (openPanel) isPanelOpen.value = true
      return r.project
    } catch (e) {
      lastError.value = e.message || '加载项目失败'
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function saveArtifact(projectId, artifact) {
    const r = await api.saveProjectArtifact(projectId, artifact)
    await loadProject(projectId, true)
    await loadProjects()
    return r.artifact
  }

  async function updateProject(id, data) {
    const r = await api.updateProject(id, data)
    activeProject.value = r.project
    await loadProjects()
    return r.project
  }

  async function generateBrief(id) {
    if (!id) return null
    isGeneratingBrief.value = true
    lastError.value = ''
    try {
      const r = await api.generateProjectBrief(id)
      activeProject.value = r.project || activeProject.value
      isPanelOpen.value = true
      await loadProjects()
      return r.artifact
    } catch (e) {
      lastError.value = e.message || '生成项目简报失败'
      throw e
    } finally {
      isGeneratingBrief.value = false
    }
  }

  function closeProject() {
    isPanelOpen.value = false
  }

  function clearActiveProject() {
    activeProject.value = null
    isPanelOpen.value = false
  }

  return {
    projects,
    activeProject,
    isPanelOpen,
    isLoading,
    isGeneratingBrief,
    lastError,
    clearProjects,
    loadProjects,
    createProject,
    loadProject,
    saveArtifact,
    updateProject,
    generateBrief,
    closeProject,
    clearActiveProject,
  }
})
