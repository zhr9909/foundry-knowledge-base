// ===== State =====
const state = {
  activeSection: '',
  history: [],
  isProcessing: false,
  currentAssistantEl: null, // current assistant message being generated
};

// ===== DOM Elements =====
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

const messagesEl = document.getElementById('messages');
const welcomeEl = document.getElementById('welcome');
const loadingEl = document.getElementById('loading');
const queryInput = document.getElementById('queryInput');
const sendBtn = document.getElementById('sendBtn');
const sectionList = document.getElementById('sectionList');
const sectionIndicator = document.getElementById('sectionIndicator');
const activeSectionLabel = document.getElementById('activeSectionLabel');
const themeToggle = document.getElementById('themeToggle');
const infoToggle = document.getElementById('infoToggle');
const infoModal = document.getElementById('infoModal');
const closeModal = document.getElementById('closeModal');
const showKnowledgeBtn = document.getElementById('showKnowledgeBtn');

// ===== Theme =====
function getTheme() { return localStorage.getItem('theme') || 'light'; }
function setTheme(t) {
  document.documentElement.setAttribute('data-theme', t);
  localStorage.setItem('theme', t);
  var moonSvg = themeToggle.querySelector("svg");
  var sunSvg = themeToggle.querySelector("svg:last-child");
  if (moonSvg && sunSvg) {
    moonSvg.style.display = t === "dark" ? "none" : "";
    sunSvg.style.display = t === "dark" ? "" : "none";
  }
}
themeToggle.addEventListener('click', () => {
  setTheme(getTheme() === 'dark' ? 'light' : 'dark');
});
setTheme(getTheme());

// ===== Modal =====
infoToggle.addEventListener('click', () => infoModal.style.display = 'flex');
closeModal.addEventListener('click', () => infoModal.style.display = 'none');
infoModal.addEventListener('click', (e) => {
  if (e.target === infoModal) infoModal.style.display = 'none';
});

// ===== Load Sections =====
async function loadSections() {
  try {
    const resp = await fetch('/sections');
    const data = await resp.json();
    renderSections(data.sections);
  } catch (e) {
    console.error('Failed to load sections:', e);
  }
}

function renderSections(sections) {
  let html = '<div class="section-item active" data-section="">📄 全部章节</div>';
  for (const s of sections) {
    const active = s === state.activeSection ? ' active' : '';
    html += `<div class="section-item${active}" data-section="${escapeHtml(s)}">${escapeHtml(s)}</div>`;
  }
  sectionList.innerHTML = html;

  sectionList.querySelectorAll('.section-item').forEach(el => {
    el.addEventListener('click', () => {
      sectionList.querySelectorAll('.section-item').forEach(e => e.classList.remove('active'));
      el.classList.add('active');
      state.activeSection = el.dataset.section;
      updateSectionIndicator();
    });
  });
}

function updateSectionIndicator() {
  if (state.activeSection) {
    sectionIndicator.style.display = 'flex';
    activeSectionLabel.textContent = state.activeSection;
  } else {
    sectionIndicator.style.display = 'none';
  }
}

// ===== Clear Section =====
document.getElementById('clearSection').addEventListener('click', () => {
  state.activeSection = '';
  sectionList.querySelectorAll('.section-item').forEach(e => e.classList.remove('active'));
  sectionList.querySelector('[data-section=""]').classList.add('active');
  updateSectionIndicator();
});
document.getElementById('clearSectionBtn').addEventListener('click', () => {
  document.getElementById('clearSection').click();
});

// ===== Suggestions =====
document.querySelectorAll('.suggestion-chip').forEach(el => {
  el.addEventListener('click', () => {
    queryInput.value = el.dataset.q;
    sendMessage();
  });
});



document.querySelectorAll(".floating-bubble").forEach(function(el) {
  el.addEventListener("click", function() {
    queryInput.value = el.dataset.q;
    sendMessage();
  });
});

// ===== PDF Viewer =====
function openPDF(sourceId, pageNum) {
  const embed = document.getElementById("pdfEmbed");
  const viewer = document.getElementById("pdfViewer");
  const status = document.getElementById("pdfStatus");
  const toggle = document.getElementById("pdfToggle");
  
  if (!embed || !viewer) return;
  
  // Cache-bust + page anchor to force iframe reload & navigation
  if (pageNum) {
    embed.src = "/static/pdf-viewer.html?file=" + encodeURIComponent("/pdf/" + sourceId) + "&page=" + pageNum;
  } else {
    embed.src = "/static/pdf-viewer.html?file=" + encodeURIComponent("/pdf/" + sourceId) + "&page=1";
  }
  viewer.style.display = "flex";
  if (toggle) toggle.classList.add("active");
  if (status) status.textContent = "pg." + (pageNum || "1");
  
  // Remember position
  state.pdfState = { sourceId: sourceId, page: pageNum || 1 };
}

