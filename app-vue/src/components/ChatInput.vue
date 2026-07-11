<template>
  <div class="chat-input">
    <div class="input-row">
      <textarea ref="textarea" v-model="text" :placeholder="placeholder" @keydown.enter.exact.prevent="submit" @input="autoResize" :disabled="disabled" rows="1"></textarea>
      <button class="send-btn" :disabled="!text.trim() || disabled" @click="submit" title="&#x53D1;&#x9001;"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M22 2 11 13" /><path d="m22 2-7 20-4-9-9-4 20-7Z" /></svg></button>
    </div>
    <div class="input-footer"><span>{{ footerText }}</span></div>
  </div>
</template>
<script setup>
import { computed, ref, nextTick } from 'vue'
const text = ref('')
const textarea = ref(null)
const props = defineProps({ disabled: Boolean, mode: { type: String, default: 'qa' } })
const emit = defineEmits(['send'])
const modeCopy = {
  qa: {
    placeholder: '输入金属材料、铸造工艺相关问题...',
    footer: 'AI 回答可能不准确，请核实关键数据',
  },
  requirement_clarification: {
    placeholder: '粘贴客户需求，提取工况、缺口和追问清单...',
    footer: '需求澄清会优先输出已知条件、待确认条件和风险',
  },
  solution_draft: {
    placeholder: '输入工况、性能目标和约束，生成方案草案...',
    footer: '方案草案仅作为工程初稿，请结合实验与标准验证',
  },
  selection_matrix: {
    placeholder: '输入候选材料、工况或目标，生成选型矩阵...',
    footer: '选型矩阵会对候选项、评价维度、风险和证据充分度进行对比',
  },
  defect_diagnosis: {
    placeholder: '输入缺陷现象、材料、工艺阶段或失效表现...',
    footer: '缺陷诊断会输出可能原因、排查步骤、工艺检查点和纠正措施',
  },
}
const placeholder = computed(() => (modeCopy[props.mode] || modeCopy.qa).placeholder)
const footerText = computed(() => (modeCopy[props.mode] || modeCopy.qa).footer)
function autoResize() { const el = textarea.value; if (el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 132) + 'px' } }
function submit() { if (!text.value.trim() || props.disabled) return; emit('send', text.value.trim()); text.value = ''; nextTick(() => { if (textarea.value) textarea.value.style.height = 'auto' }) }
</script>
<style scoped>
.chat-input { border-top: 1px solid var(--border-light); background: color-mix(in srgb, var(--bg-main) 88%, white); padding: 14px 18px 12px; }
.input-row { width: min(920px, calc(100% - 48px)); margin: 0 auto; display: flex; align-items: flex-end; gap: 10px; }
textarea { min-height: 46px; max-height: 132px; flex: 1; resize: none; border: 1px solid var(--border-light); border-radius: 12px; background: var(--bg-surface); color: var(--text-primary); padding: 12px 14px; line-height: 1.55; font-size: 14px; box-shadow: var(--shadow-control); transition: border-color .16s ease, box-shadow .16s ease; }
textarea::placeholder { color: #6b7788; }
textarea:focus { border-color: var(--accent); box-shadow: 0 0 0 4px var(--accent-soft); outline: none; }
textarea:disabled { opacity: .7; cursor: not-allowed; }
.send-btn { width: 46px; height: 46px; border: 0; border-radius: 12px; background: var(--accent); color: #fff; display: grid; place-items: center; cursor: pointer; transition: background .16s ease, transform .16s ease, opacity .16s ease; }
.send-btn:hover:not(:disabled) { background: var(--accent-strong); }
.send-btn:active:not(:disabled) { transform: translateY(1px); }
.send-btn:disabled { opacity: .4; cursor: not-allowed; }
.send-btn svg { width: 20px; height: 20px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.input-footer { margin-top: 8px; text-align: center; color: var(--text-muted); font-size: 12px; }
@media (max-width: 820px) { .input-row { width: min(100% - 24px, 920px); } }
</style>
