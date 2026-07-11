<template>
  <aside class="sidebar">
    <div class="sidebar-brand">
      <div class="brand-mark">FK</div>
      <div>
        <div class="brand-title">Foundry KB</div>
        <div class="brand-subtitle">AI &#x6280;&#x672F;&#x68C0;&#x7D22;</div>
      </div>
    </div>
    <button class="new-chat-btn" @click="$emit('newChat')" title="&#x65B0;&#x5EFA;&#x5BF9;&#x8BDD;">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
      <span>&#x65B0;&#x5EFA;&#x5BF9;&#x8BDD;</span>
    </button>
    <div class="sidebar-section-title">项目空间</div>
    <div class="project-list">
      <button v-if="!creatingProject" class="project-create" @click="startCreate">
        <span>+</span>
        <strong>新建项目</strong>
      </button>
      <form v-else class="project-create-form" @submit.prevent="submitCreate" @click.stop>
        <input
          ref="createInput"
          v-model.trim="createName"
          type="text"
          maxlength="80"
          placeholder="输入项目名称"
          @keydown.esc.prevent="cancelCreate"
        />
        <div class="project-form-actions">
          <button type="button" @click="cancelCreate">取消</button>
          <button type="submit" :disabled="!createName">创建</button>
        </div>
      </form>
      <div
        v-for="project in projects"
        :key="project.id"
        class="project-item"
        :class="{ active: activeProjectId === project.id }"
        role="button"
        tabindex="0"
        @click="$emit('selectProject', project.id)"
        @keydown.enter="$emit('selectProject', project.id)"
      >
        <span class="project-mark"></span>
        <span class="project-copy">
          <strong v-if="editingProjectId !== project.id" title="双击重命名" @dblclick.stop="startRename(project)">{{ project.name }}</strong>
          <form v-else class="project-rename-form" @submit.prevent.stop="submitRename(project.id)" @click.stop>
            <input
              ref="renameInput"
              v-model.trim="editingName"
              type="text"
              maxlength="80"
              @blur="submitRename(project.id)"
              @keydown.esc.prevent="cancelRename"
            />
          </form>
          <small>{{ project.conversation_count || 0 }} 个对话 · {{ project.artifact_count || 0 }} 个产物</small>
        </span>
      </div>
      <div v-if="projects.length === 0" class="project-empty">暂无项目</div>
    </div>
    <div class="sidebar-section-title">&#x5386;&#x53F2;&#x5BF9;&#x8BDD;</div>
    <div class="history-list">
      <div v-if="items.length === 0" class="history-empty">
        <span class="empty-line"></span>
        <strong>&#x6682;&#x65E0;&#x5BF9;&#x8BDD;&#x8BB0;&#x5F55;</strong>
        <small>&#x767B;&#x5F55;&#x540E;&#x4F1A;&#x5728;&#x8FD9;&#x91CC;&#x4FDD;&#x5B58;&#x68C0;&#x7D22;&#x8FC7;&#x7A0B;</small>
      </div>
      <button v-for="item in items" :key="item.id" class="history-item" :class="{ active: activeId === item.id }" @click="$emit('select', item.id)">
        <span class="history-dot"></span>
        <span class="history-item-title">{{ item.title || '\u65b0\u5bf9\u8bdd' }}</span>
      </button>
    </div>
  </aside>
</template>
<script setup>
import { nextTick, ref } from 'vue'

defineProps({
  items: { type: Array, default: () => [] },
  activeId: { type: Number, default: null },
  projects: { type: Array, default: () => [] },
  activeProjectId: { type: Number, default: null },
})
const emit = defineEmits(['select', 'newChat', 'selectProject', 'newProject', 'renameProject'])

const creatingProject = ref(false)
const createName = ref('')
const createInput = ref(null)
const editingProjectId = ref(null)
const editingName = ref('')
const renameInput = ref(null)

function startCreate() {
  creatingProject.value = true
  createName.value = ''
  nextTick(() => createInput.value?.focus())
}

function submitCreate() {
  const name = createName.value.trim()
  if (!name) return
  emit('newProject', name)
  creatingProject.value = false
  createName.value = ''
}

function cancelCreate() {
  creatingProject.value = false
  createName.value = ''
}

function startRename(project) {
  editingProjectId.value = project.id
  editingName.value = project.name || ''
  nextTick(() => {
    const input = Array.isArray(renameInput.value) ? renameInput.value[0] : renameInput.value
    input?.focus()
    input?.select()
  })
}

function submitRename(id) {
  if (editingProjectId.value !== id) return
  const name = editingName.value.trim()
  if (name) emit('renameProject', { id, name })
  editingProjectId.value = null
  editingName.value = ''
}