function closePDF() {
  const viewer = document.getElementById("pdfViewer");
  const toggle = document.getElementById("pdfToggle");
  if (viewer) viewer.style.display = "none";
  if (toggle) toggle.classList.remove("active");
}

function togglePDF() {
  const viewer = document.getElementById("pdfViewer");
  if (!viewer) return;
  if (viewer.style.display === "none" || !viewer.style.display) {
    // Open last document or default to Vol.2
    const src = state.pdfState ? state.pdfState.sourceId : 2;
    const page = state.pdfState ? state.pdfState.page : 1;
    openPDF(src, page);
  } else {
    closePDF();
  }
}

// Drag support for PDF viewer (only during drag)
let pdfDragState = null;

function onDragMove(e) {
  if (!pdfDragState) return;
  const dx = e.clientX - pdfDragState.startX;
  const dy = e.clientY - pdfDragState.startY;
  pdfDragState.viewer.style.left = (pdfDragState.left + dx) + "px";
  pdfDragState.viewer.style.top = (pdfDragState.top + dy) + "px";
  pdfDragState.viewer.style.right = "auto";
}

function onDragEnd() {
  if (pdfDragState) {
    pdfDragState = null;
    document.removeEventListener("mousemove", onDragMove);
    document.removeEventListener("mouseup", onDragEnd);
  }
}

document.addEventListener("mousedown", function(e) {
  const handle = e.target.closest(".pdf-viewer-header");
  if (!handle) return;
  const viewer = handle.closest(".pdf-viewer");
  if (!viewer) return;
  
  const rect = viewer.getBoundingClientRect();
  pdfDragState = {
    viewer: viewer,
    startX: e.clientX,
    startY: e.clientY,
    left: rect.left,
    top: rect.top
  };
  e.preventDefault();
  
  document.addEventListener("mousemove", onDragMove);
  document.addEventListener("mouseup", onDragEnd);
});

// Citation click handler - opens PDF at specific page
function openCitation(page, sourceId) {
  if (!sourceId) {
    sourceId = state.pdfState ? state.pdfState.sourceId : 2;
  }
  openPDF(sourceId, page);
}




// ===== Auth State =====
const authState = { user: null, token: localStorage.getItem('auth_token') || null, pendingEmail: null };
// If no token in localStorage but cookie exists, restore from cookie
if (!authState.token && getCookie('auth_token')) {
  authState.token = getCookie('auth_token');
  localStorage.setItem('auth_token', authState.token);
}

const urlToken = new URLSearchParams(window.location.search).get("token");
if (urlToken) {
  localStorage.setItem("auth_token", urlToken);
  authState.token = urlToken; setCookie('auth_token', urlToken, 72);
  fetch("/api/auth/me", { headers: { "Authorization": "Bearer " + urlToken } })
    .then(r => r.json()).then(d => {
      if (d.user) { authState.user = d.user; updateAuthUI(); showToast("\u767b\u5f55\u6210\u529f"); }
    }).catch(() => {});
  window.history.replaceState({}, document.title, window.location.pathname);
}


if (authState.token) {
  fetch('/api/auth/me', { headers: { 'Authorization': 'Bearer ' + authState.token } })
    .then(r => r.json()).then(d => { if (d.user) { authState.user = d.user; updateAuthUI(); }
    else { localStorage.removeItem('auth_token'); authState.token = null; updateAuthUI(); }}).catch(() => {});
}

function updateAuthUI() {
  const um = document.getElementById('userMenu'); const lb = document.getElementById('loginBtn');
  if (!um || !lb) return;
  if (authState.user) {
    um.style.display = 'flex'; lb.style.display = 'none';
    const avatar = document.getElementById('userAvatar');
    document.getElementById('userNameText').textContent = authState.user.username;
    document.getElementById('dropdownEmail').textContent = authState.user.username;
    document.getElementById('dropdownEmailSub').textContent = authState.user.email;
    avatar.textContent = authState.user.username.charAt(0).toUpperCase();
    avatar.style.background = 'var(--accent)';
    const vb = document.getElementById('verifyBadge');
    if (authState.user.email_verified) { vb.textContent = '\u5df2\u9a8c\u8bc1'; vb.className = 'verify-badge verified'; }
    else { vb.textContent = '\u672a\u9a8c\u8bc1'; vb.className = 'verify-badge'; }
  } else { um.style.display = 'none'; lb.style.display = 'inline-flex'; }
}

