<template>
  <main class="chat-area" ref="chatArea">
    <div id="chatArea" class="chat-inner">
      <div v-if="messages.length === 0 && !chat.isProcessing" id="welcome" class="welcome">
        <h1>铸造知识库 AI 助手</h1>
        <p class="welcome-subtitle">输入金属材料、铸造工艺相关问题，从技术手册知识库中检索答案</p>
        <div class="suggestions">
          <div v-for="(s, i) in suggestions" :key="i" class="suggestion-chip" @click="$emit('suggest', s.query)">{{ s.label }}</div>
        </div>
      </div>
      <div v-for="(msg, i) in messages" :key="i"><MessageItem :msg="msg" :logs="chat.logs" /></div>
      <ProgressSteps :steps="chat.progressSteps" :visible="chat.showProgress" />
      <div v-if="chat.isProcessing && !messages.length" class="loading"><span>正在处理...</span></div>
    </div>
  </main>
</template>
<script setup>
import { ref } from 'vue'
import MessageItem from './MessageItem.vue'
import ProgressSteps from './ProgressSteps.vue'
const props = defineProps({ messages: { type: Array, default: () => [] }, chat: Object })
defineEmits(['suggest'])
const suggestions = [
  { label: '铝合金6061的力学性能', query: '铝合金6061的力学性能' },
  { label: '不锈钢的热处理温度', query: '不锈钢的热处理温度' },
  { label: '铜合金的铸造工艺', query: '铜合金的铸造工艺' },
  { label: '钛合金的抗拉强度', query: '钛合金的抗拉强度' },
]
</script>
<style scoped>
.chat-area { flex: 1; overflow-y: auto; padding: 0; }
.chat-inner { max-width: 740px; margin: 0 auto; padding: 24px 16px; }
.welcome { text-align: center; padding: 60px 0 40px; }
.welcome h1 { font-size: 28px; font-weight: 600; margin-bottom: 8px; letter-spacing: -0.5px; }
.welcome-subtitle { font-size: 14px; color: var(--text-secondary); }
.suggestions { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 24px; }
.suggestion-chip { padding: 8px 16px; border: 1px solid var(--border-light); border-radius: 20px; font-size: 13px; cursor: pointer; color: var(--text-secondary); transition: all .2s; }
.suggestion-chip:hover { border-color: var(--border-focus); color: var(--text-primary); }
.loading { text-align: center; padding: 40px; color: var(--text-muted); font-size: 14px; }
</style>
