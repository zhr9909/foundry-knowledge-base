<template>
  <main class="chat-area" ref="chatArea">
    <div id="chatArea" class="chat-inner">
      <div v-if="messages.length === 0 && !chat.isProcessing" id="welcome" class="welcome">
        <div class="welcome-kicker">AI Native RAG Console</div>
        <h1>{{ welcomeCopy.title }}</h1>
        <p class="welcome-subtitle">{{ welcomeCopy.subtitle }}</p>
        <div class="suggestions"><button v-for="(s, i) in suggestions" :key="i" class="suggestion-chip" @click="$emit('suggest', s.query)"><span>{{ s.label }}</span></button></div>
      </div>
      <div class="messages-stack">
        <MessageItem v-for="(msg, i) in messages" :key="i" :msg="msg" :logs="chat.logs" @correct-context="$emit('suggest', $event)" />
        <ProgressSteps :steps="chat.progressSteps" :visible="chat.showProgress" />
        <div v-if="chat.isProcessing && !messages.length" class="loading"><span>{{ loadingText }}</span></div>
      </div>
    </div>
  </main>
</template>
<script setup>
import { computed, ref } from 'vue'
import MessageItem from './MessageItem.vue'
import ProgressSteps from './ProgressSteps.vue'
const props = defineProps({ messages: { type: Array, default: () => [] }, chat: Object })
defineEmits(['suggest'])
const loadingText = '\u6b63\u5728\u5904\u7406...'
const modeWelcome = {
  qa: {
    title: '铸造知识库 AI 助手',
    subtitle: '输入金属材料、铸造工艺相关问题，从技术手册知识库中检索答案',
    suggestions: [
      { label: '铝合金6061的力学性能', query: '铝合金6061的力学性能' },
      { label: '不锈钢的热处理温度', query: '不锈钢的热处理温度' },
      { label: '铜合金的铸造工艺', query: '铜合金的铸造工艺' },
      { label: '钛合金的抗拉强度', query: '钛合金的抗拉强度' },
    ],
  },
  requirement_clarification: {
    title: '客户需求澄清工作台',
    subtitle: '把客户的模糊描述拆成工况、性能目标、缺失条件、风险和追问清单',
    suggestions: [
      { label: '海水泵体，80℃，预算中等', query: '客户想做海水泵体，温度80℃，预算中等，需要耐腐蚀' },
      { label: '高温阀体需求澄清', query: '客户要做高温阀体，但只说要耐热耐磨，帮我澄清需求' },
      { label: '轻量化壳体约束梳理', query: '一个轻量化设备壳体，需要兼顾强度和铸造成形，帮我整理追问清单' },
    ],
  },
  solution_draft: {
    title: '材料铸造方案草案',
    subtitle: '围绕工况和约束生成候选材料、工艺路线、风险点、依据和验证步骤',
    suggestions: [
      { label: '耐腐蚀泵体方案', query: '海水环境泵体，80℃，中等预算，帮我出材料和铸造方案草案' },
      { label: '高强轻量结构件方案', query: '高强轻量结构件，要求可铸造、后续可热处理，帮我出方案草案' },
      { label: '耐磨阀体方案', query: '矿山工况耐磨阀体，冲蚀严重，帮我比较材料和工艺路线' },
    ],
  },
  selection_matrix: {
    title: '材料与工艺选型矩阵',
    subtitle: '把候选材料、工艺路线、性能目标、风险和证据放进一张可比较的工程决策表',
    suggestions: [
      { label: '海水泵体材料选型', query: '海水泵体，80℃，预算中等，帮我做材料选型矩阵' },
      { label: '钛/铝/铁合金对比', query: '钛合金、铝合金、铁合金之间怎么选，帮我做选型矩阵' },
      { label: '高强轻量结构件选型', query: '高强轻量结构件，要求可铸造和后续热处理，帮我做材料工艺选型矩阵' },
    ],
  },
  defect_diagnosis: {
    title: '铸造缺陷诊断工作台',
    subtitle: '把缺陷现象、材料、工艺阶段和现场信息转成可能原因、检查路径和纠正措施',
    suggestions: [
      { label: '铝合金铸件气孔', query: '铝合金铸件出现气孔，浇注后表面有针孔，怎么排查' },
      { label: '热裂问题排查', query: '铸件凝固后出现热裂，可能是什么原因，怎么检查和改进' },
      { label: '热处理后硬度不足', query: '热处理后硬度不够，可能是什么原因，需要检查哪些工艺参数' },
    ],
  },
}
const welcomeCopy = computed(() => modeWelcome[props.chat?.currentMode] || modeWelcome.qa)
const suggestions = computed(() => welcomeCopy.value.suggestions)
</script>
<style scoped>
.chat-area { flex: 1; overflow-y: auto; min-height: 0; }
.chat-inner { width: min(920px, calc(100% - 48px)); margin: 0 auto; padding: 30px 0 34px; }
.messages-stack { display: flex; flex-direction: column; gap: 18px; }
.welcome { min-height: calc(100vh - 180px); display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 42px 0; }
.welcome-kicker { color: var(--accent-strong); background: var(--accent-soft); border: 1px solid color-mix(in srgb, var(--accent) 24%, transparent); border-radius: 999px; padding: 5px 10px; font-size: 12px; font-weight: 700; margin-bottom: 16px; }
.welcome h1 { font-size: 32px; line-height: 1.2; font-weight: 780; letter-spacing: 0; text-wrap: balance; }
.welcome-subtitle { max-width: 580px; margin-top: 12px; font-size: 15px; line-height: 1.75; color: var(--text-secondary); text-wrap: pretty; }
.suggestions { margin-top: 26px; display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; max-width: 620px; }
.suggestion-chip { border: 1px solid var(--border-light); border-radius: 999px; background: var(--bg-surface); color: var(--text-secondary); min-height: 38px; padding: 0 16px; cursor: pointer; box-shadow: var(--shadow-control); transition: border-color .16s ease, background .16s ease, color .16s ease; }
.suggestion-chip:hover { border-color: var(--accent); background: var(--accent-soft); color: var(--accent-strong); }
.loading { padding: 18px; color: var(--text-muted); text-align: center; }
@media (max-width: 820px) { .chat-inner { width: min(100% - 24px, 920px); } .welcome h1 { font-size: 26px; } }
</style>