function showToast(msg, type) {
  const el = document.createElement('div'); el.className = 'toast' + (type === 'error' ? ' toast-error' : '');
  el.textContent = msg; document.body.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

// Cookie helpers
function setCookie(name, value, hours) {
  const d = new Date(); d.setTime(d.getTime() + hours * 60 * 60 * 1000);
  document.cookie = name + "=" + value + "; path=/; expires=" + d.toUTCString();
}
function getCookie(name) {
  const m = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
  return m ? m[2] : null;
}

// Auth Modal
const authModal = document.getElementById('authModal');
const closeAuthModal = document.getElementById('closeAuthModal');
const authOverlay = document.getElementById('authOverlay');
const tabLogin = document.getElementById('tabLogin');
const tabRegister = document.getElementById('tabRegister');
const loginBtn = document.getElementById('loginBtn');

function switchTab(tab) {
  document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.auth-view').forEach(v => v.classList.remove('active'));
  if (tab === 'login') { tabLogin.classList.add('active'); document.getElementById('loginView').classList.add('active'); }
  else { tabRegister.classList.add('active'); document.getElementById('registerView').classList.add('active'); }
  const err = document.getElementById('authError'); if (err) err.style.display = 'none';
  const err2 = document.getElementById('regError'); if (err2) err2.style.display = 'none';
}

tabLogin.addEventListener('click', () => switchTab('login'));
tabRegister.addEventListener('click', () => switchTab('register'));
loginBtn.addEventListener('click', () => { authModal.style.display = 'flex'; switchTab('login'); });
closeAuthModal.addEventListener('click', () => authModal.style.display = 'none');
authOverlay.addEventListener('click', () => authModal.style.display = 'none');
document.getElementById('backToLoginBtn').addEventListener('click', (e) => { e.preventDefault(); authModal.style.display = 'none'; });

function showAuthError(el, msg) { el.textContent = msg; el.style.display = 'block'; }

// Login submit
document.getElementById('loginForm').addEventListener('submit', async (e) => {
  e.preventDefault(); const btn = document.getElementById('loginSubmit');
  btn.disabled = true; btn.classList.add('loading');
  try {
    const resp = await fetch('/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: document.getElementById('loginEmail').value, password: document.getElementById('loginPassword').value }) });
    const data = await resp.json();
    if (!resp.ok) { showAuthError(document.getElementById('authError'), data.detail || '\u767b\u5f55\u5931\u8d25'); btn.disabled = false; btn.classList.remove('loading'); return; }
    authState.token = data.token; authState.user = data.user;
    localStorage.setItem('auth_token', data.token); setCookie('auth_token', data.token, 72); authModal.style.display = 'none'; updateAuthUI(); showToast('\u767b\u5f55\u6210\u529f');
  } catch(e) { showAuthError(document.getElementById('authError'), '\u7f51\u7edc\u9519\u8bef'); }
  btn.disabled = false; btn.classList.remove('loading');
});

// Register - Step 1
document.getElementById('registerForm').addEventListener('submit', async (e) => {
  e.preventDefault(); const btn = document.getElementById('sendCodeBtn');
  btn.disabled = true; btn.classList.add('loading');
  const email = document.getElementById('regEmail').value;
  const username = document.getElementById('regUsername').value;
  const password = document.getElementById('regPassword').value;
  try {
    const resp = await fetch('/api/auth/register', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, username, password }) });
    const data = await resp.json();
    if (!resp.ok) { showAuthError(document.getElementById('regError'), data.detail || '\u6ce8\u518c\u5931\u8d25'); btn.disabled = false; btn.classList.remove('loading'); return; }
    authState.token = data.token; authState.user = data.user; authState.pendingEmail = email;
    localStorage.setItem('auth_token', data.token); setCookie('auth_token', data.token, 72);
    document.getElementById('regStepInfo').style.display = 'none';
    document.getElementById('regStepOtp').style.display = 'block';
    document.getElementById('regOtpEmail').textContent = email;
    document.getElementById('verifyCodeBtn').disabled = true;
    document.querySelector('.otp-input').focus(); updateAuthUI();
  } catch(e) { showAuthError(document.getElementById('regError'), '\u7f51\u7edc\u9519\u8bef'); }
  btn.disabled = false; btn.classList.remove('loading');
});

