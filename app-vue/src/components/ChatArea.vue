<template>
  <main class="chat-area" ref="chatArea">
    <div id="chatArea" class="chat-inner">
      <!-- Welcome -->
      <div v-if="messages.length === 0 && !chat.isProcessing" id="welcome" class="welcome">
        <h1>????? AI ??</h1>
        <p class="welcome-subtitle">?????????????????????????????</p>
        <div class="suggestions">
          <div v-for="(s, i) in suggestions" :key="i" class="suggestion-chip" @click="('suggest', s.query)">{{ s.label }}</div>
        </div>
      </div>
      <!-- Messages -->
      <div v-for="(msg, i) in messages" :key="i">
        <MessageItem :msg="msg" :logs="chat.logs" />
      </div>
      <!-- Progress -->
      <ProgressSteps :steps="chat.progressSteps" :visible="chat.showProgress" />
      <!-- Loading -->
      <div v-if="chat.isProcessing && !messages.length" class="loading"><span>????...</span></div>
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
  { label: '???6061?????', query: '???6061?????' },
  { label: '?????????', query: '?????????' },
  { label: '????????', query: '????????' },
  { label: '????????', query: '????????' },
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
