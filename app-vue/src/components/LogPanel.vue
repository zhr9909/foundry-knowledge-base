<template>
  <details class="log-panel-inline" open>
    <summary class="log-panel-header">
      <span class="log-panel-title">📋 处理日志</span>
      <span class="log-panel-badge">{{ logs.length }}</span>
    </summary>
    <div class="log-panel-body">
      <div v-for="(log, i) in logs" :key="i" class="log-entry" :class="log.level">
        <span class="log-time">[{{ log.time }}]</span>
        <span class="log-icon">{{ iconFor(log.msg) }}</span>
        <span class="log-msg">{{ log.msg }}</span>
      </div>
    </div>
  </details>
</template>
<script setup>
defineProps({ logs: { type: Array, default: () => [] } })
function iconFor(msg) {
  if (msg.includes('拆解') || msg.includes('语义')) return '\uD83D\uDD33'
  if (msg.includes('检索')) return '\uD83D\uDCD7'
  if (msg.includes('精选') || msg.includes('上下文')) return '\uD83D\uDCCE'
  if (msg.includes('提示词') || msg.includes('生成')) return '\uD83E\uDDFB'
  if (msg.includes('质量') || msg.includes('检查')) return '\u2705'
  if (msg.includes('降级') || msg.includes('兜底')) return '\u26A0\uFE0F'
  if (msg.includes('偏低') || msg.includes('新一轮')) return '\uD83D\uDD04'
  if (msg.includes('失败')) return '\u274C'
  return '\u25B6'
}
</script>
<style scoped>
.log-panel-inline { margin: 0 0 8px 0; border: 1px solid var(--border-light); border-radius: var(--radius-sm); background: var(--bg-sub); overflow: hidden; }
.log-panel-header { display: flex; align-items: center; gap: 8px; padding: 6px 10px; cursor: pointer; font-size: 12px; color: var(--text-secondary); user-select: none; }
.log-panel-title { flex: 1; }
.log-panel-badge { background: var(--text-primary); color: #fff; font-size: 10px; min-width: 18px; height: 18px; border-radius: 9px; display: flex; align-items: center; justify-content: center; }
.log-panel-body { padding: 4px 10px 8px; max-height: 180px; overflow-y: auto; display: flex; flex-direction: column; gap: 2px; }
.log-entry { display: flex; align-items: baseline; gap: 4px; font-size: 11px; line-height: 1.5; color: var(--text-secondary); }
.log-time { color: var(--text-muted); flex-shrink: 0; }
.log-icon { flex-shrink: 0; }
.log-msg { word-break: break-all; }
.log-entry.retry .log-msg { color: #e67e22; }
.log-entry.fallback .log-msg { color: #e74c3c; }
.log-entry.error .log-msg { color: #e74c3c; font-weight: 500; }
</style>