// OTP inputs
document.querySelectorAll('.otp-input').forEach((inp, idx) => {
  inp.addEventListener('input', function() {
    this.value = this.value.replace(/[^0-9]/g, '').slice(0,1);
    if (this.value) { this.classList.add('filled'); if (idx < 5) document.querySelectorAll('.otp-input')[idx+1].focus(); }
    const filled = Array.from(document.querySelectorAll('.otp-input')).every(i => i.value);
    document.getElementById('verifyCodeBtn').disabled = !filled;
  });
  inp.addEventListener('keydown', function(e) {
    if (e.key === 'Backspace' && !this.value && idx > 0) document.querySelectorAll('.otp-input')[idx-1].focus();
  });
  inp.addEventListener('paste', function(e) {
    e.preventDefault(); const paste = (e.clipboardData||window.clipboardData).getData('text').replace(/[^0-9]/g,'').slice(0,6);
    document.querySelectorAll('.otp-input').forEach((i, n) => { if (n < paste.length) { i.value = paste[n]; i.classList.add('filled'); } });
    document.getElementById('verifyCodeBtn').disabled = paste.length < 6;
  });
});

document.getElementById('verifyCodeBtn').addEventListener('click', async () => {
  const btn = document.getElementById('verifyCodeBtn');
  const code = Array.from(document.querySelectorAll('.otp-input')).map(i => i.value).join('');
  btn.disabled = true; btn.classList.add('loading');
  try {
    const resp = await fetch('/api/auth/verify-code', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: authState.pendingEmail || document.getElementById('regEmail').value, code }) });
    if (!resp.ok) { const d = await resp.json(); showAuthError(document.getElementById('regError'), d.detail || '\u9a8c\u8bc1\u5931\u8d25'); btn.disabled = true; btn.classList.remove('loading'); return; }
    authModal.style.display = 'none';
    document.getElementById('regStepOtp').style.display = 'none';
    document.getElementById('regStepInfo').style.display = 'block';
    document.querySelectorAll('.otp-input').forEach(i => { i.value = ''; i.classList.remove('filled'); });
    if (authState.user) { authState.user.email_verified = true; updateAuthUI(); }
    showToast('\u9a8c\u8bc1\u6210\u529f\uff01\u6b22\u8fce\u4f7f\u7528');
  } catch(e) { showAuthError(document.getElementById('regError'), '\u7f51\u7edc\u9519\u8bef'); }
  btn.disabled = true; btn.classList.remove('loading');
});

document.getElementById('resendCodeBtn').addEventListener('click', async (e) => {
  e.preventDefault();
  try {
    const resp = await fetch('/api/auth/resend-verification', { method: 'POST', headers: { 'Authorization': 'Bearer ' + authState.token } });
    if (resp.ok) showToast('\u9a8c\u8bc1\u7801\u5df2\u91cd\u65b0\u53d1\u9001');
    else showToast('\u53d1\u9001\u5931\u8d25', 'error');
  } catch { showToast('\u7f51\u7edc\u9519\u8bef', 'error'); }
});

// User Dropdown
const userAvatarBtn = document.getElementById('userAvatarBtn');
userAvatarBtn.addEventListener('click', (e) => { e.stopPropagation(); userAvatarBtn.closest('.user-menu').classList.toggle('open'); });
document.addEventListener('click', () => { if (userAvatarBtn) userAvatarBtn.closest('.user-menu').classList.remove('open'); });

document.getElementById('logoutBtn').addEventListener('click', () => {
  authState.token = null; authState.user = null; authState.pendingEmail = null;
  localStorage.removeItem('auth_token');
  document.cookie = "auth_token=; path=/; max-age=0";
  if (userAvatarBtn) userAvatarBtn.closest('.user-menu').classList.remove('open');
  updateAuthUI(); showToast('\u5df2\u9000\u51fa\u767b\u5f55');
});

document.getElementById('resendVerifyBtn').addEventListener('click', async () => {
  if (!authState.token) return;
  try {
    const resp = await fetch('/api/auth/resend-verification', { method: 'POST', headers: { 'Authorization': 'Bearer ' + authState.token } });
    if (resp.ok) showToast('\u9a8c\u8bc1\u90ae\u4ef6\u5df2\u91cd\u65b0\u53d1\u9001');
  } catch { showToast('\u7f51\u7edc\u9519\u8bef', 'error'); }
});

