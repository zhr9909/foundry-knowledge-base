import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import './style.css'

const pinia = createPinia()

const router = createRouter({
  history: createWebHashHistory('/static/'),
  routes: [
    { path: '/', component: () => import('./components/ChatLayout.vue') },
    { path: '/pdf', component: () => import('./components/PDFViewer.vue') },
  ]
})

const app = createApp(App)
app.use(pinia)
app.use(router)
app.mount('#app')
