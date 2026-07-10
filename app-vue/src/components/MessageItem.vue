<template>
  <article class="message" :class="msg.role">
    <div class="message-avatar">{{ msg.role === 'user' ? 'YOU' : 'AI' }}</div>
    <div class="message-content">
      <LogPanel v-if="msg.role === 'assistant' && msg.metadata.logs?.length" :logs="msg.metadata.logs" />
      <section v-if="showRetrievalPanel" class="retrieval-panel">
        <div class="retrieval-head">
          <div>
            <div class="retrieval-title">检索解释</div>
            <div class="retrieval-subtitle">{{ retrievalModeText }}</div>
          </div>
          <button class="correction-toggle" type="button" @click="correctionOpen = !correctionOpen">{{ correctionOpen ? '收起' : '纠正上下文' }}</button>
        </div>
        <div class="retrieval-grid">
          <div class="retrieval-item">
            <span>当前实体</span>
            <strong>{{ entityText }}</strong>
          </div>
          <div class="retrieval-item">
            <span>过滤规则</span>
            <strong>{{ retrieval.filter_rule || '全部' }}</strong>
          </div>
          <div class="retrieval-item">
            <span>候选 / 精选</span>
            <strong>{{ countText }}</strong>
          </div>
        </div>
        <div v-if="retrieval.resolved_query && retrieval.resolved_query !== retrieval.original_query" class="resolved-query">
          <span>上下文解析</span>
          <strong>{{ retrieval.original_query }}</strong>
          <em>→</em>
          <strong>{{ retrieval.resolved_query }}</strong>
        </div>
        <details v-if="searchQueries.length" class="query-details">
          <summary>查看检索语句</summary>
          <ol>
            <li v-for="(query, index) in searchQueries" :key="index">{{ query }}</li>
          </ol>
        </details>
        <form v-if="correctionOpen" class="correction-form" @submit.prevent="submitCorrection">
          <input v-model.trim="correctionEntity" type="text" placeholder="输入正确实体，例如：钻石、铜合金、不锈钢" />
          <button type="submit" :disabled="!correctionEntity">按此实体重问</button>
        </form>
      </section>
      <div v-if="msg.role === 'assistant' && msg.metadata.thinking" class="thinking-block"><details><summary>{{ thinkingTitle }}</summary><p>{{ msg.metadata.thinking }}</p></details></div>
      <div class="answer-text" v-html="renderedAnswer"></div>
      <KnowledgeGraph v-if="msg.role === 'assistant'" :graph="knowledgeGraph" />
      <div v-if="msg.role === 'assistant' && msg.metadata.citations && msg.metadata.citations.length" class="citations">
        <div class="citations-title">{{ citationTitle }}</div>
        <a
          v-for="(c, i) in msg.metadata.citations"
          :key="i"
          class="citation-card"
          :href="pdfViewerUrl(c)"
          target="_blank"
          rel="noopener"
          @click="rememberCitation(c)"
        ><div class="citation-header"><span class="citation-page">pg.{{ c.page || '?' }}</span><span class="citation-score">{{ (c.score || 0).toFixed(3) }}</span><span class="citation-section">{{ c.section || '' }}</span></div><div class="citation-text">{{ (c.text || '').substring(0, 200) }}</div></a>
      </div>
    </div>
  </article>
