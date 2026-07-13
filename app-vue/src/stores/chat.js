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
  const showProgress = ref(false)
  const progressSteps = ref(defaultProgress())
  const logs = ref([])
  const currentMode = ref(localStorage.getItem('task_mode') || 'qa')
  let sessionSeq = 1
  const currentSessionToken = ref(sessionSeq)
  const processingSessions = ref({})
  const isProcessing = computed(() => !!processingSessions.value[currentSessionToken.value])
  let activeRunSeq = 0
  const activeRuns = new Map()
  const activeStreams = new Map()
  const activeRejects = new Map()
  const backgroundSessions = new Map()
  const convSessionTokens = new Map()

  function setProcessing(token, value) {
    processingSessions.value = { ...processingSessions.value, [token]: value }
  }

  function cloneSession(session) {
    return {
      messages: [...(session?.messages || [])],
      currentConvId: session?.currentConvId || null,
      showProgress: !!session?.showProgress,
      progressSteps: { ...(session?.progressSteps || defaultProgress()) },
      logs: [...(session?.logs || [])],
      sessionToken: session?.sessionToken || ++sessionSeq,
    }
  }

  function currentSessionState() {
    return {
      messages: messages.value,
      currentConvId: currentConvId.value,
      showProgress: showProgress.value,
      progressSteps: progressSteps.value,
      logs: logs.value,
      sessionToken: currentSessionToken.value,
    }
  }

  function applySessionState(state) {
    messages.value = state.messages
    currentConvId.value = state.currentConvId
    showProgress.value = state.showProgress
    progressSteps.value = state.progressSteps
    logs.value = state.logs
    currentSessionToken.value = state.sessionToken
  }

  function mutateRunSession(mode, token, updater) {
    if (currentMode.value === mode && currentSessionToken.value === token) {
      const state = {
        messages: messages.value,
        currentConvId: currentConvId.value,
        showProgress: showProgress.value,
        progressSteps: progressSteps.value,
        logs: logs.value,
        sessionToken: currentSessionToken.value,
      }
      updater(state)
      applySessionState(state)
      snapshotMode(mode)
      return
    }
    const state = cloneSession(backgroundSessions.get(token) || modeSessions.value[mode] || defaultSession())
    state.sessionToken = token
    updater(state)
    backgroundSessions.set(token, cloneSession(state))
    if (state.currentConvId) convSessionTokens.set(state.currentConvId, token)
  }

  function snapshotMode(mode = currentMode.value) {
    if (!supportedModes.includes(mode)) return
    modeSessions.value[mode] = {
      messages: [...messages.value],
      currentConvId: currentConvId.value,
      showProgress: showProgress.value,
      progressSteps: { ...progressSteps.value },
      logs: [...logs.value],
      sessionToken: currentSessionToken.value,
    }
  }

  function restoreMode(mode) {
    const session = modeSessions.value[mode] || defaultSession()
    applySessionState(cloneSession(session))
  }

  function setMode(mode) {
    const nextMode = supportedModes.includes(mode) ? mode : 'qa'
    snapshotMode()
    currentMode.value = nextMode
    localStorage.setItem('task_mode', currentMode.value)
    restoreMode(nextMode)
  }

  function addLog(msg, level = 'info') {
    logs.value.push({ msg, level, time: new Date().toLocaleTimeString('zh-CN', { hour12: false }) })
  }

  function cancelActiveStream(token = currentSessionToken.value) {
    activeRuns.set(token, ++activeRunSeq)
    const reject = activeRejects.get(token)
    activeRejects.delete(token)
    const stream = activeStreams.get(token)
    if (stream) {
      try { stream.close() } catch {}
      activeStreams.delete(token)
    }
    if (reject) reject(new Error('canceled'))
    setProcessing(token, false)
    mutateRunSession(currentMode.value, token, (state) => { state.showProgress = false })
  }

  function clearChat() {
    cancelActiveStream()
    messages.value = []
    logs.value = []
    progressSteps.value = defaultProgress()
    currentConvId.value = null
    currentSessionToken.value = ++sessionSeq
    snapshotMode()
  }

  function addMessage(role, content, metadata = {}) {
    messages.value.push({ role, content, metadata })
    snapshotMode()
  }

  async function sendMessage(query, section = '', projectId = null, options = {}) {
    const runMode = currentMode.value
    const runToken = currentSessionToken.value
    if (!query.trim() || processingSessions.value[runToken]) return
    const runId = ++activeRunSeq
    activeRuns.set(runToken, runId)
    setProcessing(runToken, true)
    const displayQuery = options.displayQuery || query
    addMessage('user', displayQuery)
    const msgIdx = messages.value.length
    addMessage('assistant', '', { citations: [], thinking: '', logs: [], question: displayQuery, retrieval: null, mode: currentMode.value, structured_output: null })
    if (messages.value[msgIdx]) {
      messages.value[msgIdx].metadata.logs = [...logs.value]
    }
    showProgress.value = true
    progressSteps.value.rewrite = 'active'
    addLog('开始处理查询...')
    addLog('原始查询：' + query)
    backgroundSessions.set(runToken, cloneSession(currentSessionState()))

    let es = null
    try {
      const params = new URLSearchParams({ query })
      if (options.type === 'entity_correction' && options.entity) {
        params.set('correction_entity', options.entity)
        params.set('correction_original_query', query)
        params.set('display_query', displayQuery)
      }
      params.set('mode', runMode)
      if (section) params.set('section', section)
      if (currentConvId.value) params.set('conv_id', currentConvId.value)
      if (!currentConvId.value && projectId) params.set('project_id', projectId)
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
      let mode = runMode
      let structuredOutput = null

      es = new EventSource(`/chat/stream?${params}`)
      activeStreams.set(runToken, es)
      const result = await new Promise((resolve, reject) => {
        activeRejects.set(runToken, reject)
        const timeout = setTimeout(() => {
          es.close()
          if (activeStreams.get(runToken) === es) activeStreams.delete(runToken)
          if (activeRejects.get(runToken) === reject) activeRejects.delete(runToken)
          if (activeRuns.get(runToken) === runId) reject(new Error('timeout'))
        }, 60000)
        es.onmessage = (event) => {
          if (activeRuns.get(runToken) !== runId) return
          try {
            const data = JSON.parse(event.data)
            if (data.type === 'conv_id') {
              convSessionTokens.set(data.conv_id, runToken)
              mutateRunSession(runMode, runToken, (state) => { state.currentConvId = data.conv_id })
              return
            }
            if (data.type === 'log') {
              mutateRunSession(runMode, runToken, (state) => {
                state.logs.push({ msg: data.message, level: data.level || 'info', time: new Date().toLocaleTimeString('zh-CN', { hour12: false }) })
                if (state.messages[msgIdx]) state.messages[msgIdx].metadata.logs = [...state.logs]
              })
              return
            }
            if (data.step === 'rewritten') {
              retrieval = data.retrieval || retrieval
              mutateRunSession(runMode, runToken, (state) => {
                state.progressSteps.rewrite = `\u2192 ${data.queries?.length || 0} 条语句`
                state.progressSteps.search = 'active'
                if (state.messages[msgIdx]) state.messages[msgIdx].metadata = { ...state.messages[msgIdx].metadata, retrieval }
              })
            } else if (data.step === 'searched') {
              retrieval = data.retrieval || { ...(retrieval || {}), candidate_count: data.count }
              mutateRunSession(runMode, runToken, (state) => {
                state.progressSteps.search = `\u2192 ${data.count} 个候选`
                state.progressSteps.context = 'active'
                if (state.messages[msgIdx]) state.messages[msgIdx].metadata = { ...state.messages[msgIdx].metadata, retrieval }
              })
            } else if (data.step === 'context_ready') {
              retrieval = data.retrieval || { ...(retrieval || {}), selected_count: data.count }
              mutateRunSession(runMode, runToken, (state) => {
                state.progressSteps.context = `\u2192 精选 ${data.count} 条`
                state.progressSteps.generate = 'active'
                if (state.messages[msgIdx]) state.messages[msgIdx].metadata = { ...state.messages[msgIdx].metadata, retrieval }
              })
            } else if (data.step === 'checked') {
              mutateRunSession(runMode, runToken, (state) => {
                state.progressSteps.generate = 'done'
                state.progressSteps.check = data.score >= 7 ? `\u2714 ${data.score}/10` : `${data.score}/10 重试中...`
              })
            }
            if (data.type === 'result') {
              clearTimeout(timeout); es.close()
              if (activeStreams.get(runToken) === es) activeStreams.delete(runToken)
              if (activeRejects.get(runToken) === reject) activeRejects.delete(runToken)
              answer = data.data.answer || ''
              citations = data.data.citations || []
              thinking = data.data.thinking || ''
              graph = data.data.graph || null
              retrieval = data.data.retrieval || retrieval
              mode = data.data.mode || mode
              structuredOutput = data.data.structured_output || null
              mutateRunSession(runMode, runToken, (state) => {
                state.progressSteps.check = '\u2714 完成'
                state.showProgress = false
                if (state.messages[msgIdx]) {
                  state.messages[msgIdx].content = answer
                  state.messages[msgIdx].metadata = { citations, thinking, graph, logs: [...state.logs], question: displayQuery, retrieval, mode, structured_output: structuredOutput }
                }
              })
              resolve(true)
            }
            if (data.type === 'error') {
              clearTimeout(timeout); es.close()
              if (activeStreams.get(runToken) === es) activeStreams.delete(runToken)
              if (activeRejects.get(runToken) === reject) activeRejects.delete(runToken)
              if (activeRuns.get(runToken) === runId) reject(new Error(data.message))
            }
          } catch {}
        }
        es.onerror = () => {
          clearTimeout(timeout)
          es.close()
          if (activeStreams.get(runToken) === es) activeStreams.delete(runToken)
          if (activeRejects.get(runToken) === reject) activeRejects.delete(runToken)
          if (activeRuns.get(runToken) === runId) reject(new Error('SSE Connection failed'))
        }
      })

      // message updated inline in SSE handler
      return result
    } catch (e) {
      if (activeRuns.get(runToken) !== runId) return false
      mutateRunSession(runMode, runToken, (state) => {
        state.messages.push({ role: 'assistant', content: `\u274c 请求失败: ${e.message}`, metadata: {} })
      })
      return false
    } finally {
      if (activeRuns.get(runToken) === runId) {
        if (activeStreams.get(runToken) === es) activeStreams.delete(runToken)
        activeRejects.delete(runToken)
        setProcessing(runToken, false)
        mutateRunSession(runMode, runToken, (state) => { state.showProgress = false })
      }
    }
  }

  async function loadConversations() {
    if (!localStorage.getItem('auth_token')) { conversations.value = []; return }
    try { const r = await api.listConversations(); conversations.value = r.conversations || [] }
    catch { conversations.value = [] }
  }

  async function loadConversation(id) {
    try {
      const backgroundToken = convSessionTokens.get(id)
      if (backgroundToken && backgroundSessions.has(backgroundToken)) {
        const cached = cloneSession(backgroundSessions.get(backgroundToken))
        const targetMode = cached.messages.slice().reverse().find((m) => supportedModes.includes(m.metadata?.mode))?.metadata?.mode || currentMode.value
        if (targetMode !== currentMode.value) {
          snapshotMode()
          currentMode.value = targetMode
          localStorage.setItem('task_mode', currentMode.value)
        }
        applySessionState(cached)
        snapshotMode(targetMode)
        return { id, messages: cached.messages }
      }
      const r = await api.getConversation(id)
      const cv = r.conversation
      if (!cv) return
      const targetModeMsg = [...(cv.messages || [])].reverse().find((m) => supportedModes.includes(m.metadata?.mode))
      const targetMode = targetModeMsg?.metadata?.mode || currentMode.value
      if (targetMode !== currentMode.value) setMode(targetMode)
      const token = convSessionTokens.get(cv.id) || ++sessionSeq
      convSessionTokens.set(cv.id, token)
      currentSessionToken.value = token
      currentConvId.value = cv.id
      messages.value = []
      if (cv.messages) {
        for (const m of cv.messages) {
          messages.value.push({ role: m.role, content: m.content, metadata: m.metadata || {} })
        }
      }
      snapshotMode(targetMode)
      await loadConversations()
      return cv
    } catch { addLog('\u52a0\u8f7d\u5931\u8d25', 'error') }
  }

  return {
    messages, conversations, currentConvId, isProcessing,
    showProgress, progressSteps, logs, currentMode,
    addLog, clearChat, addMessage, sendMessage,
    loadConversations, loadConversation, setMode, cancelActiveStream,
  }
})
