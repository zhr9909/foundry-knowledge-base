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
  let text = props.msg.content || ''
  if (props.msg.role === 'user') return text
  if (!props.msg.metadata.citations) return text.replace(/\n/g, '<br>')
  let result = text
  const citations = props.msg.metadata.citations || []
  for (let i = 0; i < citations.length; i++) {
    const c = citations[i]
    const page = c.page || '?'
    result = result.replace(new RegExp('\\[' + (i+1) + '\\]', 'g'),
      '<sup class="citation-ref" onclick="event.preventDefault(); window.open(\'/static/pdf-viewer.html?page=' + page + '\')">[' + (i+1) + ']</sup>')
  }
  result = result.replace(/\*\*(.*?)\*\*/g, "<strong>`$1</strong>")
  // Bold: **text** -> <strong>text</strong>
  result = result.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
  // Bold markdown
  result = result.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
  return result.replace(/\n/g, '<br>')
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
