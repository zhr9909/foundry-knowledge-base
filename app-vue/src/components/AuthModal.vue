<template>
  <div class="auth-overlay" @click.self="('close')">
    <div class="auth-card">
      <button class="auth-close" @click="('close')">&times;</button>
      <div class="auth-tabs">
        <button :class="{ active: tab === 'login' }" @click="tab='login'">??</button>
        <button :class="{ active: tab === 'register' }" @click="tab='register'">??</button>
      </div>
      <form v-if="tab === 'login'" @submit.prevent="handleLogin" class="auth-form">
        <input v-model="email" type="email" placeholder="??" required />
        <input v-model="password" type="password" placeholder="??" required />
        <button type="submit" class="auth-btn" :disabled="loading">{{ loading ? '???...' : '??' }}</button>
        <p v-if="error" class="auth-error">{{ error }}</p>
        <div class="auth-divider"><span>?</span></div>
        <button type="button" class="auth-btn google-btn" @click="googleLogin">
          <svg width="18" height="18" viewBox="0 0 18 18"><path fill="#4285f4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84c-.21 1.04-.82 1.92-1.74 2.5v2.08h2.82c1.64-1.52 2.58-3.76 2.58-6.22z"/><path fill="#34a853" d="M9 18c2.34 0 4.3-.78 5.73-2.1l-2.82-2.08c-.78.52-1.78.83-2.91.83-2.24 0-4.14-1.51-4.82-3.55H1.27v2.14C2.69 15.96 5.6 18 9 18z"/><path fill="#fbbc05" d="M4.18 10.9c-.18-.52-.28-1.07-.28-1.64s.1-1.12.28-1.64V5.48H1.27A8.98 8.98 0 0 0 0 9c0 1.47.36 2.87 1.27 4.1l2.91-2.2z"/><path fill="#ea4335" d="M9 3.58c1.38 0 2.6.48 3.58 1.4l2.68-2.68C13.28.5 11.32 0 9 0 5.6 0 2.69 2.04 1.27 4.9l2.91 2.2C4.86 5.09 6.76 3.58 9 3.58z"/></svg>
          ?? Google ??
        </button>
      </form>
      <form v-else @submit.prevent="handleRegister" class="auth-form">
        <input v-model="email" type="email" placeholder="??" required />
        <input v-model="username" placeholder="???" required />
        <input v-model="password" type="password" placeholder="?????6??" required minlength="6" />
        <button type="submit" class="auth-btn" :disabled="loading">{{ loading ? '???...' : '??' }}</button>
        <p v-if="error" class="auth-error">{{ error }}</p>
        <div v-if="verifyStep" class="verify-section">
          <p class="verify-hint">??????? {{ email }}</p>
          <input v-model="verifyCode" placeholder="?????" maxlength="6" />
          <button type="button" class="auth-btn" @click="handleVerify">??</button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useAuthStore } from '../stores/auth.js'
import { api } from '../utils/api.js'
const emit = defineEmits(['close'])
const auth = useAuthStore()
const tab = ref('login')
const email = ref(''); const username = ref(''); const password = ref('')
const verifyCode = ref(''); const verifyStep = ref(false)
const loading = ref(false); const error = ref('')

async function handleLogin() {
  loading.value = true; error.value = ''
  try { await auth.login(email.value, password.value); emit('close') }
  catch (e) { error.value = e.message || '????' }
  finally { loading.value = false }
}
async function handleRegister() {
  loading.value = true; error.value = ''
  try { await auth.register(email.value, username.value, password.value); verifyStep.value = true }
  catch (e) { error.value = e.message || '????' }
  finally { loading.value = false }
}
async function handleVerify() {
  loading.value = true; error.value = ''
  try { await api.verifyCode({ email: email.value, code: verifyCode.value }); emit('close') }
  catch (e) { error.value = e.message || '????' }
  finally { loading.value = false }
}
async function googleLogin() {
  try { const r = await api.getGoogleUrl(); if (r.url) window.location.href = r.url }
  catch { error.value = 'Google ????' }
}
</script>

<style scoped>
.auth-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.auth-card { background: #fff; border-radius: 16px; padding: 32px; width: 380px; max-width: 90vw; position: relative; box-shadow: 0 20px 60px rgba(0,0,0,0.15); }
.auth-close { position: absolute; top: 12px; right: 16px; background: none; border: none; font-size: 24px; cursor: pointer; color: #999; }
.auth-tabs { display: flex; gap: 24px; margin-bottom: 24px; border-bottom: 1px solid #eee; }
.auth-tabs button { background: none; border: none; padding: 8px 0 12px; font-size: 15px; color: #999; cursor: pointer; border-bottom: 2px solid transparent; }
.auth-tabs button.active { color: #111; border-bottom-color: #111; font-weight: 600; }
.auth-form { display: flex; flex-direction: column; gap: 12px; }
.auth-form input { padding: 10px 14px; border: 1px solid #e5e5e5; border-radius: 12px; font-size: 14px; outline: none; transition: border-color .2s; }
.auth-form input:focus { border-color: #111; }
.auth-btn { padding: 10px; border: none; border-radius: 12px; font-size: 14px; cursor: pointer; background: #111; color: #fff; font-weight: 500; transition: opacity .2s; }
.auth-btn:disabled { opacity: .5; cursor: not-allowed; }
.google-btn { background: #fff; color: #111; border: 1px solid #e5e5e5; display: flex; align-items: center; justify-content: center; gap: 8px; }
.google-btn:hover { background: #f8f8f8; }
.auth-error { color: #e74c3c; font-size: 13px; }
.auth-divider { display: flex; align-items: center; gap: 12px; color: #999; font-size: 12px; }
.auth-divider::before, .auth-divider::after { content: ''; flex: 1; height: 1px; background: #eee; }
.verify-section { display: flex; flex-direction: column; gap: 12px; padding: 16px; background: #f8f7f5; border-radius: 12px; }
.verify-hint { font-size: 13px; color: #6f6e6b; }
</style>
