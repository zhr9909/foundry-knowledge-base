<template>
  <div class="layout">
    <Sidebar
      :items="chat.conversations"
      :activeId="chat.currentConvId"
      :projects="project.projects"
      :activeProjectId="project.activeProject?.id"
      @select="loadConversation"
      @newChat="newChat"
      @selectProject="loadProject"
      @newProject="newProject"
      @renameProject="renameProject"
    />
    <div class="main">
      <header class="topbar">
        <div class="topbar-left">
          <button v-if="auth.isLoggedIn" class="icon-btn" @click="newChat" title="&#x65B0;&#x5EFA;&#x5BF9;&#x8BDD;"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg></button>
          <div class="workspace-title"><span class="status-dot"></span><span>&#x77E5;&#x8BC6;&#x68C0;&#x7D22;&#x5DE5;&#x4F5C;&#x53F0;</span></div>
          <button v-if="project.activeProject" class="active-project-chip" type="button" @click="project.isPanelOpen = true" title="打开当前项目">
            <span>项目</span>
            <strong>{{ project.activeProject.name }}</strong>
          </button>
          <ModeSwitcher :model-value="chat.currentMode" @update:modelValue="chat.setMode" />
        </div>
        <div class="topbar-right">
          <button class="icon-btn" @click="toggleTheme" title="&#x5207;&#x6362;&#x4E3B;&#x9898;">
            <svg v-if="isDark" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" /></svg>
            <svg v-else viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v2M12 19v2M5.64 5.64l1.41 1.41M16.95 16.95l1.41 1.41M3 12h2M19 12h2M5.64 18.36l1.41-1.41M16.95 7.05l1.41-1.41" /><circle cx="12" cy="12" r="4" /></svg>
          </button>
          <template v-if="auth.isLoggedIn">
            <div class="user-menu"><button class="user-avatar-btn" @click.stop="menuOpen = !menuOpen">{{ auth.user?.email?.charAt(0).toUpperCase() || 'U' }}</button><div v-if="menuOpen" class="user-dropdown" @click.stop><div class="user-dropdown-header">{{ auth.user?.email }}</div><button class="user-dropdown-item" @click="logout">&#x9000;&#x51FA;&#x767B;&#x5F55;</button></div></div>
          </template>
          <button v-else class="login-btn" @click="auth.showAuth = true">&#x767B;&#x5F55; / &#x6CE8;&#x518C;</button>
        </div>
      </header>
      <ChatArea :messages="chat.messages" :chat="chat" @suggest="handleSuggest" @save-artifact="handleSaveArtifact" />
      <ChatInput :disabled="chat.isProcessing" :mode="chat.currentMode" @send="handleSend" />
    </div>
    <ProjectPanel
      v-if="project.isPanelOpen && project.activeProject"
      :project="project.activeProject"
      :isGeneratingBrief="project.isGeneratingBrief"
      @close="project.closeProject"
      @select-conversation="loadConversation"
      @generate-brief="generateProjectBrief"
      @start-workflow="startWorkflow"
    />
  </div>
