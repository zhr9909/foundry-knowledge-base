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
  themeToggle.textContent = t === 'dark' ? '☀️' : '🌙';
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
  if (!citations || citations.length === 0) return escapeHtml(text).replace(/\n/g, '<br>');
  // Replace [N] with citation reference
  let result = escapeHtml(text);
  for (let i = 0; i < citations.length; i++) {
    const page = citations[i].page || '?';
    result = result.replace(`[${i + 1}]`, `<sup style="color:var(--accent);cursor:pointer" title="pg.${page}">[${i + 1}]</sup>`);
  }
  return result.replace(/\n/g, '<br>');
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

