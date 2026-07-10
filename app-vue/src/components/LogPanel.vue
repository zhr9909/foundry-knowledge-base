<template>
  <details class="log-panel-inline" open>
    <summary class="log-panel-header"><span class="log-panel-title">{{ title }}</span><span class="log-panel-badge">{{ logs.length }}</span></summary>
    <div class="log-panel-body">
      <div v-for="(log, i) in logs" :key="i" class="log-entry" :class="log.level"><span class="log-time">[{{ log.time }}]</span><span class="log-icon">{{ iconFor(log.msg) }}</span><span class="log-msg">{{ log.msg }}</span></div>
    </div>
  </details>
</template>
<script setup>
defineProps({ logs: { type: Array, default: () => [] } })
const title = '\u5904\u7406\u65e5\u5fd7'
function iconFor(msg) {
  if (msg.includes('\u62c6\u89e3') || msg.includes('\u8bed\u4e49')) return 'S'
  if (msg.includes('\u68c0\u7d22')) return 'R'
  if (msg.includes('\u7cbe\u9009') || msg.includes('\u4e0a\u4e0b\u6587')) return 'C'
  if (msg.includes('\u63d0\u793a\u8bcd') || msg.includes('\u751f\u6210')) return 'G'
  if (msg.includes('\u8d28\u91cf') || msg.includes('\u68c0\u67e5')) return 'Q'
  if (msg.includes('\u5931\u8d25')) return '!'
  return '>'
}
</script>
<style scoped>
.log-panel-inline { margin-bottom: 12px; border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--bg-surface-2); overflow: hidden; }
.log-panel-header { display: flex; align-items: center; gap: 8px; padding: 8px 10px; cursor: pointer; color: var(--text-secondary); font-size: 12px; font-weight: 650; user-select: none; }
.log-panel-title { flex: 1; }
.log-panel-badge { min-width: 20px; height: 20px; border-radius: 999px; display: grid; place-items: center; background: var(--bg-user); color: white; font-size: 11px; }
.log-panel-body { max-height: 190px; overflow-y: auto; padding: 0 10px 10px; display: flex; flex-direction: column; gap: 4px; }
.log-entry { display: flex; align-items: baseline; gap: 6px; color: var(--text-secondary); font-family: var(--font-mono); font-size: 11px; line-height: 1.55; }
.log-time { color: var(--text-muted); flex: 0 0 auto; }
.log-icon { width: 15px; height: 15px; border-radius: 4px; display: inline-grid; place-items: center; background: var(--accent-soft); color: var(--accent-strong); font-size: 9px; font-weight: 800; flex: 0 0 auto; }
.log-msg { word-break: break-word; }
.log-entry.error .log-msg { color: var(--danger); font-weight: 700; }
.log-entry.retry .log-msg, .log-entry.fallback .log-msg { color: var(--warning); }
</style>