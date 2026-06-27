// ===== State =====
const state = {
  activeSection: '',
  history: [],
  isProcessing: false,
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

// ===== Send Message =====
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

  // Hide welcome
  welcomeEl.style.display = 'none';

  // Add user message
  addMessage('user', q);

  // Show loading
  loadingEl.style.display = 'flex';
  loadingEl.querySelector('span').textContent = '正在检索知识库...';

  try {
    // Step 1: Search
    const params = new URLSearchParams({ query: q, top_k: 6 });
    if (state.activeSection) params.set('section', state.activeSection);
    const searchResp = await fetch(`/search?${params}`);
    const searchData = await searchResp.json();

    loadingEl.querySelector('span').textContent = 'AI 正在生成回答...';

    // Step 2: Generate answer
    const chatResp = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: q,
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
    addAssistantMessage(chatData.answer, chatData.search_results || [], chatData.thinking);

    // Update history
    state.history.push(
      { role: 'user', content: q },
      { role: 'assistant', content: chatData.answer }
    );
    if (state.history.length > 20) state.history = state.history.slice(-20);

  } catch (e) {
    addAssistantMessage(`❌ 请求失败: ${e.message}`, []);
  } finally {
    loadingEl.style.display = 'none';
    state.isProcessing = false;
    sendBtn.disabled = !queryInput.value.trim();
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
        <a class="citation-card" href="#" onclick="event.preventDefault(); openCitation(${page})">
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

function openCitation(page) {
  alert(`查看第 ${page} 页原文（需 PDF 查看器）`);
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
loadSections();

// Also show chunk count from health endpoint
fetch('/health').then(r => r.json()).then(d => {
  const el = document.getElementById('chunkCount');
  if (d.chunks) el.textContent = `${d.chunks.toLocaleString()} chunks`;
}).catch(() => {});