document.getElementById('googleLogin').addEventListener('click', async () => { try { const r = await fetch('/api/auth/google/url'); const d = await r.json(); if (d.url) location.href = d.url; } catch(e) { showToast('Error'); } });
document.getElementById('githubLogin').addEventListener('click', () => showToast('GitHub \u767b\u5f55\u5c1a\u672a\u5b9e\u73b0'));
// ===== Log Panel =====
function createAssistantSkeleton() {
  const div = document.createElement('div');
  div.className = 'message assistant';
  div.innerHTML = `
    <div class="message-avatar">🤖</div>
    <div class="message-content">
      <details class="log-panel-inline" open>
        <summary class="log-panel-header">
          <span class="log-panel-title">📋 处理日志</span>
          <span class="log-panel-badge">0</span>
        </summary>
        <div class="log-panel-body"></div>
      </details>
      <div class="answer-block"></div>
    </div>
  `;
  document.getElementById('messages').appendChild(div);
  scrollToBottom();
  return div;
}

function fillAssistantAnswer(skeleton, answerText, citations, thinking) {
  const answerBlock = skeleton.querySelector('.answer-block');
  if (!answerBlock) return;
  
  let content = '';
  
  if (thinking) {
    content += '<details class="thinking-block" style="margin-bottom:8px;font-size:12px;color:var(--text-secondary)">'
      + '<summary style="cursor:pointer;font-weight:500">🤔 AI 思考过程</summary>'
      + '<p style="margin-top:6px;padding:8px;background:var(--bg-code);border-radius:6px">'
      + escapeHtml(thinking) + '</p></details>';
  }
  
  content += '<div class="answer-text">' + renderAnswer(answerText, citations) + '</div>';
  
  if (citations && citations.length > 0) {
    content += '<div class="citations"><div class="citations-title">📚 引用来源</div>';
    for (let i = 0; i < citations.length; i++) {
      const c = citations[i];
      const page = c.page || '?';
      const section = c.section || '';
      const preview = (c.text || '').substring(0, 200);
      const score = typeof c.score === 'number' ? c.score.toFixed(3) : '';
      content += `
        <a class="citation-card" href="#" onclick="event.preventDefault(); sessionStorage.setItem('pdfHighlight',this.querySelector('.citation-text')?.textContent||'');openCitation(${page}, ${c.source_id || 2})">
          <div class="citation-header">
            <span class="citation-page">pg.${page}</span>
            <span class="citation-score">[${score}]</span>
            <span class="citation-section" title="${escapeHtml(section)}">${escapeHtml(section)}</span>
          </div>
          <div class="citation-text">${escapeHtml(preview)}</div>
        </a>`;
    }
    content += '</div>';
  }
  
  answerBlock.innerHTML = content;
  scrollToBottom();
}

function resetLogPanel() {
  const panel = document.getElementById('logPanel');
  const body = document.getElementById('logBody');
  const badge = document.getElementById('logBadge');
  if (panel) panel.style.display = 'none';
  if (body) body.innerHTML = '';
  if (badge) badge.textContent = '0';
}

function showLogPanel() {
  const p = document.getElementById('logPanel');
  if (p) p.style.display = 'block';
}

function addLogEntry(message, level) {
  let body, badge;
  if (state.currentAssistantEl) {
    body = state.currentAssistantEl.querySelector('.log-panel-body');
    badge = state.currentAssistantEl.querySelector('.log-panel-badge');
  }
  if (!body) return;

  const now = new Date();
  const time = now.toLocaleTimeString('zh-CN', { hour12: false });
  const cl = level === 'retry' ? 'log-retry' : level === 'fallback' ? 'log-fallback' : level === 'done' ? 'log-done' : level === 'error' ? 'log-error' : '';

  let icon = '▶';
  if (message.includes('拆解') || message.includes('语义')) icon = '🔍';
  else if (message.includes('检索')) icon = '📡';
  else if (message.includes('精选') || message.includes('上下文')) icon = '📚';
  else if (message.includes('提示词') || message.includes('生成')) icon = '🤖';
  else if (message.includes('质量') || message.includes('检查')) icon = '✅';
  else if (message.includes('降级') || message.includes('兜底')) icon = '⚠️';
  else if (message.includes('偏低') || message.includes('新一轮')) icon = '🔄';
  else if (message.includes('通过')) icon = '✅';
  else if (message.includes('完成') || message.includes('生成完成')) icon = '✨';
  else if (message.includes('失败')) icon = '❌';

  const entry = document.createElement('div');
  entry.className = 'log-entry' + (cl ? ' ' + cl : '');
  entry.innerHTML = '<span class="log-time">[' + time + ']</span><span class="log-icon">' + icon + '</span><span class="log-msg">' + escapeHtml(message) + '</span>';
  body.appendChild(entry);
  body.scrollTop = body.scrollHeight;

  const count = body.children.length;
  if (badge) badge.textContent = count;
}

