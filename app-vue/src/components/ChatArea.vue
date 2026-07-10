<template>
  <main class="chat-area" ref="chatArea">
    <div id="chatArea" class="chat-inner">
      <div v-if="messages.length === 0 && !chat.isProcessing" id="welcome" class="welcome">
        <div class="welcome-kicker">AI Native RAG Console</div>
        <h1>&#x94F8;&#x9020;&#x77E5;&#x8BC6;&#x5E93; AI &#x52A9;&#x624B;</h1>
        <p class="welcome-subtitle">&#x8F93;&#x5165;&#x91D1;&#x5C5E;&#x6750;&#x6599;&#x3001;&#x94F8;&#x9020;&#x5DE5;&#x827A;&#x76F8;&#x5173;&#x95EE;&#x9898;&#xFF0C;&#x4ECE;&#x6280;&#x672F;&#x624B;&#x518C;&#x77E5;&#x8BC6;&#x5E93;&#x4E2D;&#x68C0;&#x7D22;&#x7B54;&#x6848;</p>
        <div class="suggestions"><button v-for="(s, i) in suggestions" :key="i" class="suggestion-chip" @click="$emit('suggest', s.query)"><span>{{ s.label }}</span></button></div>
      </div>
      <div class="messages-stack">
        <MessageItem v-for="(msg, i) in messages" :key="i" :msg="msg" :logs="chat.logs" />
        <ProgressSteps :steps="chat.progressSteps" :visible="chat.showProgress" />
        <div v-if="chat.isProcessing && !messages.length" class="loading"><span>{{ loadingText }}</span></div>
      </div>
    </div>
  </main>
</template>
<script setup>
import { ref } from 'vue'
import MessageItem from './MessageItem.vue'
import ProgressSteps from './ProgressSteps.vue'
defineProps({ messages: { type: Array, default: () => [] }, chat: Object })
defineEmits(['suggest'])
const loadingText = '\u6b63\u5728\u5904\u7406...'
const suggestions = [
  { label: '\u94dd\u5408\u91d16061\u7684\u529b\u5b66\u6027\u80fd', query: '\u94dd\u5408\u91d16061\u7684\u529b\u5b66\u6027\u80fd' },
  { label: '\u4e0d\u9508\u94a2\u7684\u70ed\u5904\u7406\u6e29\u5ea6', query: '\u4e0d\u9508\u94a2\u7684\u70ed\u5904\u7406\u6e29\u5ea6' },
  { label: '\u94dc\u5408\u91d1\u7684\u94f8\u9020\u5de5\u827a', query: '\u94dc\u5408\u91d1\u7684\u94f8\u9020\u5de5\u827a' },
  { label: '\u949b\u5408\u91d1\u7684\u6297\u62c9\u5f3a\u5ea6', query: '\u949b\u5408\u91d1\u7684\u6297\u62c9\u5f3a\u5ea6' },
]
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