</template>
<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '../stores/auth.js'
import { useChatStore } from '../stores/chat.js'
import { useProjectStore } from '../stores/project.js'
import Sidebar from './Sidebar.vue'
import ChatArea from './ChatArea.vue'
import ChatInput from './ChatInput.vue'
import ModeSwitcher from './ModeSwitcher.vue'
import ProjectPanel from './ProjectPanel.vue'
const auth = useAuthStore()
const chat = useChatStore()
const project = useProjectStore()
const menuOpen = ref(false)
const isDark = ref(localStorage.getItem('theme') === 'dark')
function toggleTheme() { isDark.value = !isDark.value; document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light'); localStorage.setItem('theme', isDark.value ? 'dark' : 'light') }
async function handleSend(payload) {
  const options = typeof payload === 'object' && payload ? payload : {}
  const text = typeof payload === 'string' ? payload : (options.query || '')
  await chat.sendMessage(text, '', project.activeProject?.id || null, options)
  if (auth.isLoggedIn) {
    await chat.loadConversations()
    if (project.activeProject?.id) {
      await project.loadProject(project.activeProject.id, false)
      await project.loadProjects()
    } else {
      await project.loadProjects()
    }
  }
}
function handleSuggest(payload) { handleSend(payload) }
async function loadConversation(id) {
  const cv = await chat.loadConversation(id)
  if (cv?.project_id) await project.loadProject(cv.project_id)
}
function newChat() { chat.clearChat() }
async function loadProject(id) { await project.loadProject(id) }
async function newProject(name) {
  if (!auth.isLoggedIn) { auth.showAuth = true; return }
  await project.createProject({ name })
}
async function renameProject(payload) {
  if (!auth.isLoggedIn || !payload?.id) return
  await project.updateProject(payload.id, { name: payload.name })
}
async function generateProjectBrief() {
  if (!auth.isLoggedIn || !project.activeProject?.id) return
  await project.generateBrief(project.activeProject.id)
}
function startWorkflow(mode) {
  if (!mode) return
  chat.setMode(mode)
  project.closeProject()
}
async function handleSaveArtifact(msg) {
  if (!auth.isLoggedIn) { auth.showAuth = true; return }
  const question = msg.metadata?.question || '项目产物'
  let target = project.activeProject
  if (!target) {
    target = await project.createProject({ name: question.slice(0, 36) })
  }
  await project.saveArtifact(target.id, {
    type: msg.metadata?.mode || chat.currentMode || 'qa',
    title: question.slice(0, 80),
    content: msg.content || '',
    structured_data: msg.metadata?.structured_output || {},
    citations: msg.metadata?.citations || [],
    metadata: {
      question,
      retrieval: msg.metadata?.retrieval || null,
      graph: msg.metadata?.graph || null,
      mode: msg.metadata?.mode || chat.currentMode || 'qa',
    },
  })
}
function logout() { auth.logout(); chat.clearChat(); chat.loadConversations(); project.clearProjects(); menuOpen.value = false }
function closeMenu() { if (menuOpen.value) menuOpen.value = false }
onMounted(() => { document.addEventListener('click', closeMenu); const savedTheme = localStorage.getItem('theme'); if (savedTheme === 'dark') { isDark.value = true; document.documentElement.setAttribute('data-theme', 'dark') } if (auth.isLoggedIn) { chat.loadConversations(); project.loadProjects() } })
onUnmounted(() => document.removeEventListener('click', closeMenu))
</script>
<style scoped>
.layout { display: flex; height: 100vh; background: var(--bg-shell); }
.main { flex: 1; min-width: 0; display: flex; flex-direction: column; background: var(--bg-main); }
.topbar { height: 58px; display: flex; align-items: center; justify-content: space-between; padding: 0 18px; background: rgba(255,255,255,.82); border-bottom: 1px solid var(--border-light); backdrop-filter: blur(10px); }
[data-theme="dark"] .topbar { background: rgba(20,31,47,.82); }
.topbar-left, .topbar-right { display: flex; align-items: center; gap: 10px; }
.topbar-left { min-width: 0; flex: 1; }
.topbar-right { flex: 0 0 auto; }
.workspace-title { display: inline-flex; align-items: center; gap: 8px; color: var(--text-secondary); font-size: 13px; font-weight: 650; }
.status-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 0 4px var(--accent-soft); }
.active-project-chip { max-width: 230px; min-height: 34px; display: inline-flex; align-items: center; gap: 7px; border: 1px solid color-mix(in srgb, var(--accent) 28%, var(--border-light)); border-radius: var(--radius-md); background: var(--accent-soft); color: var(--accent-strong); padding: 0 10px; cursor: pointer; }
.active-project-chip span { font-size: 11px; font-weight: 800; }
.active-project-chip strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; font-weight: 760; }
.active-project-chip:hover { border-color: var(--accent); }
.icon-btn { width: 34px; height: 34px; border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--bg-surface); color: var(--text-secondary); display: grid; place-items: center; cursor: pointer; transition: background .16s ease, color .16s ease, border-color .16s ease; }
.icon-btn:hover { background: var(--bg-hover); color: var(--text-primary); border-color: var(--border-strong); }
.icon-btn svg { width: 17px; height: 17px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.login-btn { height: 34px; padding: 0 14px; border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--bg-surface); color: var(--text-primary); font-size: 13px; font-weight: 650; cursor: pointer; }
.login-btn:hover { border-color: var(--accent); background: var(--accent-soft); }
.user-menu { position: relative; }
.user-avatar-btn { width: 34px; height: 34px; border: 1px solid color-mix(in srgb, var(--accent) 30%, transparent); border-radius: 50%; background: var(--bg-user); color: #fff; font-size: 13px; font-weight: 760; cursor: pointer; }
.user-dropdown { position: fixed; top: 48px; right: 16px; min-width: 220px; background: var(--bg-surface); border: 1px solid var(--border-light); border-radius: var(--radius-md); box-shadow: var(--shadow-panel); z-index: 30; overflow: hidden; }
.user-dropdown-header { padding: 10px 12px; color: var(--text-muted); border-bottom: 1px solid var(--border-light); font-size: 12px; }
.user-dropdown-item { width: 100%; padding: 10px 12px; border: 0; background: transparent; color: var(--text-secondary); text-align: left; cursor: pointer; }
.user-dropdown-item:hover { background: var(--bg-hover); color: var(--text-primary); }
@media (max-width: 980px) {
  .topbar { height: auto; min-height: 58px; align-items: stretch; padding: 10px 12px; gap: 10px; }
  .topbar-left { flex-wrap: wrap; }
  .workspace-title { min-height: 34px; }
}
</style>