// ===== Send Message =====

// ===== Progress Steps =====
function resetProgressSteps() {
  const container = document.getElementById('progressSteps');
  container.style.display = 'none';
  document.querySelectorAll('.step').forEach(s => {
    s.classList.remove('active', 'done');
    s.querySelector('.step-status').textContent = '';
  });
}

function showProgressSteps() {
  document.getElementById('progressSteps').style.display = 'flex';
}

function activateStep(stepId) {
  const step = document.querySelector(`.step[data-step="${stepId}"]`);
  if (step) step.classList.add('active');
}

function completeStep(stepId, statusText) {
  const step = document.querySelector(`.step[data-step="${stepId}"]`);
  if (step) {
    step.classList.remove('active');
    step.classList.add('done');
    const status = step.querySelector('.step-status');
    if (statusText) status.textContent = statusText;
  }
}

function advanceStep(fromStep, toStep, statusText) {
  completeStep(fromStep, statusText);
  if (toStep) activateStep(toStep);
}

// ===== Send Message (SSE with POST fallback) =====
queryInput.addEventListener('input', () => {
  sendBtn.disabled = !queryInput.value.trim() || state.isProcessing;
  autoResize(queryInput);
});
queryInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});
sendBtn.addEventListener('click', sendMessage);

async function sendMessage() {
  const q = queryInput.value.trim();
  if (!q || state.isProcessing) return;
  queryInput.value = '';
  sendBtn.disabled = true;
  state.isProcessing = true;

  // Hide welcome, show progress
  welcomeEl.style.display = 'none';
  resetProgressSteps();
  showProgressSteps();
  activateStep('rewrite');
  
  // Create assistant skeleton with log panel
  state.currentAssistantEl = createAssistantSkeleton();
  addLogEntry('开始处理查询...');
  addLogEntry('原始查询：' + q);

  // Add user message
  addMessage('user', q);

  // Try SSE first
  const sseSuccess = await sendMessageSSE(q);
  
  if (!sseSuccess) {
    // Fallback to POST
    console.log('SSE failed, falling back to POST');
    await sendMessagePOST(q);
  }

  state.currentAssistantEl = null;
  state.isProcessing = false;
  sendBtn.disabled = !queryInput.value.trim();
  loadingEl.style.display = 'none';
}

function sendMessageSSE(query) {
  return new Promise((resolve) => {
    const params = new URLSearchParams({ query });
    if (state.activeSection) params.set('section', state.activeSection);
    if (state.history.length > 0) params.set('history', JSON.stringify(state.history.slice(-6)));
    
    let resolved = false;
    let hasData = false;
    let es;
    
    try {
      es = new EventSource(`/chat/stream?${params}`);
    } catch (e) {
      return resolve(false);
    }
    
    const timeout = setTimeout(() => {
      if (!resolved) {
        resolved = true;
        es.close();
        resolve(false);
      }
    }, 30000);

    es.onmessage = (event) => {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch {
        return;
      }

      hasData = true;

      // --- Log events ---
      if (data.type === 'log') {
        addLogEntry(data.message, data.level || 'info');
      }
      // --- Progress events ---
      else if (data.step === 'rewritten') {
        const count = data.queries ? data.queries.length : 0;
        advanceStep('rewrite', 'search', `→ ${count} 条语句`);
      } 
      else if (data.step === 'searched') {
        advanceStep('search', 'context', `→ ${data.count} 个候选`);
      }
      else if (data.step === 'context_ready') {
        advanceStep('context', 'generate', `→ 精选 ${data.count} 条`);
      }
      else if (data.step === 'checked') {
        completeStep('generate');
        if (data.score >= 7) {
          completeStep('check', `✅ ${data.score}/10`);
        } else {
          // Will retry - show retry status
          const checkStep = document.querySelector('.step[data-step="check"]');
          if (checkStep) {
            checkStep.classList.add('active');
            checkStep.querySelector('.step-status').textContent = `${data.score}/10 重试中...`;
          }
        }
      }
      // --- Result event ---
      else if (data.type === 'result') {
        clearTimeout(timeout);
        es.close();
        if (!resolved) {
          resolved = true;
          const result = data.data;
          // Ensure check step is marked done
          completeStep('check', `✅ 完成`);
          if (state.currentAssistantEl) {
            fillAssistantAnswer(state.currentAssistantEl, result.answer || '无回答', result.citations || [], result.thinking || '');
          } else {
            addAssistantMessage(
              result.answer || '无回答',
              result.citations || [],
              result.thinking || ''
            );
          }
          // Update history
          state.history.push(
            { role: 'user', content: query },
            { role: 'assistant', content: result.answer || '' }
          );
          if (state.history.length > 20) state.history = state.history.slice(-20);
          resolve(true);
        }
      }
      // --- Error event ---
      else if (data.type === 'error') {
        clearTimeout(timeout);
        es.close();
        if (!resolved) {
          resolved = true;
          addAssistantMessage(`❌ 生成回答失败: ${data.message}`, []);
          resolve(false);
        }
      }
    };

    es.onerror = () => {
      clearTimeout(timeout);
      es.close();
      if (!resolved) {
        resolved = true;
        resolve(false); // fallback to POST
      }
    };
  });
}