function cancelRename() {
  editingProjectId.value = null
  editingName.value = ''
}
</script>
<style scoped>
.sidebar { width: 280px; min-width: 280px; height: 100vh; display: flex; flex-direction: column; gap: 12px; padding: 16px 14px; background: var(--bg-sidebar); color: var(--text-inverse); border-right: 1px solid rgba(255,255,255,.08); }
.sidebar-brand { display: flex; align-items: center; gap: 10px; padding: 4px 4px 10px; }
.brand-mark { width: 34px; height: 34px; display: grid; place-items: center; border: 1px solid rgba(255,255,255,.18); border-radius: 8px; background: #0f766e; font-size: 12px; font-weight: 800; letter-spacing: 0; }
.brand-title { font-weight: 720; font-size: 14px; letter-spacing: 0; }
.brand-subtitle { color: rgba(248,250,252,.62); font-size: 12px; margin-top: 2px; }
.new-chat-btn { height: 42px; width: 100%; border: 1px solid rgba(255,255,255,.16); border-radius: var(--radius-md); background: rgba(255,255,255,.08); color: var(--text-inverse); display: flex; align-items: center; justify-content: center; gap: 8px; cursor: pointer; transition: background .18s ease, border-color .18s ease; }
.new-chat-btn:hover { background: rgba(255,255,255,.12); border-color: rgba(255,255,255,.28); }
.new-chat-btn svg { width: 16px; height: 16px; stroke: currentColor; stroke-width: 2; fill: none; stroke-linecap: round; }
.sidebar-section-title { margin-top: 8px; padding: 0 6px; color: rgba(248,250,252,.54); font-size: 12px; font-weight: 650; }
.project-list { display: flex; flex-direction: column; gap: 6px; max-height: 214px; overflow-y: auto; padding-right: 2px; }
.project-create, .project-item { width: 100%; border: 1px solid rgba(255,255,255,.12); border-radius: var(--radius-md); color: rgba(248,250,252,.78); background: rgba(255,255,255,.05); cursor: pointer; transition: background .16s ease, border-color .16s ease, color .16s ease; }
.project-create { min-height: 36px; display: flex; align-items: center; justify-content: center; gap: 7px; font-size: 13px; }
.project-create span { width: 18px; height: 18px; display: grid; place-items: center; border-radius: 50%; background: rgba(20,184,166,.18); color: #5eead4; font-weight: 800; }
.project-create:hover, .project-item:hover { color: #fff; background: rgba(255,255,255,.09); border-color: rgba(255,255,255,.24); }
.project-create-form { border: 1px solid rgba(20,184,166,.34); border-radius: var(--radius-md); background: rgba(255,255,255,.07); padding: 8px; }
.project-create-form input, .project-rename-form input { width: 100%; min-width: 0; border: 1px solid rgba(255,255,255,.16); border-radius: var(--radius-sm); background: rgba(2,6,23,.38); color: #fff; padding: 7px 8px; font-size: 13px; outline: none; }
.project-create-form input:focus, .project-rename-form input:focus { border-color: rgba(20,184,166,.72); box-shadow: 0 0 0 3px rgba(20,184,166,.14); }
.project-form-actions { margin-top: 7px; display: flex; justify-content: flex-end; gap: 6px; }
.project-form-actions button { min-height: 28px; border: 1px solid rgba(255,255,255,.14); border-radius: var(--radius-sm); background: rgba(255,255,255,.06); color: rgba(248,250,252,.78); padding: 0 9px; font-size: 12px; cursor: pointer; }
.project-form-actions button[type="submit"] { border-color: rgba(20,184,166,.45); background: rgba(20,184,166,.18); color: #ccfbf1; font-weight: 700; }
.project-form-actions button:disabled { opacity: .45; cursor: not-allowed; }
.project-item { min-height: 50px; display: flex; align-items: center; gap: 9px; padding: 8px 10px; text-align: left; }
.project-item.active { background: rgba(20,184,166,.15); border-color: rgba(20,184,166,.36); color: #fff; }
.project-mark { width: 8px; height: 28px; border-radius: 999px; background: linear-gradient(180deg, #14b8a6, #2563eb); flex: 0 0 auto; opacity: .8; }
.project-copy { min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.project-copy strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; font-weight: 700; }
.project-rename-form { width: 100%; }
.project-rename-form input { height: 26px; padding: 3px 6px; }
.project-copy small, .project-empty { color: rgba(248,250,252,.48); font-size: 12px; }
.project-empty { padding: 2px 10px 8px; }
.history-list { min-height: 0; flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 4px; padding-right: 2px; }
.history-empty { margin: 16px 4px; padding: 18px 14px; border: 1px dashed rgba(255,255,255,.18); border-radius: var(--radius-md); color: rgba(248,250,252,.72); display: flex; flex-direction: column; gap: 6px; }
.history-empty strong { font-size: 13px; font-weight: 650; }
.history-empty small { font-size: 12px; line-height: 1.5; color: rgba(248,250,252,.5); }
.empty-line { width: 26px; height: 2px; background: var(--accent); border-radius: 999px; }
.history-item { width: 100%; border: 0; border-radius: var(--radius-md); background: transparent; color: rgba(248,250,252,.72); display: flex; align-items: center; gap: 9px; min-height: 36px; padding: 8px 10px; text-align: left; cursor: pointer; transition: background .16s ease, color .16s ease; }
.history-item:hover { background: rgba(255,255,255,.08); color: #fff; }
.history-item.active { background: rgba(20,184,166,.16); color: #fff; }
.history-dot { width: 6px; height: 6px; border-radius: 50%; background: rgba(248,250,252,.34); flex: 0 0 auto; }
.history-item.active .history-dot { background: #14b8a6; }
.history-item-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; }
@media (max-width: 820px) { .sidebar { width: 232px; min-width: 232px; } }
</style>
