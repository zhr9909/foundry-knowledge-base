import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '../utils/api.js'

export const useChatStore = defineStore('chat', () => {
  const messages = ref([])
  const conversations = ref([])
  const currentConvId = ref(null)
  const isProcessing = ref(false)
  const showProgress = ref(false)
  const progressSteps = ref({ rewrite: '', search: '', context: '', generate: '', check: '' })
  const logs = ref([])

  function addLog(msg, level = 'info') {
    logs.value.push({ msg, level, time: new Date().toLocaleTimeString('zh-CN', { hour12: false }) })
  }

  function clearChat() {
    messages.value = []
    logs.value = []
    progressSteps.value = { rewrite: '', search: '', context: '', generate: '', check: '' }
    showProgress.value = false
    currentConvId.value = null
  }

  function addMessage(role, content, metadata = {}) {
    messages.value.push({ role, content, metadata })
  }

  async function sendMessage(query, section = '') {
    if (!query.trim() || isProcessing.value) return
    isProcessing.value = true
    addMessage('user', query)
    const msgIdx = messages.value.length
    addMessage('assistant', '', { citations: [], thinking: '', logs: [], question: query })
    if (messages.value[msgIdx]) {
      messages.value[msgIdx].metadata.logs = [...logs.value]
    }
    showProgress.value = true
    progressSteps.value.rewrite = 'active'
    addLog('开始处理查询...')
    addLog('原始查询：' + query)

    try {
      const params = new URLSearchParams({ query })
      if (section) params.set('section', section)
      if (currentConvId.value) params.set('conv_id', currentConvId.value)
      if (localStorage.getItem('auth_token')) params.set('token', localStorage.getItem('auth_token'))
      const recentHistory = messages.value
        .slice(0, Math.max(0, msgIdx - 1))
        .filter((m) => m.role && m.content)
        .slice(-8)
        .map((m) => ({ role: m.role, content: String(m.content).slice(0, 1200) }))
      if (recentHistory.length) params.set('history', JSON.stringify(recentHistory))

      let answer = ''
      let citations = []
      let thinking = ''
      let graph = null

      const es = new EventSource(`/chat/stream?${params}`)
      const result = await new Promise((resolve, reject) => {
        const timeout = setTimeout(() => { es.close(); reject(new Error('timeout')) }, 60000)
        es.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            if (data.type === 'conv_id') { currentConvId.value = data.conv_id; return }
            if (data.type === 'log') { addLog(data.message, data.level || 'info'); if (messages.value[msgIdx]) { messages.value[msgIdx].metadata.logs = [...logs.value] } return }
            if (data.step === 'rewritten') {
              progressSteps.value.rewrite = `\u2192 ${data.queries?.length || 0} 条语句`
              progressSteps.value.search = 'active'
            } else if (data.step === 'searched') {
              progressSteps.value.search = `\u2192 ${data.count} 个候选`
              progressSteps.value.context = 'active'
            } else if (data.step === 'context_ready') {
              progressSteps.value.context = `\u2192 精选 ${data.count} 条`
              progressSteps.value.generate = 'active'
            } else if (data.step === 'checked') {
              progressSteps.value.generate = 'done'
              progressSteps.value.check = data.score >= 7 ? `\u2714 ${data.score}/10` : `${data.score}/10 重试中...`
            }
            if (data.type === 'result') {
              clearTimeout(timeout); es.close()
              answer = data.data.answer || ''
              citations = data.data.citations || []
              thinking = data.data.thinking || ''
              graph = data.data.graph || null
              progressSteps.value.check = '\u2714 完成'
              if (messages.value[msgIdx]) {
                messages.value[msgIdx].content = answer
                messages.value[msgIdx].metadata = { citations, thinking, graph, logs: [...logs.value], question: query }
              }
              resolve(true)
            }
            if (data.type === 'error') {
              clearTimeout(timeout); es.close()
              reject(new Error(data.message))
            }
          } catch {}
        }
        es.onerror = () => { clearTimeout(timeout); es.close(); reject(new Error('SSE Connection failed')) }
      })

      // message updated inline in SSE handler
      return result
    } catch (e) {
      addMessage('assistant', `\u274c 请求失败: ${e.message}`)
      return false
    } finally {
      isProcessing.value = false
      showProgress.value = false
    }
  }

  async function loadConversations() {
    if (!localStorage.getItem('auth_token')) { conversations.value = []; return }
    try { const r = await api.listConversations(); conversations.value = r.conversations || [] }
    catch { conversations.value = [] }
  }

  async function loadConversation(id) {
    try {
      const r = await api.getConversation(id)
      const cv = r.conversation
      if (!cv) return
      currentConvId.value = cv.id
      messages.value = []
      if (cv.messages) {
        for (const m of cv.messages) {
          addMessage(m.role, m.content, m.metadata || {})
        }
      }
      await loadConversations()
    } catch { addLog('\u52a0\u8f7d\u5931\u8d25', 'error') }
  }

  return {
    messages, conversations, currentConvId, isProcessing,
    showProgress, progressSteps, logs,
    addLog, clearChat, addMessage, sendMessage,
    loadConversations, loadConversation,
  }
})