// ===== POST Fallback (original logic) =====
async function sendMessagePOST(query) {
  loadingEl.style.display = 'flex';
  loadingEl.querySelector('span').textContent = '正在检索知识库...';

  try {
    // Step 1: Search
    const params = new URLSearchParams({ query, top_k: 6 });
    if (state.activeSection) params.set('section', state.activeSection);
    const searchResp = await fetch(`/search?${params}`);
    const searchData = await searchResp.json();

    loadingEl.querySelector('span').textContent = 'AI 正在生成回答...';

    // Step 2: Generate
    const chatResp = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        search_results: searchData.results,
        history: state.history.slice(-6),
        section: state.activeSection || null,
      }),
    });

    if (!chatResp.ok) {
      const err = await chatResp.text();
      addAssistantMessage(`❌ 生成回答失败: ${err}`, []);
      return;
    }

    const chatData = await chatResp.json();
    if (state.currentAssistantEl) {
      fillAssistantAnswer(state.currentAssistantEl, chatData.answer || '', chatData.search_results || [], chatData.thinking || '');
    } else {
      addAssistantMessage(chatData.answer, chatData.search_results || [], chatData.thinking);
    }

    state.history.push(
      { role: 'user', content: query },
      { role: 'assistant', content: chatData.answer }
    );
    if (state.history.length > 20) state.history = state.history.slice(-20);

  } catch (e) {
    addAssistantMessage(`❌ 请求失败: ${e.message}`, []);
  }
}

// ===== Message Rendering =====
function addMessage(role, text) {
  const div = document.createElement('div');
  div.className = `message ${role}`;
  div.innerHTML = `
    <div class="message-avatar">${role === 'user' ? '👤' : '🤖'}</div>
    <div class="message-content"><p>${escapeHtml(text).replace(/\n/g, '<br>')}</p></div>
  `;
  messagesEl.appendChild(div);
  scrollToBottom();
}

function addAssistantMessage(text, citations, thinking) {
  const div = document.createElement('div');
  div.className = 'message assistant';
  let content = `<div class="message-avatar">🤖</div><div class="message-content">`;

  if (thinking) {
    content += `<details class="thinking-block" style="margin-bottom:8px;font-size:12px;color:var(--text-secondary)">
      <summary style="cursor:pointer;font-weight:500">🤔 AI 思考过程</summary>
      <p style="margin-top:6px;padding:8px;background:var(--bg-code);border-radius:6px">${escapeHtml(thinking)}</p>
    </details>`;
  }

  // Process citations inline: [1], [2] etc become clickable
  content += `<div class="answer-text">${renderAnswer(text, citations)}</div>`;

  if (citations && citations.length > 0) {
    content += '<div class="citations"><div class="citations-title">📚 引用来源</div>';
    for (let i = 0; i < citations.length; i++) {
      const c = citations[i];
      const page = c.page || '?';
      const section = c.section || '';
      const preview = (c.text || '').substring(0, 200);
      const score = typeof c.score === 'number' ? c.score.toFixed(3) : '';
      content += `
        <a class="citation-card" href="#" onclick="event.preventDefault(); sessionStorage.setItem('pdfHighlight',this.querySelector('.citation-text')?.textContent||'');openCitation(${page}, ${c.source_id || 2})">
          <div class="citation-header">
            <span class="citation-page">pg.${page}</span>
            <span class="citation-score">[${score}]</span>
            <span class="citation-section" title="${escapeHtml(section)}">${escapeHtml(section)}</span>
          </div>
          <div class="citation-text">${escapeHtml(preview)}</div>
        </a>`;
    }
    content += '</div>';
  }

  content += '</div>';
  div.innerHTML = content;
  messagesEl.appendChild(div);
  scrollToBottom();
}