</template>
<script setup>
import { computed, ref } from 'vue'
import LogPanel from './LogPanel.vue'
import KnowledgeGraph from './KnowledgeGraph.vue'
import { buildKnowledgeGraph } from '../utils/knowledgeGraph.js'
const props = defineProps({ msg: Object, logs: { type: Array, default: () => [] } })
const emit = defineEmits(['correct-context'])
const thinkingTitle = 'AI \u601d\u8003\u8fc7\u7a0b'
const citationTitle = '\u5f15\u7528\u6765\u6e90'
const correctionOpen = ref(false)
const correctionEntity = ref('')
const retrieval = computed(() => props.msg.metadata?.retrieval || null)
const showRetrievalPanel = computed(() => props.msg.role === 'assistant' && retrieval.value)
const searchQueries = computed(() => Array.isArray(retrieval.value?.search_queries) ? retrieval.value.search_queries : [])
const entityText = computed(() => {
  const entities = retrieval.value?.core_entity
  return Array.isArray(entities) && entities.length ? entities.join('、') : '未限定'
})
const countText = computed(() => {
  const candidate = retrieval.value?.candidate_count ?? '-'
  const selected = retrieval.value?.selected_count ?? '-'
  return `${candidate} / ${selected}`
})
const retrievalModeText = computed(() => retrieval.value?.used_history ? '本轮使用历史上下文补全了省略实体' : '本轮优先使用当前问题中的显式实体')
const knowledgeGraph = computed(() => {
  if (props.msg.role !== 'assistant' || !props.msg.content) return null
  return props.msg.metadata.graph || buildKnowledgeGraph(
    props.msg.metadata.question || '',
    props.msg.content,
    props.msg.metadata.citations || [],
  )
})
const renderedAnswer = computed(() => {
  function escapeHtml(s) { return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;') }
  function renderTable(md) {
    const rows = md.trim().split('\n').filter(line => line.trim().startsWith('|'))
    if (!rows.length) return escapeHtml(md)
    const hasSep = rows.length > 1 && rows[1].includes('---')
    let html = '<table>'
    if (hasSep) {
      html += '<thead><tr>' + rows[0].split('|').filter(c => c.trim()).map(c => '<th>' + escapeHtml(c.trim()) + '</th>').join('') + '</tr></thead><tbody>'
      for (let i = 2; i < rows.length; i++) {
        const cells = rows[i].split('|').filter(c => c.trim())
        if (cells.length) html += '<tr>' + cells.map(c => '<td>' + escapeHtml(c.trim()) + '</td>').join('') + '</tr>'
      }
      html += '</tbody>'
    } else {
      html += '<tbody>' + rows.map(row => '<tr>' + row.split('|').filter(c => c.trim()).map(c => '<td>' + escapeHtml(c.trim()) + '</td>').join('') + '</tr>').join('') + '</tbody>'
    }
    return html + '</table>'
  }
  let text = props.msg.content || ''
  if (props.msg.role === 'user') return escapeHtml(text)
  const citations = props.msg.metadata.citations || []
  const tblBlocks = []
  let result = text.replace(/((?:\|.*\|(?:\r?\n|$)){2,})/g, function(m) { tblBlocks.push(renderTable(m)); return '\x00T' + (tblBlocks.length - 1) + '\x00' })
  result = escapeHtml(result)
  result = result.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
  result = result.replace(/`(.*?)`/g, '<code>$1</code>')
  result = result.replace(/^###\s+(.*?)$/gm, '<h4>$1</h4>')
  result = result.replace(/^##\s+(.*?)$/gm, '<h3>$1</h3>')
  result = result.replace(/\x00T(\d+)\x00/g, function(_, id) { return tblBlocks[parseInt(id)] })
  for (let i = 0; i < citations.length; i++) {
    const page = citations[i].page || '?'
    const sourceId = citations[i].source_id || 2
    const url = pdfViewerUrl({ page, source_id: sourceId })
    result = result.replace('[' + (i + 1) + ']', '<a class="citation-ref" style="color:var(--info);cursor:pointer;text-decoration:none" href="' + url + '" target="_blank" rel="noopener">[' + (i + 1) + ']</a>')
  }
  result = result.replace(/\n{2,}/g, '</p><p>')
  result = result.replace(/\n/g, '<br>')
  if (!result.startsWith('<')) result = '<p>' + result + '</p>'
  return result
})
function submitCorrection() {
  const entity = correctionEntity.value
  if (!entity) return
  const question = props.msg.metadata?.question || retrieval.value?.original_query || ''
  emit('correct-context', `关于${entity}，${question}`)
  correctionEntity.value = ''
  correctionOpen.value = false
}
function pdfViewerUrl(c) {
  const page = c?.page || 1
  const sourceId = c?.source_id || c?.sourceId || 2
  return `/static/pdf-viewer.html?file=${encodeURIComponent(`/pdf/${sourceId}`)}&page=${encodeURIComponent(page)}`
}

function rememberCitation(c) {
  try {
    sessionStorage.setItem('pdfHighlight', c?.text || '')
  } catch {}
}
</script>
<style scoped>
.message { display: grid; grid-template-columns: 36px minmax(0, 1fr); gap: 12px; align-items: start; }
.message.user { grid-template-columns: minmax(0, 1fr) 36px; }
.message.user .message-avatar { grid-column: 2; grid-row: 1; background: var(--bg-user); color: #fff; }
.message.user .message-content { grid-column: 1; grid-row: 1; justify-self: end; background: var(--bg-user); color: #fff; border-color: transparent; max-width: min(640px, 82%); }
.message.assistant .message-content { background: var(--bg-assistant); border: 1px solid var(--border-light); max-width: 100%; }
.message-avatar { width: 36px; height: 36px; border-radius: 10px; display: grid; place-items: center; background: var(--accent-soft); color: var(--accent-strong); font-size: 11px; font-weight: 800; letter-spacing: 0; border: 1px solid var(--border-light); }
.message-content { border-radius: var(--radius-lg); padding: 14px 16px; box-shadow: var(--shadow-control); min-width: 0; }
.answer-text { color: inherit; font-size: 14px; line-height: 1.78; white-space: pre-wrap; }
.message.user .answer-text { text-align: left; }
.message.user :deep(code) { background: rgba(255,255,255,.14); border-color: rgba(255,255,255,.18); color: #fff; }
.retrieval-panel { margin-bottom: 12px; padding: 11px; border: 1px solid color-mix(in srgb, var(--accent) 22%, var(--border-light)); border-radius: var(--radius-md); background: color-mix(in srgb, var(--accent-soft) 36%, var(--bg-surface)); }
.retrieval-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.retrieval-title { color: var(--text-primary); font-size: 13px; font-weight: 750; line-height: 1.35; }
.retrieval-subtitle { margin-top: 2px; color: var(--text-muted); font-size: 12px; line-height: 1.45; }
.correction-toggle { flex: 0 0 auto; border: 1px solid var(--border-light); border-radius: var(--radius-sm); background: var(--bg-surface); color: var(--accent-strong); padding: 5px 8px; font-size: 12px; font-weight: 650; cursor: pointer; }
.correction-toggle:hover { border-color: var(--accent); background: var(--accent-soft); }
.retrieval-grid { margin-top: 10px; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.retrieval-item { min-width: 0; padding: 8px; border: 1px solid var(--border-light); border-radius: var(--radius-sm); background: var(--bg-surface); }
.retrieval-item span, .resolved-query span { display: block; margin-bottom: 3px; color: var(--text-muted); font-size: 11px; font-weight: 650; }
.retrieval-item strong { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-primary); font-size: 12px; font-weight: 720; }
.resolved-query { margin-top: 8px; color: var(--text-secondary); font-size: 12px; line-height: 1.55; }
.resolved-query strong { color: var(--text-primary); font-weight: 680; }
.resolved-query em { margin: 0 6px; color: var(--accent-strong); font-style: normal; font-weight: 800; }
.query-details { margin-top: 8px; color: var(--text-secondary); font-size: 12px; }
.query-details summary { cursor: pointer; font-weight: 650; }
.query-details ol { margin-top: 6px; padding-left: 18px; font-family: var(--font-mono); line-height: 1.6; word-break: break-word; }
.correction-form { margin-top: 9px; display: flex; gap: 8px; }
.correction-form input { flex: 1; min-width: 0; border: 1px solid var(--border-light); border-radius: var(--radius-sm); background: var(--bg-surface); color: var(--text-primary); padding: 7px 9px; font-size: 12px; }
.correction-form button { border: 0; border-radius: var(--radius-sm); background: var(--accent); color: white; padding: 0 10px; font-size: 12px; font-weight: 700; cursor: pointer; }
.correction-form button:disabled { opacity: .45; cursor: not-allowed; }
.thinking-block { margin-bottom: 12px; font-size: 12px; color: var(--text-secondary); }
.thinking-block summary { cursor: pointer; font-weight: 650; }
.thinking-block p { margin-top: 8px; padding: 10px; background: var(--bg-surface-2); border: 1px solid var(--border-light); border-radius: var(--radius-md); white-space: pre-wrap; }
.citations { margin-top: 14px; display: flex; flex-direction: column; gap: 7px; }
.citations-title { color: var(--text-muted); font-size: 12px; font-weight: 700; }
.citation-card { display: block; padding: 10px 11px; border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--bg-surface-2); color: inherit; text-decoration: none; transition: border-color .16s ease, background .16s ease; }
.citation-card:hover { border-color: var(--accent); background: var(--accent-soft); }
.citation-header { display: flex; align-items: center; gap: 8px; color: var(--text-muted); font-family: var(--font-mono); font-size: 11px; margin-bottom: 4px; }
.citation-page { color: var(--accent-strong); font-weight: 800; }
.citation-section { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.citation-text { color: var(--text-secondary); font-size: 12px; line-height: 1.55; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
@media (max-width: 820px) { .message.user .message-content { max-width: 92%; } .retrieval-grid { grid-template-columns: 1fr; } .retrieval-head, .correction-form { flex-direction: column; } .correction-toggle, .correction-form button { width: 100%; min-height: 34px; } }
</style>
