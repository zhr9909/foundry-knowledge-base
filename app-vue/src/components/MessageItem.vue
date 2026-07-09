<template>
  <div class="message" :class="msg.role">
    <div class="message-avatar">{{ msg.role === 'user' ? '👤' : '🤖' }}</div>
    <div class="message-content">
      <LogPanel v-if="msg.role === 'assistant' && msg.metadata.logs?.length" :logs="msg.metadata.logs" />
      <div v-if="msg.role === 'assistant' && msg.metadata.thinking" class="thinking-block">
        <details>
          <summary>馃 AI ????</summary>
          <p>{{ msg.metadata.thinking }}</p>
        </details>
      </div>
      <div class="answer-text" v-html="renderedAnswer"></div>
      <div v-if="msg.role === 'assistant' && msg.metadata.citations && msg.metadata.citations.length" class="citations">
        <div class="citations-title">馃搸 ????</div>
        <a v-for="(c, i) in msg.metadata.citations" :key="i" class="citation-card" href="#" @click.prevent="openCitation(c)">
          <div class="citation-header">
            <span class="citation-page">pg.{{ c.page || '?' }}</span>
            <span class="citation-score">[{{ (c.score || 0).toFixed(3) }}]</span>
            <span class="citation-section">{{ c.section || '' }}</span>
          </div>
          <div class="citation-text">{{ (c.text || '').substring(0, 200) }}</div>
        </a>
      </div>
    </div>
  </div>
</template>
<script setup>
import { computed } from 'vue'
import LogPanel from './LogPanel.vue'
const props = defineProps({ msg: Object, logs: { type: Array, default: () => [] } })
const renderedAnswer = computed(() => {
  function escapeHtml(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;") }
  function renderTable(md) {
    const lines = md.trim().split("\n")
    let html = "<table><thead><tr>"
    for (const h of lines[0].split("|").filter(function(c) { return c.trim() })) html += "<th>" + h.trim() + "</th>"
    html += "</tr></thead><tbody>"
    for (let i = 2; i < lines.length; i++) {
      const cells = lines[i].split("|").filter(function(c) { return c.trim() })
      if (cells.length) {
        html += "<tr>"
        for (const c of cells) html += "<td>" + c.trim() + "</td>"
        html += "</tr>"
      }
    }
    html += "</tbody></table>"
    return html
  }
  
  let text = props.msg.content || ""
  if (props.msg.role === "user") return text
  const citations = props.msg.metadata.citations || []
  
  // Extract tables before HTML escaping
  const tblBlocks = []
  let result = text.replace(/((?:\|.*\|(?:\r?\n|$)){2,})/g, function(m) {
    tblBlocks.push(renderTable(m))
    return "\x00T" + (tblBlocks.length - 1) + "\x00"
  })
  
  // Escape HTML
  result = escapeHtml(result)
  
  // Bold
  result = result.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
  // Inline code
  result = result.replace(/\`(.*?)\`/g, "<code>$1</code>")
  // Headers
  result = result.replace(/^###\s+(.*?)$/gm, "<h4>$1</h4>")
  result = result.replace(/^##\s+(.*?)$/gm, "<h3>$1</h3>")
  
  // Restore tables
  result = result.replace(/\x00T(\d+)\x00/g, function(_, id) { return tblBlocks[parseInt(id)] })
  
  // Citations
  for (let i = 0; i < citations.length; i++) {
    const page = citations[i].page || "?"
    result = result.replace("[" + (i + 1) + "]", "<sup class=\"citation-ref\" style=\"color:#2563eb;cursor:pointer\" onclick=\"event.preventDefault(); window.open(\'/static/pdf-viewer.html?page=" + page + "\')\">[" + (i + 1) + "]</sup>")
  }
  
  // Line breaks to paragraphs
  result = result.replace(/\n{2,}/g, "</p><p>")
  result = result.replace(/\n/g, "<br>")
  if (!result.startsWith("<")) result = "<p>" + result + "</p>"
  
  return result
})

function openCitation(c) {
  const page = c.page || 1
  window.open('/static/pdf-viewer.html?page=' + page, '_blank')
}
</script>
<style scoped>
.message { display: flex; gap: 12px; padding: 16px 0; }
.message.user { flex-direction: row-reverse; }
.message-avatar { width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 16px; flex-shrink: 0; background: var(--bg-sub); }
.message.user .message-avatar { background: var(--text-primary); }
.message-content { max-width: 640px; flex: 1; }
.message.user .message-content { text-align: right; }
.answer-text { line-height: 1.7; font-size: 14px; white-space: pre-wrap; }
.citations { margin-top: 12px; }
.citations-title { font-size: 12px; color: var(--text-muted); margin-bottom: 6px; font-weight: 500; }
.citation-card { display: block; padding: 8px 10px; margin-bottom: 4px; border: 1px solid var(--border-light); border-radius: var(--radius-sm); text-decoration: none; color: inherit; transition: border-color .15s; }
.citation-card:hover { border-color: var(--border-focus); }
.citation-header { display: flex; align-items: center; gap: 8px; font-size: 11px; color: var(--text-muted); margin-bottom: 2px; }
.citation-page { font-weight: 500; color: var(--text-primary); }
.citation-text { font-size: 12px; color: var(--text-secondary); line-height: 1.4; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.thinking-block details { margin: 6px 0; font-size: 12px; color: var(--text-secondary); }
.thinking-block summary { cursor: pointer; font-weight: 500; }
.thinking-block p { margin-top: 6px; padding: 8px; background: var(--bg-code); border-radius: 6px; white-space: pre-wrap; }
</style>