function renderAnswer(text, citations) {
  if (!text) return "";
  // Extract pipe tables before HTML escaping
  const tblBlocks = [];
  const noTables = text.replace(/((?:\|.*\|(?:\r?\n|$)){2,})/g, function(m) {
    tblBlocks.push(renderTable(m));
    return "\x00T" + (tblBlocks.length - 1) + "\x00";
  });
  // Escape HTML (table placeholders survive since \x00 is not in the escape list)
  let result = escapeHtml(noTables);
  // Process basic markdown formatting (safe after escapeHtml)
  result = result.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  result = result.replace(/`(.*?)`/g, "<code>$1</code>");
  result = result.replace(/^### (.*?)$/gm, "<h4>$1</h4>");
  result = result.replace(/^## (.*?)$/gm, "<h3>$1</h3>");
  // Restore table HTML
  result = result.replace(/\x00T(\d+)\x00/g, function(_, id) { return tblBlocks[parseInt(id)]; });
  // Replace citations
  if (citations) {
    for (let i = 0; i < citations.length; i++) {
      const page = citations[i].page || "?";
      result = result.replace("[" + (i + 1) + "]", '<sup onclick="openCitation(' + page + ')" style="color:var(--accent);cursor:pointer" title="pg.' + page + '">[' + (i + 1) + ']</sup>');
    }
  }
  return result.replace(/\n/g, "<br>");
}

function renderTable(t) {
  var rows = t.trim().split("\n").filter(function(x) { return x.trim().startsWith("|"); });
  if (rows.length < 1) return escapeHtml(t);
  var hasSep = rows.some(function(x) { return x.indexOf("---") >= 0; });
  var html = '<div style="overflow-x:auto;margin:8px 0"><table style="border-collapse:collapse;width:100%;font-size:13px">';
  if (hasSep && rows.length >= 2) {
    // Header row
    html += "<thead><tr>";
    rows[0].split("|").filter(function(c) { return c.trim(); }).forEach(function(c) {
      html += '<th style="background:var(--accent);color:white;padding:4px 8px;border:1px solid var(--border);text-align:left;white-space:nowrap">' + escapeHtml(c.trim()) + "</th>";
    });
    html += "</tr></thead><tbody>";
    for (var i = 2; i < rows.length; i++) {
      var cells = rows[i].split("|").filter(function(c) { return c.trim(); });
      if (!cells.length) continue;
      html += "<tr" + (i % 2 === 0 ? ' style="background:var(--bg)"' : "") + ">";
      cells.forEach(function(c) { html += '<td style="padding:4px 8px;border:1px solid var(--border)">' + escapeHtml(c.trim()) + "</td>"; });
      html += "</tr>";
    }
    html += "</tbody></table></div>";
  } else {
    html += "<tbody>";
    for (var i = 0; i < rows.length; i++) {
      var cells = rows[i].split("|").filter(function(c) { return c.trim(); });
      if (!cells.length) continue;
      html += "<tr>";
      cells.forEach(function(c) { html += '<td style="padding:4px 8px;border:1px solid var(--border)">' + escapeHtml(c.trim()) + "</td>"; });
      html += "</tr>";
    }
    html += "</tbody></table></div>";
  }
  return html;
}


// ===== Utility =====
function escapeHtml(s) {
  if (!s) return '';
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
          .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

function scrollToBottom() {
  setTimeout(() => {
    const ca = document.querySelector('.chat-area');
    ca.scrollTop = ca.scrollHeight;
  }, 50);
}

// ===== Knowledge Base Overview =====
showKnowledgeBtn.addEventListener('click', () => {
  infoModal.style.display = 'flex';
});

// ===== Init =====
// loadSections(); // disabled - sections not ready

// PDF viewer toggle
const pdfToggle = document.getElementById('pdfToggle');
const pdfClose = document.getElementById('pdfCloseBtn');
if (pdfToggle) pdfToggle.addEventListener('click', togglePDF);
if (pdfClose) pdfClose.addEventListener('click', closePDF);

// Init PDF state
state.pdfState = null;

// Also show chunk count from health endpoint (disabled)
// fetch('/health').then(r => r.json()).then(d => {
//   const el = document.getElementById('chunkCount');
//   if (d.chunks) el.textContent = `${d.chunks.toLocaleString()} chunks`;
// }).catch(() => {});

