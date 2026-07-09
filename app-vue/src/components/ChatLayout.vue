<template>
  <div class="layout">
    <Sidebar :items="chat.conversations" :activeId="chat.currentConvId" @select="loadConversation" @newChat="newChat" />
    <div class="main">
      <header class="topbar">
        <div class="topbar-left">
          <button v-if="auth.isLoggedIn" class="topbar-btn" @click="newChat" title="新建对话">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          </button>
        </div>
        <div class="topbar-right">
          <button class="topbar-btn" @click="toggleTheme" title="切换主题">
            <svg v-if="isDark" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
            <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
          </button>
          <template v-if="auth.isLoggedIn">
            <div class="user-menu">
              <button class="user-avatar-btn" @click.stop="menuOpen = !menuOpen">{{ auth.user?.email?.charAt(0).toUpperCase() || 'U' }}</button>
              <div v-if="menuOpen" class="user-dropdown" @click.stop>
                <div class="user-dropdown-header">{{ auth.user?.email }}</div>
                <button class="user-dropdown-item" @click="auth.logout(); chat.clearChat(); chat.loadConversations()">退出登录</button>
              </div>
            </div>
          </template>
          <button v-else class="login-btn" @click="auth.showAuth = true">登录 / 注册</button>
        </div>
      </header>
      <ChatArea :messages="chat.messages" :chat="chat" @suggest="handleSuggest" />
      <ChatInput :disabled="chat.isProcessing" @send="handleSend" />
    </div>
  </div>
</template>
<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '../stores/auth.js'
import { useChatStore } from '../stores/chat.js'
import Sidebar from './Sidebar.vue'
import ChatArea from './ChatArea.vue'
import ChatInput from './ChatInput.vue'
const auth = useAuthStore()
const chat = useChatStore()
const menuOpen = ref(false)
const isDark = ref(localStorage.getItem('theme') === 'dark')

function toggleTheme() {
  isDark.value = !isDark.value
  document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
}
async function handleSend(text) {
  await chat.sendMessage(text, '')
  if (auth.isLoggedIn) chat.loadConversations()
}
function handleSuggest(query) { handleSend(query) }
async function loadConversation(id) { await chat.loadConversation(id) }
function newChat() { chat.clearChat() }

function closeMenu(e) { if (menuOpen.value) menuOpen.value = false }
onMounted(() => {
  document.addEventListener('click', closeMenu)
  const savedTheme = localStorage.getItem('theme')
  if (savedTheme === 'dark') { isDark.value = true; document.documentElement.setAttribute('data-theme', 'dark') }
  if (auth.isLoggedIn) chat.loadConversations()
})
onUnmounted(() => document.removeEventListener('click', closeMenu))
</script>
<style scoped>
.layout { display: flex; height: 100vh; }
.main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.topbar { display: flex; align-items: center; justify-content: space-between; padding: 8px 16px; border-bottom: 1px solid var(--border-light); }
.topbar-left, .topbar-right { display: flex; align-items: center; gap: 8px; }
.topbar-btn { background: none; border: none; cursor: pointer; padding: 6px; border-radius: 8px; color: var(--text-secondary); display: flex; align-items: center; }
.topbar-btn:hover { background: var(--bg-sub); }
.login-btn { padding: 6px 14px; border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--bg-main); cursor: pointer; font-size: 13px; color: var(--text-primary); }
.login-btn:hover { border-color: var(--border-focus); }
.user-menu { position: relative; }
.user-avatar-btn { width: 32px; height: 32px; border-radius: 50%; border: 1px solid var(--border-light); cursor: pointer; font-size: 13px; font-weight: 600; display: flex; align-items: center; justify-content: center; background: var(--text-primary); color: #fff; }
.user-dropdown { position: absolute; top: 100%; right: 0; margin-top: 4px; background: #fff; border: 1px solid var(--border-light); border-radius: var(--radius-md); box-shadow: var(--shadow-card); min-width: 160px; z-index: 100; }
.user-dropdown-header { padding: 8px 12px; font-size: 12px; color: var(--text-muted); border-bottom: 1px solid var(--border-light); }
.user-dropdown-item { width: 100%; padding: 8px 12px; border: none; background: none; text-align: left; font-size: 13px; cursor: pointer; color: var(--text-secondary); }
.user-dropdown-item:hover { background: var(--bg-sub); }
</style>
