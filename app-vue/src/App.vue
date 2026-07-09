<template>
  <router-view />
  <AuthModal v-if="authStore.showAuth" @close="authStore.showAuth = false" />
</template>
<script setup>
import { onMounted } from 'vue'
import { useAuthStore } from './stores/auth'
import AuthModal from './components/AuthModal.vue'
const authStore = useAuthStore()
onMounted(() => {
  authStore.init()
})
</script>
