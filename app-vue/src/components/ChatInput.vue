<template>
  <div class="chat-input">
    <div class="input-row">
      <textarea ref="textarea" v-model="text" placeholder="输入金属材料、铸造工艺相关问题..."
        @keydown.enter.exact.prevent="submit" @input="autoResize"
        :disabled="disabled" rows="1"></textarea>
      <button class="send-btn" :disabled="!text.trim() || disabled" @click="submit">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
      </button>
    </div>
    <div class="input-footer"><span>AI 回答可能不准确，请核实关键数据</span></div>
  </div>
</template>
<script setup>
import { ref, nextTick } from 'vue'
const text = ref('')
const textarea = ref(null)
defineProps({ disabled: Boolean })
const emit = defineEmits(['send'])
function autoResize() {
  const el = textarea.value
  if (el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 120) + 'px' }
}
function submit() {
  if (!text.value.trim() || this.disabled) return
  emit('send', text.value.trim())
  text.value = ''
  nextTick(() => { if (textarea.value) { textarea.value.style.height = 'auto' } })
}
</script>
<style scoped>
.chat-input { border-top: 1px solid var(--border-light); padding: 12px 16px; background: var(--bg-main); }
.input-row { display: flex; gap: 8px; align-items: flex-end; max-width: 740px; margin: 0 auto; width: 100%; }
.input-row textarea { flex: 1; padding: 10px 14px; border: 1px solid var(--border-light); border-radius: 16px; font-size: 14px; outline: none; resize: none; max-height: 120px; line-height: 1.5; background: var(--bg-sub); transition: border-color .2s; }
.input-row textarea:focus { border-color: var(--border-focus); }
.send-btn { flex-shrink: 0; width: 40px; height: 40px; border-radius: 50%; border: none; background: var(--text-primary); color: #fff; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: opacity .2s; }
.send-btn:disabled { opacity: .3; cursor: not-allowed; }
.send-btn:hover:not(:disabled) { opacity: .8; }
.input-footer { text-align: center; font-size: 11px; color: var(--text-muted); margin-top: 8px; }
</style>
