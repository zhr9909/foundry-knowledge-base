<template>
  <div v-if="visible" id="progressSteps" class="progress-steps">
    <div class="step" :class="stepClass('rewrite')" data-step="rewrite">
      <span class="step-label">🔍 分析问题</span>
      <span class="step-status">{{ steps.rewrite }}</span>
    </div>
    <span class="step-arrow">➡</span>
    <div class="step" :class="stepClass('search')" data-step="search">
      <span class="step-label">📘 检索知识库</span>
      <span class="step-status">{{ steps.search }}</span>
    </div>
    <span class="step-arrow">➡</span>
    <div class="step" :class="stepClass('context')" data-step="context">
      <span class="step-label">📎 精选上下文</span>
      <span class="step-status">{{ steps.context }}</span>
    </div>
    <span class="step-arrow">➡</span>
    <div class="step" :class="stepClass('generate')" data-step="generate">
      <span class="step-label">🧻 生成回答</span>
      <span class="step-status">{{ steps.generate }}</span>
    </div>
    <span class="step-arrow">➡</span>
    <div class="step" :class="stepClass('check')" data-step="check">
      <span class="step-label">✅ 质量检查</span>
      <span class="step-status">{{ steps.check }}</span>
    </div>
  </div>
</template>
<script setup>
defineProps({ steps: { type: Object, default: () => ({}) }, visible: Boolean })
function stepClass(name) {
  const s = this?.steps?.[name]
  if (!s || s === '') return ''
  if (s === 'active') return 'active'
  if (s === 'done') return 'done'
  return 'done'
}
</script>
<style scoped>
.progress-steps { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 12px 16px; background: var(--bg-sub); border-radius: var(--radius-sm); margin: 8px 0; flex-wrap: wrap; }
.step { display: flex; align-items: center; gap: 4px; font-size: 12px; color: var(--text-muted); white-space: nowrap; }
.step.active { color: var(--text-primary); font-weight: 500; }
.step.done { color: #2ecc71; }
.step-status { font-size: 11px; color: var(--text-muted); }
.step.done .step-status { color: #2ecc71; }
.step-arrow { color: var(--text-muted); font-size: 10px; }
</style>
