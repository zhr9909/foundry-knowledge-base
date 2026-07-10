<template>
  <div v-if="visible" id="progressSteps" class="progress-steps" aria-label="Processing progress">
    <template v-for="(item, index) in stepItems" :key="item.key">
      <div class="step" :class="stepClass(item.key)" :data-step="item.key">
        <span class="step-node"></span><span class="step-label">{{ item.label }}</span><span v-if="steps[item.key] && steps[item.key] !== 'active'" class="step-status">{{ steps[item.key] }}</span>
      </div>
      <span v-if="index < stepItems.length - 1" class="step-arrow"></span>
    </template>
  </div>
</template>
<script setup>
const props = defineProps({ steps: { type: Object, default: () => ({}) }, visible: Boolean })
const stepItems = [
  { key: 'rewrite', label: '\u5206\u6790\u95ee\u9898' },
  { key: 'search', label: '\u68c0\u7d22\u77e5\u8bc6\u5e93' },
  { key: 'context', label: '\u7cbe\u9009\u4e0a\u4e0b\u6587' },
  { key: 'generate', label: '\u751f\u6210\u56de\u7b54' },
  { key: 'check', label: '\u8d28\u91cf\u68c0\u67e5' },
]
function stepClass(name) { const s = props.steps?.[name]; if (!s) return ''; if (s === 'active') return 'active'; return 'done' }
</script>
<style scoped>
.progress-steps { display: flex; align-items: center; flex-wrap: wrap; gap: 7px; margin: 2px 0 0 48px; padding: 10px 12px; border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--bg-surface); color: var(--text-muted); }
.step { display: inline-flex; align-items: center; gap: 6px; min-height: 24px; font-size: 12px; white-space: nowrap; }
.step-node { width: 7px; height: 7px; border-radius: 50%; background: #c7d2df; }
.step.active { color: var(--accent-strong); font-weight: 700; }
.step.active .step-node { background: var(--accent); box-shadow: 0 0 0 4px var(--accent-soft); }
.step.done { color: var(--success); }
.step.done .step-node { background: var(--success); }
.step-status { color: inherit; opacity: .8; }
.step-arrow { width: 18px; height: 1px; background: var(--border-strong); opacity: .7; }
@media (max-width: 820px) { .progress-steps { margin-left: 0; } }
</style>