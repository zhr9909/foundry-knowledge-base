<template>
  <div class="mode-switcher" role="tablist" aria-label="任务模式">
    <button
      v-for="item in modes"
      :key="item.value"
      type="button"
      class="mode-option"
      :class="{ active: modelValue === item.value }"
      :disabled="disabled"
      role="tab"
      :aria-selected="modelValue === item.value"
      @click="$emit('update:modelValue', item.value)"
    >
      <span class="mode-name">{{ item.label }}</span>
      <span class="mode-hint">{{ item.hint }}</span>
    </button>
  </div>
</template>

<script setup>
defineProps({
  modelValue: { type: String, default: 'qa' },
  disabled: Boolean,
})
defineEmits(['update:modelValue'])

const modes = [
  { value: 'qa', label: '知识问答', hint: '检索回答' },
  { value: 'requirement_clarification', label: '需求澄清', hint: '条件追问' },
  { value: 'solution_draft', label: '方案草案', hint: '工程建议' },
  { value: 'selection_matrix', label: '选型矩阵', hint: '候选对比' },
  { value: 'defect_diagnosis', label: '缺陷诊断', hint: '现场排查' },
]
</script>

<style scoped>
.mode-switcher {
  display: inline-grid;
  grid-template-columns: repeat(5, minmax(70px, 1fr));
  gap: 3px;
  padding: 3px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-surface-2);
  box-shadow: var(--shadow-control);
}
.mode-option {
  min-width: 0;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-muted);
  padding: 5px 7px;
  cursor: pointer;
  text-align: left;
  transition: background .16s ease, color .16s ease, box-shadow .16s ease;
}
.mode-option:hover:not(:disabled) {
  color: var(--text-primary);
  background: var(--bg-hover);
}
.mode-option.active {
  color: var(--text-primary);
  background: var(--bg-surface);
  box-shadow: 0 1px 4px rgba(16, 24, 40, .08);
}
.mode-option:disabled {
  cursor: not-allowed;
  opacity: .66;
}
.mode-name,
.mode-hint {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mode-name {
  font-size: 12px;
  font-weight: 750;
  line-height: 1.25;
}
.mode-hint {
  margin-top: 1px;
  font-size: 10px;
  line-height: 1.2;
}
@media (max-width: 980px) {
  .mode-switcher { grid-template-columns: repeat(5, 1fr); width: 100%; }
  .mode-hint { display: none; }
}
@media (max-width: 620px) {
  .mode-switcher { grid-template-columns: repeat(2, 1fr); }
}
</style>
