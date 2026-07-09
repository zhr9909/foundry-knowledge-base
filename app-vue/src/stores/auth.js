import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useChatStore } from './chat.js'
import { api } from '../utils/api.js'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const token = ref(localStorage.getItem('auth_token') || '')
  const showAuth = ref(false)

  const isLoggedIn = computed(() => !!token.value)

  function saveToken(t) {
    token.value = t
    localStorage.setItem('auth_token', t)
  }

  function clearAuth() {
    user.value = null
    token.value = ''
    localStorage.removeItem('auth_token')
  }

  async function init() {
    // Check URL params for OAuth callback
    const params = new URLSearchParams(window.location.search)
    let urlToken = params.get('token')
    // Try hash too
    if (!urlToken) {
      const hashParams = new URLSearchParams(location.hash.replace('#', '?'))
      urlToken = hashParams.get('token')
    }
    if (urlToken) {
      saveToken(urlToken)
      // Remove token from URL
      history.replaceState(null, '', '/static/#/')
    }
    if (token.value) {
      try { const r = await api.getMe(); user.value = r.user; useChatStore().loadConversations() }
      catch { clearAuth() }
    }
  }

  async function login(email, password) {
    const r = await api.login({ email, password })
    saveToken(r.token)
    user.value = r.user
    try { useChatStore().loadConversations() } catch {}
  }

  async function register(email, username, password) {
    const r = await api.register({ email, username, password })
    saveToken(r.token)
    user.value = r.user
  }

  function logout() { clearAuth() }

  return { user, token, showAuth, isLoggedIn, init, login, register, logout }
})
