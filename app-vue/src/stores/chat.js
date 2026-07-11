import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '../utils/api.js'

export const useChatStore = defineStore('chat', () => {
  const supportedModes = ['qa', 'requirement_clarification', 'solution_draft', 'selection_matrix', 'defect_diagnosis']
  const defaultProgress = () => ({ rewrite: '', search: '', context: '', generate: '', check: '' })
  const defaultSession = () => ({
    messages: [],
    currentConvId: null,
    showProgress: false,
    progressSteps: defaultProgress(),
    logs: [],
  })
  const modeSessions = ref(Object.fromEntries(supportedModes.map((mode) => [mode, defaultSession()])))
  const messages = ref([])
  const conversations = ref([])
  const currentConvId = ref(null)
  const isProcessing = ref(false)
  const showProgress = ref(false)
  const progressSteps = ref(defaultProgress())
  const logs = ref([])
  const currentMode = ref(localStorage.getItem('task_mode') || 'qa')

  function snapshotMode(mode = currentMode.value) {
    if (!supportedModes.includes(mode)) return
    modeSessions.value[mode] = {
      messages: [...messages.value],
      currentConvId: currentConvId.value,
      showProgress: showProgress.value,
      progressSteps: { ...progressSteps.value },
      logs: [...logs.value],
    }
  }

  function restoreMode(mode) {
    const session = modeSessions.value[mode] || defaultSession()
    messages.value = [...session.messages]
    currentConvId.value = session.currentConvId
    showProgress.value = session.showProgress
    progressSteps.value = { ...session.progressSteps }
    logs.value = [...session.logs]
  }

  function setMode(mode) {
    if (isProcessing.value) return
    const nextMode = supportedModes.includes(mode) ? mode : 'qa'
    snapshotMode()
    currentMode.value = nextMode
    localStorage.setItem('task_mode', currentMode.value)
    restoreMode(nextMode)
  }

  function addLog(msg, level = 'info') {
    logs.value.push({ msg, level, time: new Date().toLocaleTimeString('zh-CN', { hour12: false }) })
  }

  function clearChat() {
    messages.value = []
    logs.value = []
    progressSteps.value = defaultProgress()
    showProgress.value = false
    currentConvId.value = null
    snapshotMode()
  }

  function addMessage(role, content, metadata = {}) {
    messages.value.push({ role, content, metadata })
    snapshotMode()
  }

  async function sendMessage(query, section = '') {
    if (!query.trim() || isProcessing.value) return
    isProcessing.value = true
    addMessage('user', query)
    const msgIdx = messages.value.length
    addMessage('assistant', '', { citations: [], thinking: '', logs: [], question: query, retrieval: null, mode: currentMode.value, structured_output: null })
    if (messages.value[msgIdx]) {
      messages.value[msgIdx].metadata.logs = [...logs.value]
    }
    showProgress.value = true
    progressSteps.value.rewrite = 'active'
    addLog('开始处理查询...')
    addLog('原始查询：' + query)

    try {
      const params = new URLSearchParams({ query })
      params.set('mode', currentMode.value)
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
      let retrieval = null
      let mode = currentMode.value
      let structuredOutput = null

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
              retrieval = data.retrieval || retrieval
              if (messages.value[msgIdx]) {
                messages.value[msgIdx].metadata = { ...messages.value[msgIdx].metadata, retrieval }
              }
            } else if (data.step === 'searched') {
              progressSteps.value.search = `\u2192 ${data.count} 个候选`
              progressSteps.value.context = 'active'
              retrieval = data.retrieval || { ...(retrieval || {}), candidate_count: data.count }
              if (messages.value[msgIdx]) {
                messages.value[msgIdx].metadata = { ...messages.value[msgIdx].metadata, retrieval }
              }
            } else if (data.step === 'context_ready') {
              progressSteps.value.context = `\u2192 精选 ${data.count} 条`
              progressSteps.value.generate = 'active'
              retrieval = data.retrieval || { ...(retrieval || {}), selected_count: data.count }
              if (messages.value[msgIdx]) {
                messages.value[msgIdx].metadata = { ...messages.value[msgIdx].metadata, retrieval }
              }
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
              retrieval = data.data.retrieval || retrieval
              mode = data.data.mode || mode
              structuredOutput = data.data.structured_output || null
              progressSteps.value.check = '\u2714 完成'
              if (messages.value[msgIdx]) {
                messages.value[msgIdx].content = answer
                messages.value[msgIdx].metadata = { citations, thinking, graph, logs: [...logs.value], question: query, retrieval, mode, structured_output: structuredOutput }
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
      snapshotMode()
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
      const targetModeMsg = [...(cv.messages || [])].reverse().find((m) => supportedModes.includes(m.metadata?.mode))
      const targetMode = targetModeMsg?.metadata?.mode || currentMode.value
      if (targetMode !== currentMode.value) setMode(targetMode)
      currentConvId.value = cv.id
      messages.value = []
      if (cv.messages) {
        for (const m of cv.messages) {
          messages.value.push({ role: m.role, content: m.content, metadata: m.metadata || {} })
        }
      }
      snapshotMode(targetMode)
      await loadConversations()
    } catch { addLog('\u52a0\u8f7d\u5931\u8d25', 'error') }
  }

  return {
    messages, conversations, currentConvId, isProcessing,
    showProgress, progressSteps, logs, currentMode,
    addLog, clearChat, addMessage, sendMessage,
    loadConversations, loadConversation, setMode,
  }
})
