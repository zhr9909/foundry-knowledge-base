const BASE = ''

async function request(url, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  const token = localStorage.getItem('auth_token')
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(BASE + url, { ...options, headers })
  if (!res.ok) { const err = await res.text(); throw new Error(err || `HTTP ${res.status}`) }
  return res.json()
}

export const api = {
  // Auth
  register: (data) => request('/api/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  login: (data) => request('/api/auth/login', { method: 'POST', body: JSON.stringify(data) }),
  verifyCode: (data) => request('/api/auth/verify-code', { method: 'POST', body: JSON.stringify(data) }),
  getMe: () => request('/api/auth/me'),
  getGoogleUrl: () => request('/api/auth/google/url'),

  // Conversations
  listConversations: () => request('/api/conversations'),
  createConversation: (data = {}) => request('/api/conversations', { method: 'POST', body: JSON.stringify(data) }),
  getConversation: (id) => request(`/api/conversations/${id}`),
  updateConversation: (id, data) => request(`/api/conversations/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteConversation: (id) => request(`/api/conversations/${id}`, { method: 'DELETE' }),
  saveMessage: (id, data) => request(`/api/conversations/${id}/messages`, { method: 'POST', body: JSON.stringify(data) }),

  // Project Workspace
  listProjects: () => request('/api/projects'),
  createProject: (data) => request('/api/projects', { method: 'POST', body: JSON.stringify(data) }),
  getProject: (id) => request(`/api/projects/${id}`),
  updateProject: (id, data) => request(`/api/projects/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  saveProjectArtifact: (id, data) => request(`/api/projects/${id}/artifacts`, { method: 'POST', body: JSON.stringify(data) }),
  generateProjectBrief: (id) => request(`/api/projects/${id}/brief`, { method: 'POST' }),

  // Search & Chat
  search: (query, top_k = 10, section) => {
    const params = new URLSearchParams({ query, top_k })
    if (section) params.set('section', section)
    return request(`/search?${params}`)
  },
  chat: (data) => request('/chat', { method: 'POST', body: JSON.stringify(data) }),

  // Health
  health: () => request('/health'),
}
